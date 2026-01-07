import geopandas as gpd
import pandas as pd
import numpy as np
import os

def process_data():
    # Paths
    shp_path = "/tmp/gadm_india/gadm41_IND_2.shp"
    output_geojson = "backend/app/data/districts.geojson"
    output_csv = "backend/app/data/population.csv"
    
    print(f"Reading shapefile from {shp_path}...")
    gdf = gpd.read_file(shp_path)
    
    print(f"Original CRS: {gdf.crs}")
    print(f"Columns: {gdf.columns}")
    print(f"Rows: {len(gdf)}")
    
    # Keep only relevant columns
    # NAME_1 = State, NAME_2 = District
    gdf = gdf[['NAME_1', 'NAME_2', 'geometry']]
    gdf.columns = ['state', 'district', 'geometry']
    
    # Simplify geometry for web performance
    print("Simplifying geometries (tolerance=0.01)...")
    gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.01, preserve_topology=True)
    
    # Save to GeoJSON
    print(f"Saving to {output_geojson}...")
    os.makedirs(os.path.dirname(output_geojson), exist_ok=True)
    gdf.to_file(output_geojson, driver='GeoJSON')
    
    # Generate population data
    print("Generating synthetic population data...")
    dataset = []
    
    # Set seed for reproducibility
    np.random.seed(42)
    
    for _, row in gdf.iterrows():
        # Synthetic population between 100,000 and 5,000,000
        pop = np.random.randint(100000, 5000000)
        
        dataset.append({
            'state_name': row['state'],
            'district_name': row['district'],
            'population': pop
        })
        
    df = pd.DataFrame(dataset)
    print(f"Saving population data to {output_csv}...")
    df.to_csv(output_csv, index=False)
    
    print("Done!")

if __name__ == "__main__":
    process_data()
