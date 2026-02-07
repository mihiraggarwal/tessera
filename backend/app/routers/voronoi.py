"""
Voronoi computation router - handles Voronoi diagram API endpoints
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.voronoi_engine import VoronoiEngine
from app.services.population_calc import PopulationService
from app.services.analytics_service import AnalyticsService
from app.services.road_network_service import RoadNetworkService

router = APIRouter()


class Facility(BaseModel):
    """A facility with coordinates"""
    id: Optional[str] = None
    name: str
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    type: Optional[str] = None


class VoronoiRequest(BaseModel):
    """Request to compute Voronoi diagram"""
    facilities: List[Facility]
    clip_to_india: bool = True
    include_population: bool = False
    state_filter: Optional[str] = None  # If set, clip to this state instead of all India
    use_road_network: bool = False  # If True, compute Voronoi based on road distance
    district_filter: Optional[str] = None  # Required when use_road_network is True


class VoronoiResponse(BaseModel):
    """GeoJSON response with Voronoi polygons"""
    type: str = "FeatureCollection"
    features: List[dict]


@router.post("/compute", response_model=VoronoiResponse)
async def compute_voronoi(request: VoronoiRequest):
    """
    Compute Voronoi diagram for given facility coordinates.
    Returns GeoJSON FeatureCollection of Voronoi polygons.
    
    If use_road_network is True, computes Voronoi based on road network distances
    instead of Euclidean distances. Requires district_filter to be set.
    """
    # Road network mode has different minimum (2 facilities)
    min_facilities = 2 if request.use_road_network else 3
    
    if len(request.facilities) < min_facilities:
        raise HTTPException(
            status_code=400,
            detail=f"At least {min_facilities} facilities are required to compute Voronoi diagram"
        )
    
    try:
        # Road Network Voronoi mode
        if request.use_road_network:
            if not request.district_filter:
                raise HTTPException(
                    status_code=400,
                    detail="district_filter is required when use_road_network is True"
                )
            
            road_service = RoadNetworkService()
            
            # Filter facilities to only those within the district
            facilities_dict = [
                {"id": f.id or str(i), "name": f.name, "lat": f.lat, "lng": f.lng, "type": f.type}
                for i, f in enumerate(request.facilities)
            ]
            filtered_facilities = road_service.filter_facilities_in_district(
                facilities_dict, request.district_filter
            )
            
            if len(filtered_facilities) < 2:
                raise HTTPException(
                    status_code=400,
                    detail=f"At least 2 facilities within {request.district_filter} are required for road network Voronoi"
                )
            
            geojson = road_service.compute_road_voronoi(
                filtered_facilities, request.district_filter
            )
            
            return VoronoiResponse(**geojson)
        
        # Standard Euclidean Voronoi mode
        engine = VoronoiEngine()
        
        # Convert facilities to coordinate list
        coords = [(f.lng, f.lat) for f in request.facilities]
        names = [f.name for f in request.facilities]
        facility_ids = [f.id or str(i) for i, f in enumerate(request.facilities)]
        types = [f.type for f in request.facilities]
        
        # Compute Voronoi and build DCEL for spatial queries
        geojson, dcel = engine.compute_voronoi_with_dcel(
            coords=coords,
            names=names,
            facility_ids=facility_ids,
            types=types,
            clip_to_india=request.clip_to_india,
            state_filter=request.state_filter
        )
        
        if request.include_population:
            pop_service = PopulationService()
            pop_data = pop_service.calculate_weighted_population(geojson['features'])
            
            # Merge population data into features
            for feature in geojson['features']:
                fid = feature['properties']['facility_id']
                # find matching population result
                match = next((p for p in pop_data if str(p['facility_id']) == str(fid)), None)
                if match:
                    feature['properties']['population'] = match['total_population']
                    feature['properties']['population_breakdown'] = match['breakdown']
        
        return VoronoiResponse(**geojson)
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sample")
async def get_sample_voronoi():
    """
    Return a sample Voronoi diagram for testing.
    Uses hardcoded coordinates of major Indian cities.
    """
    sample_facilities = [
        Facility(id="1", name="Delhi", lat=28.6139, lng=77.2090, type="city"),
        Facility(id="2", name="Mumbai", lat=19.0760, lng=72.8777, type="city"),
        Facility(id="3", name="Chennai", lat=13.0827, lng=80.2707, type="city"),
        Facility(id="4", name="Kolkata", lat=22.5726, lng=88.3639, type="city"),
        Facility(id="5", name="Bangalore", lat=12.9716, lng=77.5946, type="city"),
        Facility(id="6", name="Hyderabad", lat=17.3850, lng=78.4867, type="city"),
    ]
    
    request = VoronoiRequest(facilities=sample_facilities, clip_to_india=True)
    return await compute_voronoi(request)


@router.post("/insights")
async def get_facility_insights(request: VoronoiRequest):
    """
    Compute comprehensive facility insights including:
    - Minimum enclosing circle (coverage radius)
    - Largest empty circle (underserved areas)
    - Most overburdened facilities (by population)
    - Most underserved areas (by coverage area)
    """
    if len(request.facilities) < 3:
        raise HTTPException(
            status_code=400,
            detail="At least 3 facilities are required for insights"
        )
    
    try:
        # First compute Voronoi with population
        engine = VoronoiEngine()
        
        coords = [(f.lng, f.lat) for f in request.facilities]
        names = [f.name for f in request.facilities]
        facility_ids = [f.id or str(i) for i, f in enumerate(request.facilities)]
        types = [f.type for f in request.facilities]
        
        geojson, dcel = engine.compute_voronoi_with_dcel(
            coords=coords,
            names=names,
            facility_ids=facility_ids,
            types=types,
            clip_to_india=request.clip_to_india,
            state_filter=request.state_filter
        )
        
        # Add population data
        pop_service = PopulationService()
        pop_data = pop_service.calculate_weighted_population(geojson['features'])
        
        for feature in geojson['features']:
            fid = feature['properties']['facility_id']
            match = next((p for p in pop_data if str(p['facility_id']) == str(fid)), None)
            if match:
                feature['properties']['population'] = match['total_population']
                feature['properties']['population_breakdown'] = match['breakdown']
        
        # Get boundary geometry for filtering and circle restriction
        boundary_geom = None
        if request.state_filter:
            boundary_geom = engine._get_state_boundary_wgs84(request.state_filter)
        elif request.clip_to_india:
            boundary_geom = engine._india_boundary_wgs84

        # Compute insights
        analytics = AnalyticsService()
        facilities_dict = [{"lat": f.lat, "lng": f.lng, "name": f.name, "id": f.id or str(i)} for i, f in enumerate(request.facilities)]
        insights = analytics.compute_facility_insights(geojson['features'], facilities_dict, boundary_geom)
        
        return insights
        
    except Exception as e:
        import traceback
        print(f"Error in get_facility_insights: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


class FindNearestRequest(BaseModel):
    """Request to find nearest facility to a click location"""
    click_lat: float = Field(..., ge=-90, le=90)
    click_lng: float = Field(..., ge=-180, le=180)
    facilities: List[Facility]


@router.post("/find-nearest")
async def find_nearest_facility(request: FindNearestRequest):
    """
    Find the facility nearest to a clicked location.
    Returns the index and details of the nearest facility.
    """
    if len(request.facilities) == 0:
        raise HTTPException(status_code=400, detail="No facilities provided")
    
    try:
        analytics = AnalyticsService()
        coords = [(f.lng, f.lat) for f in request.facilities]
        
        nearest_idx = analytics.find_nearest_facility_index(
            (request.click_lng, request.click_lat),
            coords
        )
        
        if nearest_idx < 0:
            return {"index": -1, "facility": None}
        
        nearest = request.facilities[nearest_idx]
        return {
            "index": nearest_idx,
            "facility": {
                "id": nearest.id,
                "name": nearest.name,
                "lat": nearest.lat,
                "lng": nearest.lng,
                "type": nearest.type
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== Road Network Endpoints ==============

@router.get("/road-districts")
async def get_available_road_districts():
    """
    Get list of districts that have available road network data.
    These are the only districts where road network Voronoi can be computed.
    """
    try:
        road_service = RoadNetworkService()
        return road_service.get_available_districts()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/road-districts/{district_id}/boundary")
async def get_road_district_boundary(district_id: str):
    """
    Get the boundary GeoJSON for a road network district.
    Used to display the district boundary on the map.
    """
    try:
        road_service = RoadNetworkService()
        boundary = road_service.get_district_boundary(district_id)
        
        if not boundary:
            raise HTTPException(
                status_code=404,
                detail=f"District '{district_id}' not found"
            )
        
        return boundary
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/road-districts/{district_id}/initialize")
async def initialize_road_network(district_id: str):
    """
    Initialize (download and cache) the road network for a district.
    This can be called proactively to avoid delays during Voronoi computation.
    
    Returns information about the loaded road network.
    """
    try:
        road_service = RoadNetworkService()
        G = road_service.load_or_download_graph(district_id)
        
        return {
            "district_id": district_id,
            "status": "ready",
            "nodes": len(G.nodes),
            "edges": len(G.edges)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/road-districts/{district_id}/edges")
async def get_road_edges(district_id: str, simplify: bool = True):
    """
    Get road network edges as GeoJSON for visualization on the map.
    
    Args:
        district_id: ID of the district
        simplify: If True, only return major roads to reduce data size (default: True)
        
    Returns:
        GeoJSON FeatureCollection of road edges as LineStrings
    """
    import math
    
    def sanitize_value(v):
        """Replace NaN/Infinity values with None or 0."""
        if isinstance(v, float):
            if math.isnan(v) or math.isinf(v):
                return 0.0
        return v
    
    def sanitize_geojson(obj):
        """Recursively sanitize all float values in a nested structure."""
        if isinstance(obj, dict):
            return {k: sanitize_geojson(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [sanitize_geojson(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(sanitize_geojson(item) for item in obj)
        elif isinstance(obj, float):
            return sanitize_value(obj)
        return obj
    
    try:
        road_service = RoadNetworkService()
        result = road_service.get_road_edges_geojson(district_id, simplify=simplify)
        # Sanitize the result to remove any NaN/Infinity values
        return sanitize_geojson(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


