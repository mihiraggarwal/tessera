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
    List available CSV files in the data folder (excluding test.csv which is sample data).
    """
    if not DATA_DIR.exists():
        return []
    
    csv_files = []
    for f in DATA_DIR.glob("*.csv"):
        if f.name != "test.csv":  # Exclude sample data file
            csv_files.append(f.name)
    
    return sorted(csv_files)


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


# ============================================
# PDF Extraction Endpoints (Azure Document Intelligence)
# ============================================

class ExtractedTable(BaseModel):
    """Extracted table from PDF"""
    row_count: int
    column_count: int
    headers: List[str]
    rows: List[dict]


class PDFExtractionResponse(BaseModel):
    """Response from PDF extraction"""
    success: bool
    page_count: int
    table_count: int
    tables: List[ExtractedTable]
    mapped_data: List[dict]  # Data mapped to population schema
    errors: List[str]


@router.get("/pdf/status")
async def pdf_extraction_status():
    """Check if PDF extraction (Document Intelligence) is configured."""
    from app.services.document_intelligence import document_service
    return {
        "configured": document_service.is_configured,
        "message": "Azure Document Intelligence is configured" if document_service.is_configured 
                   else "Set AZURE_DOC_INTEL_ENDPOINT and AZURE_DOC_INTEL_KEY in .env"
    }


@router.post("/pdf", response_model=PDFExtractionResponse)
async def extract_pdf_tables(file: UploadFile = File(...)):
    """
    Extract tables from a PDF file using Azure Document Intelligence.
    
    The extracted tables are automatically mapped to population schema if possible.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    from app.services.document_intelligence import document_service
    
    if not document_service.is_configured:
        raise HTTPException(
            status_code=503, 
            detail="Azure Document Intelligence is not configured. Set AZURE_DOC_INTEL_ENDPOINT and AZURE_DOC_INTEL_KEY."
        )
    
    try:
        # Read the PDF file
        pdf_bytes = await file.read()
        
        # Extract tables using Document Intelligence
        result = document_service.extract_tables_from_pdf(pdf_bytes)
        
        # Map first table to population schema (if available)
        mapped_data = []
        if result["tables"]:
            mapped_data = document_service.map_to_population_schema(result["tables"][0])
        
        # Convert to response format
        tables = [
            ExtractedTable(
                row_count=t["row_count"],
                column_count=t["column_count"],
                headers=t["headers"],
                rows=t["rows"]
            )
            for t in result["tables"]
        ]
        
        return PDFExtractionResponse(
            success=True,
            page_count=result["page_count"],
            table_count=result["table_count"],
            tables=tables,
            mapped_data=mapped_data,
            errors=[]
        )
        
    except Exception as e:
        return PDFExtractionResponse(
            success=False,
            page_count=0,
            table_count=0,
            tables=[],
            mapped_data=[],
            errors=[str(e)]
        )


