import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import shape, Polygon
from typing import List, Dict, Any
import os

class PopulationService:
    _instance = None
    _districts_gdf = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PopulationService, cls).__new__(cls)
            cls._instance._load_data()
        return cls._instance
    
    def _load_data(self):
        """Load district boundaries and population data"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        geojson_path = os.path.join(base_dir, "data/districts.geojson")
        csv_path = os.path.join(base_dir, "data/population.csv")
        
        if not os.path.exists(geojson_path) or not os.path.exists(csv_path):
            print("Data files not found. Please run data processing script.")
            return

        print("Loading population data...")
        # Load GeoJSON
        self._districts_gdf = gpd.read_file(geojson_path)
        
        # Load Population CSV
        pop_df = pd.read_csv(csv_path)
        
        # Merge population data based on state/district
        # Note: In GADM, 'state' is NAME_1 and 'district' is NAME_2
        # Our processed geojson has 'state' and 'district' columns
        self._districts_gdf = self._districts_gdf.merge(
            pop_df, 
            how='left', 
            left_on=['state', 'district'], 
            right_on=['state_name', 'district_name']
        )
        
        # Fill missing population with 0 or estimate
        self._districts_gdf['population'] = self._districts_gdf['population'].fillna(0)
        
        # Ensure CRS is projected for accurate area calculation
        # Using India-centric projection (EPSG:32644 - UTM Zone 44N) 
        # roughly for area calculations, or equal area projection like EPSG:3035 (Europe)
        # For India, EPSG:32644 is decent, or Albers Equal Area EPSG:102028 (but might not be standard in all proj libs)
        # We will project on the fly during calculation to ensure accuracy
        
        print(f"Loaded {len(self._districts_gdf)} districts with population data.")

    def calculate_weighted_population(self, voronoi_features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Calculate population for each Voronoi cell based on intersection with districts.
        """
        if self._districts_gdf is None:
            self._load_data()
            if self._districts_gdf is None:
                return []
        
        results = []
        
        # Create GeoDataFrame from Voronoi features
        geoms = [shape(f['geometry']) for f in voronoi_features]
        ids = [f['properties'].get('facility_id', i) for i, f in enumerate(voronoi_features)]
        voronoi_gdf = gpd.GeoDataFrame({'geometry': geoms, 'id': ids}, crs="EPSG:4326")
        
        # Spatial Join - find districts that intersect with Voronoi cells
        # This gives us pairs of (voronoi_idx, district_idx)
        # However, we need exact intersection areas.
        
        # Project both to projected CRS for area calc
        projected_crs = "EPSG:32644"
        districts_proj = self._districts_gdf.to_crs(projected_crs)
        voronoi_proj = voronoi_gdf.to_crs(projected_crs)
        
        for idx, row in voronoi_proj.iterrows():
            voronoi_geom = row['geometry']
            facility_id = row['id']
            
            # Find intersecting districts using spatial index
            candidates_idx = districts_proj.sindex.query(voronoi_geom, predicate='intersects')
            candidates = districts_proj.iloc[candidates_idx]
            
            total_weighted_pop = 0
            breakdown = []
            
            for _, district in candidates.iterrows():
                intersection = voronoi_geom.intersection(district['geometry'])
                if not intersection.is_empty:
                    intersection_area = intersection.area
                    district_area = district['geometry'].area
                    
                    if district_area > 0:
                        ratio = intersection_area / district_area
                        weighted_pop = district['population'] * ratio
                        
                        total_weighted_pop += weighted_pop
                        
                        breakdown.append({
                            'district': district['district'],
                            'state': district['state'],
                            'intersection_area_km2': intersection_area / 1e6,
                            'overlap_percentage': ratio * 100,
                            'contributed_population': int(weighted_pop)
                        })
            
            results.append({
                'facility_id': facility_id,
                'total_population': int(total_weighted_pop),
                'breakdown': sorted(breakdown, key=lambda x: x['contributed_population'], reverse=True)[:5] # Top 5
            })
            
        return results
