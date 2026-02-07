"""
Area Rating Router - API endpoints for area analysis.
"""
from typing import Literal, Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.area_rating_service import AreaRatingService
from app.services.pincode_service import PincodeService
from app.services.dataset_registry import get_datasets_for_type, EMERGENCY_DATASETS, LIVING_DATASETS

router = APIRouter()


# Request/Response Models
class AnalyzeByPincodeRequest(BaseModel):
    """Request to analyze area by pincode."""
    pincode: str = Field(..., min_length=6, max_length=6, description="6-digit Indian postal code")
    analysis_type: Literal["emergency", "living"] = Field(..., description="Type of analysis")


class AnalyzeByLocationRequest(BaseModel):
    """Request to analyze area by coordinates."""
    lat: float = Field(..., ge=6.5, le=37.5, description="Latitude (India bounds)")
    lng: float = Field(..., ge=68.0, le=97.5, description="Longitude (India bounds)")
    analysis_type: Literal["emergency", "living"] = Field(..., description="Type of analysis")


class FacilityBreakdown(BaseModel):
    """Breakdown for a single facility type."""
    score: int
    distance_km: Optional[float]
    facility_name: Optional[str]
    weight: float


class NearestFacility(BaseModel):
    """Nearest facility info."""
    type: str
    name: Optional[str]
    distance_km: float
    lat: Optional[float]
    lng: Optional[float]


class Recommendation(BaseModel):
    """Analysis recommendation."""
    type: str
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    message: str


class PincodeInfoResponse(BaseModel):
    """Pincode information response."""
    pincode: str
    place_name: str
    state: str
    district: str
    lat: float
    lng: float


class AreaRatingResponse(BaseModel):
    """Area rating analysis response."""
    overall_score: float
    grade: Literal["A", "B", "C", "D", "F"]
    analysis_type: str
    location: dict
    breakdown: dict
    nearest_facilities: List[dict]
    recommendations: List[dict]
    pincode_info: Optional[dict] = None


class PincodeSearchResult(BaseModel):
    """Pincode search result."""
    pincode: str
    place_name: str
    state: str
    district: str


# Endpoints
@router.post("/analyze", response_model=AreaRatingResponse)
async def analyze_by_pincode(request: AnalyzeByPincodeRequest):
    """
    Analyze an area by pincode for emergency or living conditions.
    Returns an overall score (0-100), grade (A-F), and detailed breakdown.
    """
    try:
        service = AreaRatingService()
        result = service.analyze_by_pincode(request.pincode, request.analysis_type)
        return AreaRatingResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-location", response_model=AreaRatingResponse)
async def analyze_by_location(request: AnalyzeByLocationRequest):
    """
    Analyze an area by coordinates for emergency or living conditions.
    Use this when user shares their location via browser geolocation.
    """
    try:
        service = AreaRatingService()
        result = service.analyze_by_location(request.lat, request.lng, request.analysis_type)
        return AreaRatingResponse(**result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pincode/{pincode}", response_model=PincodeInfoResponse)
async def get_pincode_info(pincode: str):
    """Get information about a pincode."""
    service = PincodeService()
    info = service.get_pincode(pincode)
    
    if not info:
        raise HTTPException(status_code=404, detail=f"Pincode not found: {pincode}")
    
    return PincodeInfoResponse(**info.to_dict())


@router.get("/pincode/search/{query}")
async def search_pincodes(query: str, limit: int = 10):
    """Search pincodes by partial match."""
    service = PincodeService()
    results = service.search_pincodes(query, limit)
    
    return {
        "results": [
            {
                "pincode": r.pincode,
                "place_name": r.place_name,
                "state": r.state,
                "district": r.district,
            }
            for r in results
        ]
    }


class ReverseGeocodeRequest(BaseModel):
    """Request for reverse geocoding."""
    lat: float = Field(..., ge=6.5, le=37.5, description="Latitude (India bounds)")
    lng: float = Field(..., ge=68.0, le=97.5, description="Longitude (India bounds)")


@router.post("/reverse-geocode")
async def reverse_geocode(request: ReverseGeocodeRequest):
    """Find the nearest pincode for given coordinates."""
    service = PincodeService()
    info = service.reverse_geocode(request.lat, request.lng)
    
    if not info:
        raise HTTPException(status_code=404, detail="Could not find nearby pincode")
    
    return PincodeInfoResponse(**info.to_dict())



@router.get("/datasets/{analysis_type}")
async def get_datasets(analysis_type: Literal["emergency", "living"]):
    """Get list of datasets used for a given analysis type."""
    try:
        datasets = get_datasets_for_type(analysis_type)
        return {
            "analysis_type": analysis_type,
            "datasets": datasets,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/analysis-types")
async def get_analysis_types():
    """Get available analysis types and their descriptions."""
    return {
        "types": [
            {
                "id": "emergency",
                "name": "Emergency Response",
                "description": "Rate area based on emergency facility coverage (hospitals, fire stations, police, blood banks, transport)",
                "datasets": EMERGENCY_DATASETS,
            },
            {
                "id": "living",
                "name": "Living Conditions",
                "description": "Rate area based on amenities for daily living (schools, parks, banks, transport, etc.)",
                "datasets": LIVING_DATASETS,
            }
        ]
    }
@router.get("/heatmap/{analysis_type}")
async def get_heatmap(analysis_type: Literal["emergency", "living"]):
    """
    Get precomputed heatmap data for all pincodes.
    Returns a list of {lat, lng, weight} objects.
    """
    try:
        service = AreaRatingService()
        result = service.get_heatmap_data(analysis_type)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
