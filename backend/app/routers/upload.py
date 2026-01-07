"""
CSV Upload router - handles facility CSV file uploads
"""
import io
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
import pandas as pd

router = APIRouter()


class FacilityData(BaseModel):
    """Parsed facility from CSV"""
    id: str
    name: str
    lat: float
    lng: float
    type: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None


class UploadResponse(BaseModel):
    """Response from CSV upload"""
    success: bool
    total_rows: int
    valid_facilities: int
    facilities: List[FacilityData]
    errors: List[str]


# India bounding box (approximate)
INDIA_BOUNDS = {
    "min_lat": 6.5,
    "max_lat": 37.5,
    "min_lng": 68.0,
    "max_lng": 97.5,
}


@router.post("/csv", response_model=UploadResponse)
async def upload_csv(file: UploadFile = File(...)):
    """
    Upload a CSV file with facility coordinates.
    
    Expected columns (case-insensitive):
    - name / facility_name / facility name: Facility name (required)
    - lat / latitude: Latitude (required)
    - lng / lon / longitude: Longitude (required)
    - type / facility_type / facility type: Facility type (optional)
    - state / state_name / state name: State name (optional)
    - district / district_name / district name: District name (optional)
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents), dtype=str, low_memory=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")
    
    # Normalize column names
    df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')
    
    errors = []
    facilities = []
    
    # Find required columns
    name_col = None
    lat_col = None
    lng_col = None
    
    for col in df.columns:
        if col in ['name', 'facility_name']:
            name_col = col
        elif col in ['lat', 'latitude']:
            lat_col = col
        elif col in ['lng', 'lon', 'longitude']:
            lng_col = col
    
    if not name_col:
        errors.append("Missing required column: name/facility_name")
    if not lat_col:
        errors.append("Missing required column: lat/latitude")
    if not lng_col:
        errors.append("Missing required column: lng/lon/longitude")
    
    if errors:
        return UploadResponse(
            success=False,
            total_rows=len(df),
            valid_facilities=0,
            facilities=[],
            errors=errors
        )
    
    # Find optional columns
    type_col = next((c for c in df.columns if c in ['type', 'facility_type']), None)
    state_col = next((c for c in df.columns if c in ['state', 'state_name']), None)
    district_col = next((c for c in df.columns if c in ['district', 'district_name']), None)
    
    # Parse rows
    for idx, row in df.iterrows():
        try:
            lat = float(row[lat_col])
            lng = float(row[lng_col])
            
            # Validate coordinates
            if not (-90 <= lat <= 90):
                errors.append(f"Row {idx + 2}: Invalid latitude {lat}")
                continue
            if not (-180 <= lng <= 180):
                errors.append(f"Row {idx + 2}: Invalid longitude {lng}")
                continue
            
            # Optional: warn if outside India bounds
            if not (INDIA_BOUNDS["min_lat"] <= lat <= INDIA_BOUNDS["max_lat"] and
                    INDIA_BOUNDS["min_lng"] <= lng <= INDIA_BOUNDS["max_lng"]):
                errors.append(f"Row {idx + 2}: Coordinates outside India bounds (warning)")
            
            facility = FacilityData(
                id=str(idx),
                name=str(row[name_col]) if pd.notna(row[name_col]) else f"Facility_{idx}",
                lat=lat,
                lng=lng,
                type=str(row[type_col]) if type_col and pd.notna(row.get(type_col)) else None,
                state=str(row[state_col]) if state_col and pd.notna(row.get(state_col)) else None,
                district=str(row[district_col]) if district_col and pd.notna(row.get(district_col)) else None,
            )
            facilities.append(facility)
            
        except (ValueError, TypeError) as e:
            errors.append(f"Row {idx + 2}: {str(e)}")
    
    return UploadResponse(
        success=len(facilities) > 0,
        total_rows=len(df),
        valid_facilities=len(facilities),
        facilities=facilities,
        errors=errors[:50]  # Limit errors to first 50
    )
