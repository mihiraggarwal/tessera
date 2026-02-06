"""
Pre-computation Service - Caches Voronoi diagrams for fast analysis.
"""
import os
import json
import pickle
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import pandas as pd

from app.services.voronoi_engine import VoronoiEngine
from app.services.dataset_registry import get_datasets_for_type


class PrecomputeService:
    """Service for pre-computing and caching Voronoi diagrams."""
    
    # Navigate: precompute_service.py -> services -> app -> backend -> tessera/data/public
    CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache", "voronoi")
    DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "data", "public")
    
    def __init__(self):
        os.makedirs(self.CACHE_DIR, exist_ok=True)
        self._voronoi_engine = VoronoiEngine()
    
    def load_dataset(self, dataset_name: str, state_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Load facilities from a dataset CSV file."""
        csv_path = os.path.join(self.DATA_DIR, f"{dataset_name}.csv")
        
        if not os.path.exists(csv_path):
            print(f"Dataset not found: {csv_path}")
            return []
        
        try:
            df = pd.read_csv(csv_path)
            
            # Normalize column names
            df.columns = df.columns.str.lower().str.strip()
            
            # Find lat/lng columns
            lat_col = None
            lng_col = None
            for col in df.columns:
                if col in ['lat', 'latitude']:
                    lat_col = col
                elif col in ['lng', 'lon', 'longitude']:
                    lng_col = col
            
            if not lat_col or not lng_col:
                print(f"Dataset {dataset_name} missing lat/lng columns")
                return []
            
            # Filter by state if provided
            if state_filter:
                state_col = None
                for col in df.columns:
                    if col in ['state', 'stat']:
                        state_col = col
                        break
                if state_col:
                    df = df[df[state_col].str.lower() == state_filter.lower()]
            
            # Convert to list of facilities
            facilities = []
            name_col = 'name' if 'name' in df.columns else df.columns[0]
            
            for idx, row in df.iterrows():
                try:
                    lat = float(row[lat_col])
                    lng = float(row[lng_col])
                    
                    # Validate coordinates are in India
                    if not (6.5 <= lat <= 37.5 and 68.0 <= lng <= 97.5):
                        continue
                    
                    facilities.append({
                        "id": str(idx),
                        "name": str(row[name_col]) if pd.notna(row[name_col]) else f"{dataset_name}_{idx}",
                        "lat": lat,
                        "lng": lng,
                        "type": dataset_name,
                    })
                except (ValueError, TypeError):
                    continue
            
            return facilities
            
        except Exception as e:
            print(f"Error loading dataset {dataset_name}: {e}")
            return []
    
    def _get_cache_path(self, dataset_name: str, state_filter: Optional[str] = None) -> str:
        """Get cache file path for a dataset."""
        state_dir = state_filter.lower().replace(" ", "_") if state_filter else "all_india"
        cache_dir = os.path.join(self.CACHE_DIR, state_dir)
        os.makedirs(cache_dir, exist_ok=True)
        return os.path.join(cache_dir, f"{dataset_name}.json")
    
    def get_cached_voronoi(self, dataset_name: str, state_filter: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get cached Voronoi GeoJSON if available."""
        cache_path = self._get_cache_path(dataset_name, state_filter)
        
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error reading cache: {e}")
        
        return None
    
    def compute_and_cache_voronoi(
        self, 
        dataset_name: str, 
        state_filter: Optional[str] = None,
        force_recompute: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Compute Voronoi for a dataset and cache it."""
        
        # Check cache first
        if not force_recompute:
            cached = self.get_cached_voronoi(dataset_name, state_filter)
            if cached:
                return cached
        
        # Load dataset
        facilities = self.load_dataset(dataset_name, state_filter)
        if len(facilities) < 3:
            print(f"Not enough facilities in {dataset_name} (need at least 3, got {len(facilities)})")
            return None
        
        # Compute Voronoi
        try:
            coords = [(f["lng"], f["lat"]) for f in facilities]
            names = [f["name"] for f in facilities]
            facility_ids = [f["id"] for f in facilities]
            types = [f["type"] for f in facilities]
            
            geojson = self._voronoi_engine.compute_voronoi(
                coords=coords,
                names=names,
                facility_ids=facility_ids,
                types=types,
                clip_to_india=True,
                state_filter=state_filter,
            )
            
            # Add metadata
            geojson["metadata"] = {
                "dataset": dataset_name,
                "state_filter": state_filter,
                "facility_count": len(facilities),
                "computed_at": datetime.now().isoformat(),
            }
            
            # Cache the result
            cache_path = self._get_cache_path(dataset_name, state_filter)
            with open(cache_path, 'w') as f:
                json.dump(geojson, f)
            
            print(f"Computed and cached Voronoi for {dataset_name} ({len(facilities)} facilities)")
            return geojson
            
        except Exception as e:
            print(f"Error computing Voronoi for {dataset_name}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def precompute_all(
        self, 
        analysis_type: str, 
        state_filter: Optional[str] = None,
        force_recompute: bool = False
    ) -> Dict[str, bool]:
        """Pre-compute Voronois for all datasets of a given analysis type."""
        datasets = get_datasets_for_type(analysis_type)
        results = {}
        
        for dataset in datasets:
            result = self.compute_and_cache_voronoi(dataset, state_filter, force_recompute)
            results[dataset] = result is not None
        
        return results
    
    def get_facility_for_point(
        self,
        dataset_name: str,
        lat: float,
        lng: float,
        state_filter: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find the nearest facility to a point using direct distance calculation.
        Much more robust than Voronoi containment approach.
        """
        import math
        
        # Load facilities directly from dataset
        facilities = self.load_dataset(dataset_name, state_filter)
        
        if not facilities:
            return None
        
        # Find nearest facility using Haversine distance
        def haversine(lat1, lng1, lat2, lng2):
            R = 6371  # Earth's radius in km
            lat1_rad = math.radians(lat1)
            lat2_rad = math.radians(lat2)
            dlat = math.radians(lat2 - lat1)
            dlng = math.radians(lng2 - lng1)
            a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            return R * c
        
        nearest = None
        min_distance = float('inf')
        
        for facility in facilities:
            try:
                distance = haversine(lat, lng, facility["lat"], facility["lng"])
                if distance < min_distance:
                    min_distance = distance
                    nearest = facility
            except (KeyError, TypeError):
                continue
        
        if nearest:
            return {
                "name": nearest.get("name"),
                "facility_id": nearest.get("id"),
                "type": nearest.get("type"),
                "lat": nearest.get("lat"),
                "lng": nearest.get("lng"),
                "distance_km": round(min_distance, 2),
            }
        
        return None

