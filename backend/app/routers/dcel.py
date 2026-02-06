"""
DCEL router - API endpoints for DCEL spatial queries.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.dcel import get_current_dcel

router = APIRouter()


class PointQueryRequest(BaseModel):
    """Request to query which facility serves a location."""
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class PointQueryResponse(BaseModel):
    """Response with facility info for a point query."""
    found: bool
    facility_id: Optional[str] = None
    facility_name: Optional[str] = None
    population: Optional[int] = None
    area_km2: Optional[float] = None
    properties: Optional[dict] = None


class RangeQueryRequest(BaseModel):
    """Request to query facilities in a bounding box."""
    min_lat: float = Field(..., ge=-90, le=90)
    min_lng: float = Field(..., ge=-180, le=180)
    max_lat: float = Field(..., ge=-90, le=90)
    max_lng: float = Field(..., ge=-180, le=180)


class TopFacilitiesRequest(BaseModel):
    """Request for top facilities by population."""
    top_n: int = Field(default=10, ge=1, le=100)
    state: Optional[str] = None


@router.post("/query-point", response_model=PointQueryResponse)
async def query_point(request: PointQueryRequest):
    """
    Find which facility serves a given location.
    
    Returns the facility whose Voronoi cell contains the point.
    """
    dcel = get_current_dcel()
    
    if dcel is None:
        raise HTTPException(
            status_code=400,
            detail="No Voronoi diagram has been computed yet. Please compute a Voronoi diagram first."
        )
    
    face = dcel.point_query(request.lat, request.lng)
    
    if face is None:
        return PointQueryResponse(found=False)
    
    props = face.properties or {}
    return PointQueryResponse(
        found=True,
        facility_id=face.facility_id,
        facility_name=face.facility_name,
        population=props.get('population'),
        area_km2=props.get('area_sq_km'),
        properties=props
    )


@router.post("/range-query")
async def range_query(request: RangeQueryRequest):
    """
    Find all facilities whose Voronoi cells intersect a bounding box.
    """
    dcel = get_current_dcel()
    
    if dcel is None:
        raise HTTPException(
            status_code=400,
            detail="No Voronoi diagram has been computed yet."
        )
    
    faces = dcel.range_query(
        request.min_lat, request.min_lng,
        request.max_lat, request.max_lng
    )
    
    return {
        "count": len(faces),
        "facilities": [
            {
                "facility_id": face.facility_id,
                "facility_name": face.facility_name,
                "population": face.properties.get('population') if face.properties else None,
                "area_km2": face.properties.get('area_sq_km') if face.properties else None
            }
            for face in faces
        ]
    }


@router.post("/top-by-population")
async def get_top_by_population(request: TopFacilitiesRequest):
    """
    Get facilities ranked by population served.
    """
    dcel = get_current_dcel()
    
    if dcel is None:
        raise HTTPException(
            status_code=400,
            detail="No Voronoi diagram has been computed yet."
        )
    
    facilities = dcel.get_facilities_by_population(
        top_n=request.top_n,
        state=request.state
    )
    
    return {
        "count": len(facilities),
        "facilities": facilities
    }


@router.get("/adjacent/{facility_id}")
async def get_adjacent_facilities(facility_id: str):
    """
    Find facilities adjacent to a given facility.
    """
    dcel = get_current_dcel()
    
    if dcel is None:
        raise HTTPException(
            status_code=400,
            detail="No Voronoi diagram has been computed yet."
        )
    
    face = dcel.get_face_by_facility_id(facility_id)
    if face is None:
        raise HTTPException(
            status_code=404,
            detail=f"Facility '{facility_id}' not found"
        )
    
    adjacent_ids = dcel.get_adjacent_facilities(facility_id)
    
    adjacent_info = []
    for adj_id in adjacent_ids:
        adj_face = dcel.get_face_by_facility_id(adj_id)
        if adj_face:
            adjacent_info.append({
                "facility_id": adj_face.facility_id,
                "facility_name": adj_face.facility_name
            })
    
    return {
        "facility_id": facility_id,
        "facility_name": face.facility_name,
        "adjacent_count": len(adjacent_info),
        "adjacent_facilities": adjacent_info
    }


@router.get("/summary")
async def get_dcel_summary():
    """
    Get summary of the current DCEL structure.
    """
    dcel = get_current_dcel()
    
    if dcel is None:
        return {
            "available": False,
            "message": "No Voronoi diagram has been computed yet."
        }
    
    return {
        "available": True,
        "data": dcel.to_dict()
    }
