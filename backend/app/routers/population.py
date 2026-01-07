from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json

from app.services.population_calc import PopulationService

router = APIRouter()

class Feature(BaseModel):
    type: str
    properties: Dict[str, Any]
    geometry: Dict[str, Any]
    id: Optional[str] = None

class WeightedPopulationRequest(BaseModel):
    """Request with Voronoi features"""
    voronoi_features: List[Feature]

class WeightedPopulationResponse(BaseModel):
    """Response with population data"""
    results: List[Dict[str, Any]]

@router.post("/weighted", response_model=WeightedPopulationResponse)
async def calculate_weighted_population(request: WeightedPopulationRequest):
    """
    Calculate weighted population for provided Voronoi polygons from the district data.
    """
    try:
        service = PopulationService()
        # Convert Pydantic models to dicts
        features_dict = [f.model_dump() for f in request.voronoi_features]
        
        results = service.calculate_weighted_population(features_dict)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/districts")
async def get_district_boundaries():
    """
    Get simplified district boundaries for map visualization.
    """
    try:
        service = PopulationService()
        if service._districts_gdf is None:
            service._load_data()
            
        if service._districts_gdf is None:
            raise HTTPException(status_code=404, detail="District data not found")
            
        # Convert to GeoJSON structure
        # We can use geopandas to_json() but let's be careful with large responses
        # Maybe return a simplified structure or just the raw geojson string
        return json.loads(service._districts_gdf.to_json())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/states")
async def get_state_boundaries():
    """
    Get simplified state boundaries for map visualization.
    """
    import geopandas as gpd
    import os
    
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        geojson_path = os.path.join(base_dir, "data/states.geojson")
        
        if not os.path.exists(geojson_path):
            raise HTTPException(status_code=404, detail="State data not found")
        
        gdf = gpd.read_file(geojson_path)
        return json.loads(gdf.to_json())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

