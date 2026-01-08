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


# Cache for states GeoDataFrame
_states_gdf = None


def _load_states_gdf():
    """Load states GeoDataFrame from shapefile."""
    global _states_gdf
    
    if _states_gdf is not None:
        return _states_gdf
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    geojson_path = os.path.join(base_dir, "data", "states.geojson")
    
    if not os.path.exists(geojson_path):
        return None
    
    try:
        _states_gdf = gpd.read_file(geojson_path)
        if _states_gdf.crs is None:
            _states_gdf = _states_gdf.set_crs("EPSG:4326")
        elif _states_gdf.crs.to_epsg() != 4326:
            _states_gdf = _states_gdf.to_crs("EPSG:4326")
        return _states_gdf
    except Exception as e:
        print(f"Error loading states GeoJSON: {e}")
        return None


@router.get("/states/list")
async def get_states_list():
    """
    Return list of available state names.
    """
    gdf = _load_states_gdf()
    
    if gdf is None:
        raise HTTPException(status_code=404, detail="States data not found")
    
    # Get unique state names, sorted alphabetically
    states = sorted(gdf['state'].dropna().unique().tolist())
    return states


@router.get("/states/{state_name}")
async def get_state_boundary(state_name: str):
    """
    Return GeoJSON Feature for a specific state.
    """
    gdf = _load_states_gdf()
    
    if gdf is None:
        raise HTTPException(status_code=404, detail="States data not found")
    
    # Find the state (case-insensitive match)
    state_gdf = gdf[gdf['state'].str.lower() == state_name.lower()]
    
    if len(state_gdf) == 0:
        raise HTTPException(status_code=404, detail=f"State '{state_name}' not found")
    
    # Return as GeoJSON Feature
    state_row = state_gdf.iloc[0]
    return {
        "type": "Feature",
        "properties": {"name": state_row['state']},
        "geometry": mapping(state_row.geometry)
    }


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
