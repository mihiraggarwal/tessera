"""
Routing Analysis Router - Point-based route analysis endpoints.

Provides on-demand route analysis for specific locations, supporting
the hybrid approach: Euclidean Voronoi + on-demand route queries.
"""
from typing import List, Optional, Tuple
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.routing_service import get_routing_service, RoutingConfig, set_routing_config
from app.services.dcel import get_current_dcel, DCEL

router = APIRouter()


class PointAnalysisRequest(BaseModel):
    """Request to analyze a specific point's accessibility."""
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    k_candidates: int = Field(default=5, ge=1, le=20)


class FacilityInfo(BaseModel):
    """Information about a facility."""
    facility_id: str
    facility_name: str
    distance_km: float
    duration_min: Optional[float] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class CandidateInfo(BaseModel):
    """Information about a candidate facility with both distance types."""
    facility_id: str
    facility_name: str
    euclidean_rank: int
    route_rank: int
    euclidean_distance_km: float
    route_distance_km: float
    route_duration_min: float
    route_connected: bool


class PointAnalysisResponse(BaseModel):
    """Response with point analysis comparing Euclidean vs Route distance."""
    location: Tuple[float, float]  # (lat, lng)
    euclidean_nearest: FacilityInfo
    route_nearest: FacilityInfo
    distortion_ratio: float
    differs: bool  # True if Euclidean and Route nearest are different
    all_candidates: List[CandidateInfo]
    routing_available: bool


def euclidean_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate approximate Euclidean distance in km."""
    lat_km = abs(lat2 - lat1) * 111.0
    lng_km = abs(lng2 - lng1) * 111.0 * 0.866  # cos(25°) ≈ 0.866 for India
    return (lat_km ** 2 + lng_km ** 2) ** 0.5


@router.post("/analyze-point", response_model=PointAnalysisResponse)
async def analyze_point(request: PointAnalysisRequest):
    """
    Analyze a specific location for nearest facilities by both Euclidean and route distance.
    
    This is the primary endpoint for the hybrid approach:
    - Fast Euclidean Voronoi for overview
    - On-demand route queries for clicked points
    
    Returns comparison between Euclidean nearest and Route nearest facilities.
    Response time: ~50-100ms with OSRM running.
    """
    dcel = get_current_dcel()
    
    if dcel is None or not dcel.faces:
        raise HTTPException(
            status_code=400,
            detail="No facilities loaded. Upload facilities and compute Voronoi first."
        )
    
    routing = get_routing_service()
    
    # Check if routing is available
    routing_available = False
    try:
        health = routing.health_check_sync()
        routing_available = health.get("status") == "healthy"
    except Exception:
        pass
    
    # Get k nearest facilities by Euclidean distance
    candidates = dcel.k_nearest_neighbors(request.lat, request.lng, k=request.k_candidates)
    
    if not candidates:
        raise HTTPException(
            status_code=404,
            detail="No facilities found in DCEL"
        )
    
    # Build candidate info with Euclidean distances
    candidate_infos: List[CandidateInfo] = []
    destinations: List[Tuple[float, float]] = []
    
    for i, face in enumerate(candidates):
        centroid = dcel.get_facility_centroid(face.facility_id)
        if centroid:
            dest_lat, dest_lng = centroid
            euc_dist = euclidean_distance_km(request.lat, request.lng, dest_lat, dest_lng)
            
            destinations.append(centroid)
            candidate_infos.append(CandidateInfo(
                facility_id=face.facility_id,
                facility_name=face.facility_name,
                euclidean_rank=i + 1,
                route_rank=0,  # Will be updated
                euclidean_distance_km=round(euc_dist, 2),
                route_distance_km=float('inf'),
                route_duration_min=float('inf'),
                route_connected=False
            ))
    
    # Query route distances if routing is available
    if routing_available and destinations:
        try:
            route_results = routing.batch_distance_sync(
                request.lat, request.lng, destinations
            )
            
            # Update candidate infos with route distances
            for i, result in enumerate(route_results):
                if i < len(candidate_infos):
                    candidate_infos[i].route_distance_km = round(result.distance_km, 2) if result.connected else float('inf')
                    candidate_infos[i].route_duration_min = round(result.duration_min, 1) if result.connected else float('inf')
                    candidate_infos[i].route_connected = result.connected
            
            # Assign route ranks
            connected = [(i, c.route_distance_km) for i, c in enumerate(candidate_infos) if c.route_connected]
            connected.sort(key=lambda x: x[1])
            for rank, (idx, _) in enumerate(connected):
                candidate_infos[idx].route_rank = rank + 1
            
            # Assign disconnected to last ranks
            disconnected_rank = len(connected) + 1
            for c in candidate_infos:
                if not c.route_connected:
                    c.route_rank = disconnected_rank
                    disconnected_rank += 1
                    
        except Exception as e:
            # Routing failed, mark as unavailable
            routing_available = False
    
    # If routing not available, set proper ranks but don't fake data
    if not routing_available:
        for i, c in enumerate(candidate_infos):
            c.route_rank = i + 1  # Rank by Euclidean order for display
    
    # Determine Euclidean nearest
    euclidean_nearest = candidates[0]
    euc_centroid = dcel.get_facility_centroid(euclidean_nearest.facility_id)
    euc_dist = euclidean_distance_km(
        request.lat, request.lng,
        euc_centroid[0] if euc_centroid else 0,
        euc_centroid[1] if euc_centroid else 0
    ) if euc_centroid else 0
    
    # Determine Route nearest
    route_nearest_info = min(
        [c for c in candidate_infos if c.route_connected],
        key=lambda c: c.route_distance_km,
        default=None
    )
    
    if route_nearest_info:
        route_nearest = FacilityInfo(
            facility_id=route_nearest_info.facility_id,
            facility_name=route_nearest_info.facility_name,
            distance_km=route_nearest_info.route_distance_km,
            duration_min=route_nearest_info.route_duration_min
        )
        distortion_ratio = (
            route_nearest_info.route_distance_km / route_nearest_info.euclidean_distance_km
            if route_nearest_info.euclidean_distance_km > 0 else 1.0
        )
        differs = route_nearest_info.facility_id != euclidean_nearest.facility_id
    else:
        # No route available, use Euclidean
        route_nearest = FacilityInfo(
            facility_id=euclidean_nearest.facility_id,
            facility_name=euclidean_nearest.facility_name,
            distance_km=euc_dist,
            duration_min=None
        )
        distortion_ratio = 1.0
        differs = False
    
    # Sanitize candidates - replace inf with large values for JSON serialization
    sanitized_candidates = []
    for c in candidate_infos:
        sanitized_candidates.append(CandidateInfo(
            facility_id=c.facility_id,
            facility_name=c.facility_name,
            euclidean_rank=c.euclidean_rank,
            route_rank=c.route_rank if c.route_rank > 0 else len(candidate_infos),
            euclidean_distance_km=c.euclidean_distance_km,
            route_distance_km=c.route_distance_km if c.route_connected else 999.0,
            route_duration_min=c.route_duration_min if c.route_connected else 999.0,
            route_connected=c.route_connected
        ))
    
    return PointAnalysisResponse(
        location=(request.lat, request.lng),
        euclidean_nearest=FacilityInfo(
            facility_id=euclidean_nearest.facility_id,
            facility_name=euclidean_nearest.facility_name,
            distance_km=round(euc_dist, 2),
            lat=euc_centroid[0] if euc_centroid else None,
            lng=euc_centroid[1] if euc_centroid else None
        ),
        route_nearest=route_nearest,
        distortion_ratio=round(distortion_ratio, 2),
        differs=differs,
        all_candidates=sanitized_candidates,
        routing_available=routing_available
    )


@router.get("/health")
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


class RoutingConfigUpdate(BaseModel):
    """Request to update routing configuration."""
    base_url: str = "http://localhost:5000"
    profile: str = "car"
    timeout_seconds: float = 10.0


@router.post("/config")
async def update_routing_config(config: RoutingConfigUpdate):
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
