
import sys
import os
import logging

# Ensure we can import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.voronoi_engine import VoronoiEngine

import pandas as pd

def test_area_calculation():
    engine = VoronoiEngine()
    
    # Load real data
    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "geocode_health_centre.csv")
    print(f"Loading {csv_path}...")
    
    try:
        df = pd.read_csv(csv_path, dtype=str, low_memory=False)
        # Normalize columns
        df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')
        
        # Filter for Maharashtra to match user scenario
        # State column might be 'state_name' or 'state'
        state_col = next((c for c in df.columns if c in ['state', 'state_name']), None)
        if state_col:
            print(f"Filtering by {state_col} = Maharashtra")
            df = df[df[state_col].str.lower() == 'maharashtra']
            print(f"Filtered to {len(df)} records")
        
        # Take a subset to be faster but representative
        # df = df.head(1000) 
        # print(f"Using {len(df)} records for Voronoi")
        
        # Limit to 5000 for feasible debug run, or full if daring
        # Full might crash the agent memory? Let's try 50000
        df = df.head(50000)
        print(f"Using {len(df)} records for Voronoi")
        
        facilities = []
        coords = []
        names = []
        ids = []
        types = []
        
        lat_col = next((c for c in df.columns if c in ['lat', 'latitude']), None)
        lng_col = next((c for c in df.columns if c in ['lng', 'lon', 'longitude']), None)
        name_col = next((c for c in df.columns if c in ['name', 'facility_name']), None)
        
        for idx, row in df.iterrows():
            try:
                lat = float(row[lat_col])
                lng = float(row[lng_col])
                coords.append((lng, lat)) # Note: lng, lat
                names.append(str(row[name_col]))
                ids.append(str(idx))
                types.append("Facility")
            except:
                continue
                
        if not coords:
            print("No valid coords found")
            return

        print("Computing Voronoi...")
        result = engine.compute_voronoi(
            coords=coords,
            names=names,
            facility_ids=ids,
            types=types,
            clip_to_india=True,
            state_filter="Maharashtra"
        )
        
        # Check for non-zero areas
        zero_count = 0
        non_zero_count = 0
        max_a = 0
        
        for feature in result['features']:
            area = feature['properties']['area_sq_km']
            if area > max_a:
                max_a = area
            if area < 0.001:
                zero_count += 1
            else:
                non_zero_count += 1
                
        print(f"Total Features: {len(result['features'])}")
        print(f"Zero Area Count: {zero_count}")
        print(f"Non-Zero Area Count: {non_zero_count}")
        print(f"Max Area: {max_a} sq km")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    test_area_calculation()
