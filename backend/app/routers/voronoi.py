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
        
        # Compute Voronoi
        geojson = engine.compute_voronoi(
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
        
        geojson = engine.compute_voronoi(
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
