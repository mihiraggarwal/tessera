"""
Voronoi computation router - handles Voronoi diagram API endpoints
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.voronoi_engine import VoronoiEngine
from app.services.population_calc import PopulationService
from app.services.analytics_service import AnalyticsService

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


class VoronoiResponse(BaseModel):
    """GeoJSON response with Voronoi polygons"""
    type: str = "FeatureCollection"
    features: List[dict]


@router.post("/compute", response_model=VoronoiResponse)
async def compute_voronoi(request: VoronoiRequest):
    """
    Compute Voronoi diagram for given facility coordinates.
    Returns GeoJSON FeatureCollection of Voronoi polygons.
    """
    if len(request.facilities) < 3:
        raise HTTPException(
            status_code=400,
            detail="At least 3 facilities are required to compute Voronoi diagram"
        )
    
    try:
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
    
    except Exception as e:
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


# === Route Voronoi Endpoints ===

from app.services.route_voronoi_service import (
    RouteVoronoiEngine, RouteVoronoiConfig, 
    get_route_voronoi_engine, reset_route_voronoi_engine
)
from app.services.routing_service import get_routing_service, RoutingConfig, set_routing_config
from app.services.dcel import get_current_dcel


class RouteVoronoiRequest(BaseModel):
    """Request to compute route-based Voronoi diagram"""
    facilities: List[Facility]
    clip_to_india: bool = True
    state_filter: Optional[str] = None
    config: Optional[dict] = None  # RouteVoronoiConfig fields


class RouteVoronoiCompareRequest(BaseModel):
    """Request to compare Euclidean vs Route Voronoi"""
    facilities: List[Facility]
    clip_to_india: bool = True
    state_filter: Optional[str] = None
    route_config: Optional[dict] = None


@router.post("/compute-route")
async def compute_route_voronoi(request: RouteVoronoiRequest):
    """
    Compute route-based Voronoi diagram using road network distances.
    
    Uses a candidate-filtered approach:
    1. Compute Euclidean Voronoi for candidate filtering
    2. For each grid point, query routing API for road distance to k nearest facilities
    3. Assign grid point to facility with minimum road distance
    4. Interpolate grid assignments into polygons
    
    Requires OSRM routing service to be running.
    """
    if len(request.facilities) < 3:
        raise HTTPException(
            status_code=400,
            detail="At least 3 facilities are required"
        )
    
    try:
        # First compute Euclidean Voronoi to build DCEL
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
        
        # Get boundary for route Voronoi computation
        if request.state_filter:
            boundary = engine._get_state_boundary_wgs84(request.state_filter)
        elif request.clip_to_india:
            boundary = engine._india_boundary_wgs84
        else:
            # Use convex hull of facilities
            from shapely.geometry import MultiPoint
            boundary = MultiPoint(coords).convex_hull.buffer(0.5)
        
        # Parse route config
        config_dict = request.config or {}
        route_config = RouteVoronoiConfig(
            grid_density=config_dict.get('grid_density', 50),
            base_k=config_dict.get('base_k', 5),
            adaptive_k=config_dict.get('adaptive_k', True),
            distortion_threshold=config_dict.get('distortion_threshold', 3.0),
            connectivity_check=config_dict.get('connectivity_check', True)
        )
        
        # Compute route Voronoi
        reset_route_voronoi_engine()  # Use fresh engine with new DCEL
        route_engine = RouteVoronoiEngine(dcel=dcel)
        result = route_engine.compute_sync(boundary, route_config)
        
        return route_engine.to_geojson(result)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
async def compare_euclidean_route(request: RouteVoronoiCompareRequest):
    """
    Compare Euclidean vs Route Voronoi side-by-side.
    
    Returns both diagrams with difference metrics.
    """
    if len(request.facilities) < 3:
        raise HTTPException(
            status_code=400,
            detail="At least 3 facilities are required"
        )
    
    try:
        # Compute Euclidean Voronoi
        engine = VoronoiEngine()
        
        coords = [(f.lng, f.lat) for f in request.facilities]
        names = [f.name for f in request.facilities]
        facility_ids = [f.id or str(i) for i, f in enumerate(request.facilities)]
        types = [f.type for f in request.facilities]
        
        euclidean_geojson, dcel = engine.compute_voronoi_with_dcel(
            coords=coords,
            names=names,
            facility_ids=facility_ids,
            types=types,
            clip_to_india=request.clip_to_india,
            state_filter=request.state_filter
        )
        
        # Get boundary
        if request.state_filter:
            boundary = engine._get_state_boundary_wgs84(request.state_filter)
        elif request.clip_to_india:
            boundary = engine._india_boundary_wgs84
        else:
            from shapely.geometry import MultiPoint
            boundary = MultiPoint(coords).convex_hull.buffer(0.5)
        
        # Parse route config  
        config_dict = request.route_config or {}
        route_config = RouteVoronoiConfig(
            grid_density=config_dict.get('grid_density', 30),  # Lower for comparison
            base_k=config_dict.get('base_k', 5),
            adaptive_k=config_dict.get('adaptive_k', True)
        )
        
        # Compute route Voronoi
        reset_route_voronoi_engine()
        route_engine = RouteVoronoiEngine(dcel=dcel)
        route_result = route_engine.compute_sync(boundary, route_config)
        route_geojson = route_engine.to_geojson(route_result)
        
        # Calculate comparison metrics
        euclidean_areas = {}
        for feature in euclidean_geojson['features']:
            fid = feature['properties']['facility_id']
            euclidean_areas[fid] = feature['properties'].get('area_km2', 0)
        
        route_areas = {}
        for feature in route_geojson['features']:
            fid = feature['properties']['facility_id']
            route_areas[fid] = feature['properties'].get('area_km2', 0)
        
        # Compute differences
        comparison_metrics = []
        for fid in set(euclidean_areas.keys()) | set(route_areas.keys()):
            e_area = euclidean_areas.get(fid, 0)
            r_area = route_areas.get(fid, 0)
            change_pct = ((r_area - e_area) / e_area * 100) if e_area > 0 else 0
            comparison_metrics.append({
                'facility_id': fid,
                'euclidean_area_km2': round(e_area, 2),
                'route_area_km2': round(r_area, 2),
                'area_change_pct': round(change_pct, 1)
            })
        
        return {
            "euclidean_voronoi": euclidean_geojson,
            "route_voronoi": route_geojson,
            "comparison": {
                "facility_metrics": comparison_metrics,
                "route_metadata": route_result.metadata
            }
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/routing-health")
async def check_routing_health():
    """Check if OSRM routing service is available."""
    try:
        routing = get_routing_service()
        health = routing.health_check_sync()
        return health
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


class RoutingConfigRequest(BaseModel):
    """Request to update routing configuration"""
    base_url: str = "http://localhost:5000"
    profile: str = "car"
    timeout_seconds: float = 10.0


@router.post("/routing-config")
async def update_routing_config(config: RoutingConfigRequest):
    """Update OSRM routing configuration."""
    try:
        new_config = RoutingConfig(
            base_url=config.base_url,
            profile=config.profile,
            timeout_seconds=config.timeout_seconds
        )
        set_routing_config(new_config)
        
        # Test the new config
        routing = get_routing_service()
        health = routing.health_check_sync()
        
        return {
            "status": "updated",
            "health": health
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

