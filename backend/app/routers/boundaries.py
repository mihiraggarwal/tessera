"""
Boundaries router - serves administrative boundary GeoJSON data
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import geopandas as gpd
from shapely.ops import unary_union
from shapely.geometry import mapping
import os

router = APIRouter()


class BoundaryResponse(BaseModel):
    """GeoJSON boundary response"""
    type: str = "FeatureCollection"
    features: list


# Cached India boundary (loaded from shapefile)
_india_boundary_geojson = None


def _load_india_boundary():
    """Load India boundary from shapefile and return as GeoJSON Feature."""
    global _india_boundary_geojson
    
    if _india_boundary_geojson is not None:
        return _india_boundary_geojson
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    shapefile_path = os.path.join(base_dir, "data", "boundaries", "india_st.shp")
    
    if not os.path.exists(shapefile_path):
        # Fall back to a simple bounding box if shapefile not found
        return {
            "type": "Feature",
            "properties": {"name": "India", "admin_level": "0"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [68.7, 6.5], [97.4, 6.5], [97.4, 35.5], [68.7, 35.5], [68.7, 6.5]
                ]]
            }
        }
    
    try:
        # Load the shapefile
        gdf = gpd.read_file(shapefile_path)
        
        # Ensure CRS is WGS84
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        elif gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs("EPSG:4326")
        
        # Dissolve all state geometries into a single unified boundary
        unified_boundary = unary_union(gdf.geometry)
        
        # Handle invalid geometries
        if not unified_boundary.is_valid:
            unified_boundary = unified_boundary.buffer(0)
        
        _india_boundary_geojson = {
            "type": "Feature",
            "properties": {"name": "India", "admin_level": "0"},
            "geometry": mapping(unified_boundary)
        }
        
        return _india_boundary_geojson
        
    except Exception as e:
        print(f"Error loading India shapefile: {e}")
        # Fall back to simple bounding box
        return {
            "type": "Feature",
            "properties": {"name": "India", "admin_level": "0"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [68.7, 6.5], [97.4, 6.5], [97.4, 35.5], [68.7, 35.5], [68.7, 6.5]
                ]]
            }
        }


@router.get("/india")
async def get_india_boundary():
    """
    Get simplified India boundary for map display.
    Returns a GeoJSON Feature with India's boundary.
    """
    return _load_india_boundary()


@router.get("/{level}")
async def get_boundaries(level: str, state: Optional[str] = None):
    """
    Get administrative boundaries at specified level.
    
    Levels:
    - state: State boundaries
    - district: District boundaries
    
    Note: Full boundary data requires additional GeoJSON files.
    """
    if level not in ["state", "district"]:
        raise HTTPException(
            status_code=400,
            detail="Level must be 'state' or 'district'"
        )
    
    # Placeholder response - in production, load from GeoJSON files
    return BoundaryResponse(
        type="FeatureCollection",
        features=[
            {
                "type": "Feature",
                "properties": {
                    "name": f"Sample {level.title()}",
                    "level": level,
                    "message": "Full boundary data not yet loaded. Add GeoJSON files to backend/app/data/boundaries/"
                },
                "geometry": None
            }
        ]
    )
