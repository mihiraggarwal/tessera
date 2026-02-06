"""
CSV Upload router - handles facility CSV file uploads
"""
import io
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
import pandas as pd

router = APIRouter()

# Path to data folder (from backend/app/routers/ -> tessera/data/)
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
RAW_DATA_DIR = DATA_DIR / "raw"


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


@router.post("/raw-csv")
async def upload_raw_csv(file: UploadFile = File(...)):
    """
    Upload a CSV file without validation, storing it in the raw folder.
    Returns the file path for further analysis.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
        
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    file_path = RAW_DATA_DIR / file.filename
    
    try:
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        
    return {
        "success": True,
        "filename": file.filename,
        "path": str(file_path)
    }


@router.get("/sample-data", response_model=UploadResponse)
async def get_sample_data():
    """
    Load sample test.csv from the data folder.
    """
    sample_file = DATA_DIR / "test.csv"
    
    if not sample_file.exists():
        raise HTTPException(status_code=404, detail="Sample data file not found")
    
    try:
        df = pd.read_csv(sample_file, dtype=str, low_memory=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse sample data: {str(e)}")
    
    # Normalize column names
    df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')
    
    errors = []
    facilities = []
    
    # Map columns to expected names
    name_col = next((c for c in df.columns if c in ['name', 'facility_name']), None)
    lat_col = next((c for c in df.columns if c in ['lat', 'latitude']), None)
    lng_col = next((c for c in df.columns if c in ['lng', 'lon', 'longitude']), None)
    type_col = next((c for c in df.columns if c in ['type', 'facility_type']), None)
    state_col = next((c for c in df.columns if c in ['state', 'state_name']), None)
    district_col = next((c for c in df.columns if c in ['district', 'district_name']), None)
    
    if not all([name_col, lat_col, lng_col]):
        raise HTTPException(status_code=500, detail="Sample data missing required columns")
    
    # Parse rows
    for idx, row in df.iterrows():
        try:
            lat = float(row[lat_col])
            lng = float(row[lng_col])
            
            if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                continue
            
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
            
        except (ValueError, TypeError):
            continue
    
    return UploadResponse(
        success=len(facilities) > 0,
        total_rows=len(df),
        valid_facilities=len(facilities),
        facilities=facilities,
        errors=[]
    )


@router.get("/available-files")
async def get_available_files():
    """
    List available CSV files in the data folder, including public facilities.
    Returns files grouped by category.
    """
    result = {
        "user_data": [],
        "public_facilities": []
    }
    
    # User data files (excluding test.csv which is sample data)
    if DATA_DIR.exists():
        for f in DATA_DIR.glob("*.csv"):
            if f.name != "test.csv":
                result["user_data"].append(f.name)
    
    # Public facilities from data/public folder
    public_dir = DATA_DIR / "public"
    if public_dir.exists():
        for f in public_dir.glob("*.csv"):
            result["public_facilities"].append(f.name)
    
    result["user_data"].sort()
    result["public_facilities"].sort()
    
    return result


@router.get("/load-file/{filename}", response_model=UploadResponse)
async def load_file(filename: str):
    """
    Load a specific CSV file from the data folder.
    """
    # Security: prevent directory traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    file_path = DATA_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found")
    
    try:
        df = pd.read_csv(file_path, dtype=str, low_memory=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse file: {str(e)}")
    
    # Normalize column names
    df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')
    
    facilities = []
    
    # Map columns to expected names
    name_col = next((c for c in df.columns if c in ['name', 'facility_name']), None)
    lat_col = next((c for c in df.columns if c in ['lat', 'latitude']), None)
    lng_col = next((c for c in df.columns if c in ['lng', 'lon', 'longitude']), None)
    type_col = next((c for c in df.columns if c in ['type', 'facility_type']), None)
    state_col = next((c for c in df.columns if c in ['state', 'state_name']), None)
    district_col = next((c for c in df.columns if c in ['district', 'district_name']), None)
    
    if not all([name_col, lat_col, lng_col]):
        raise HTTPException(status_code=400, detail="File missing required columns (name, latitude, longitude)")
    
    # Parse rows
    for idx, row in df.iterrows():
        try:
            lat = float(row[lat_col])
            lng = float(row[lng_col])
            
            if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                continue
            
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
            
        except (ValueError, TypeError):
            continue
    
    return UploadResponse(
        success=len(facilities) > 0,
        total_rows=len(df),
        valid_facilities=len(facilities),
        facilities=facilities,
        errors=[]
    )


@router.get("/load-public-file/{filename}", response_model=UploadResponse)
async def load_public_file(filename: str):
    """
    Load a public facility CSV file from the data/public folder.
    """
    # Security: prevent directory traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    public_dir = DATA_DIR / "public"
    file_path = public_dir / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found")
    
    try:
        df = pd.read_csv(file_path, dtype=str, low_memory=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse file: {str(e)}")
    
    # Normalize column names
    df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')
    
    facilities = []
    
    # Map columns to expected names
    name_col = next((c for c in df.columns if c in ['name', 'facility_name']), None)
    lat_col = next((c for c in df.columns if c in ['lat', 'latitude']), None)
    lng_col = next((c for c in df.columns if c in ['lng', 'lon', 'longitude']), None)
    type_col = next((c for c in df.columns if c in ['type', 'facility_type']), None)
    state_col = next((c for c in df.columns if c in ['state', 'state_name']), None)
    district_col = next((c for c in df.columns if c in ['district', 'district_name']), None)
    
    if not all([name_col, lat_col, lng_col]):
        raise HTTPException(status_code=500, detail="File missing required columns (name, lat, lng)")
    
    for idx, row in df.iterrows():
        try:
            lat = float(row[lat_col])
            lng = float(row[lng_col])
            
            # Skip invalid coordinates
            if not (INDIA_BOUNDS["min_lat"] <= lat <= INDIA_BOUNDS["max_lat"] and 
                    INDIA_BOUNDS["min_lng"] <= lng <= INDIA_BOUNDS["max_lng"]):
                continue
            
            facility = FacilityData(
                id=f"public_{idx}",
                name=str(row[name_col]) if pd.notna(row[name_col]) else "Unknown",
                lat=lat,
                lng=lng,
                type=str(row[type_col]) if type_col and pd.notna(row.get(type_col)) else None,
                state=str(row[state_col]) if state_col and pd.notna(row.get(state_col)) else None,
                district=str(row[district_col]) if district_col and pd.notna(row.get(district_col)) else None,
            )
            facilities.append(facility)
            
        except (ValueError, TypeError):
            continue
    
    return UploadResponse(
        success=len(facilities) > 0,
        total_rows=len(df),
        valid_facilities=len(facilities),
        facilities=facilities,
        errors=[]
    )


@router.get("/bus-stops/{state_name}", response_model=UploadResponse)
async def get_bus_stops_for_state(state_name: str):
    """
    Dynamically fetch bus stops for a specific state from OpenStreetMap.
    This is only available when filtering by state to avoid overwhelming data.
    """
    import requests
    
    # Validate state name
    if not state_name or len(state_name) < 2:
        raise HTTPException(status_code=400, detail="Invalid state name")
    
    # Query Overpass API for bus stops in the state
    query = f"""
    [out:json][timeout:60];
    area["name"="{state_name}"]["admin_level"="4"]->.state;
    (
      node["highway"="bus_stop"](area.state);
    );
    out body;
    """
    
    try:
        response = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            timeout=90
        )
        response.raise_for_status()
        result = response.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Failed to fetch bus stops: {str(e)}")
    
    facilities = []
    for idx, element in enumerate(result.get("elements", [])):
        if element.get("type") == "node":
            tags = element.get("tags", {})
            lat, lng = element["lat"], element["lon"]
            
            # Validate coordinates
            if not (INDIA_BOUNDS["min_lat"] <= lat <= INDIA_BOUNDS["max_lat"] and 
                    INDIA_BOUNDS["min_lng"] <= lng <= INDIA_BOUNDS["max_lng"]):
                continue
            
            facility = FacilityData(
                id=f"bus_{idx}",
                name=tags.get("name", tags.get("name:en", "Bus Stop")),
                lat=lat,
                lng=lng,
                type="bus_stop",
                state=state_name,
                district=tags.get("addr:district", None),
            )
            facilities.append(facility)
    
    return UploadResponse(
        success=len(facilities) > 0,
        total_rows=len(result.get("elements", [])),
        valid_facilities=len(facilities),
        facilities=facilities,
        errors=[]
    )


