import pytest
from pathlib import Path
import pandas as pd
from app.services.augmentation_service import AugmentationService

@pytest.fixture
def sample_raw_csv(tmp_path):
    csv_content = """lat_coord,lng_coord,location_title,category
23.0225,72.5714,"Hospital A","Health"
21.1702,72.8311,"Hospital B","Health"
"""
    file_path = tmp_path / "raw_data.csv"
    file_path.write_text(csv_content)
    return file_path

def test_analyze_csv(sample_raw_csv):
    service = AugmentationService()
    result = service.analyze_csv(sample_raw_csv)
    
    assert "columns" in result
    assert "sample_data" in result
    assert "suggested_mapping" in result
    assert "lat" in result["suggested_mapping"]
    assert "lng" in result["suggested_mapping"]
    assert "name" in result["suggested_mapping"]
    assert result["suggested_mapping"]["lat"] == "lat_coord"

def test_transform_csv(sample_raw_csv, tmp_path):
    service = AugmentationService()
    mapping = {
        "name": "location_title",
        "lat": "lat_coord",
        "lng": "lng_coord",
        "type": "category"
    }
    
    output_name = "standardized.csv"
    output_path = service.transform_csv(sample_raw_csv, mapping, output_name)
    
    assert output_path.exists()
    df = pd.read_csv(output_path)
    assert set(df.columns) == {"name", "lat", "lng", "type"}
    assert df.iloc[0]["name"] == "Hospital A"
    assert df.iloc[0]["lat"] == 23.0225
