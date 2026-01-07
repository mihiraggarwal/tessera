"""
Boundaries router - serves administrative boundary GeoJSON data
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class BoundaryResponse(BaseModel):
    """GeoJSON boundary response"""
    type: str = "FeatureCollection"
    features: list


# Simplified India boundary (approximate polygon following coastline)
INDIA_BOUNDARY_SIMPLE = {
    "type": "Feature",
    "properties": {"name": "India", "admin_level": "0"},
    "geometry": {
        "type": "Polygon",
        "coordinates": [[
            [68.2, 23.6],   # Gujarat coast (Kutch)
            [68.9, 22.2],   # Gujarat
            [70.0, 20.7],   # Gujarat south
            [72.6, 19.0],   # Mumbai coast
            [73.8, 15.6],   # Goa
            [74.8, 12.8],   # Karnataka coast
            [75.2, 11.7],   # Kerala north
            [76.5, 8.3],    # Kerala south tip
            [77.5, 8.1],    # Cape Comorin
            [78.1, 8.3],    # Tamil Nadu south
            [79.8, 10.3],   # Tamil Nadu coast
            [80.2, 13.1],   # Chennai
            [81.5, 15.9],   # Andhra coast
            [83.3, 18.0],   # Odisha coast
            [86.0, 20.0],   # West Bengal coast
            [88.0, 21.5],   # Kolkata region
            [89.0, 22.0],   # Bangladesh border start
            [88.9, 24.3],   # Bangladesh border
            [88.2, 26.3],   # West Bengal north
            [89.8, 28.0],   # Sikkim
            [92.0, 27.8],   # Arunachal Pradesh
            [97.0, 28.5],   # NE corner
            [96.2, 27.0],   # Arunachal
            [93.3, 24.0],   # Manipur/Mizoram
            [91.5, 21.9],   # Myanmar border
            [88.5, 21.5],   # Back to West Bengal
            [88.0, 22.2],   # Kolkata again
            [86.5, 21.3],   # Odisha
            [85.5, 21.9],   # Jharkhand
            [82.8, 25.4],   # Bihar
            [80.0, 28.5],   # UP
            [77.5, 30.5],   # Uttarakhand
            [76.0, 32.5],   # HP
            [74.5, 34.8],   # J&K
            [73.9, 36.5],   # Northern tip
            [74.0, 34.5],   # Back down
            [71.0, 30.0],   # Punjab
            [70.5, 27.5],   # Rajasthan
            [69.5, 25.0],   # Gujarat north
            [68.2, 23.6],   # Close polygon
        ]]
    }
}


@router.get("/india")
async def get_india_boundary():
    """
    Get simplified India boundary for map display.
    Returns a GeoJSON Feature with India's boundary.
    """
    return INDIA_BOUNDARY_SIMPLE


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
