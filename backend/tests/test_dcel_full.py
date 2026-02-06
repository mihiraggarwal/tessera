from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from app.main import app
from app.services.dcel import set_current_dcel
import pytest

client = TestClient(app)

# Helper to create a mock VoronoiFace
def create_mock_face(facility_id="F1", facility_name="Hospital A", population=1000, area=5.0):
    face = MagicMock()
    face.facility_id = facility_id
    face.facility_name = facility_name
    face.properties = {"population": population, "area_sq_km": area}
    return face

@pytest.fixture
def mock_dcel_computed():
    dcel = MagicMock()
    
    # Mock point_query
    dcel.point_query.return_value = create_mock_face()
    
    # Mock range_query
    dcel.range_query.return_value = [
        create_mock_face("F1", "Hospital A", 1000, 5.0),
        create_mock_face("F2", "Clinic B", 500, 2.0)
    ]
    
    # Mock get_facilities_by_population
    dcel.get_facilities_by_population.return_value = [
        {"facility_id": "F1", "facility_name": "Hospital A", "population": 1000},
        {"facility_id": "F2", "facility_name": "Clinic B", "population": 500}
    ]
    
    # Mock get_face_by_facility_id
    dcel.get_face_by_facility_id.side_effect = lambda fid: create_mock_face(fid, f"Facility {fid}")
    
    # Mock get_adjacent_facilities
    dcel.get_adjacent_facilities.return_value = ["F2", "F3"]
    
    # Mock to_dict for summary
    dcel.to_dict.return_value = {
        "num_sites": 10,
        "num_vertices": 20,
        "num_faces": 10,
        "num_half_edges": 30,
        "bounds": [0, 0, 100, 100]
    }
    
    return dcel

def test_query_point_success(mock_dcel_computed):
    set_current_dcel(mock_dcel_computed)
    
    response = client.post("/api/dcel/query-point", json={"lat": 10.0, "lng": 20.0})
    
    assert response.status_code == 200
    data = response.json()
    assert data["found"] is True
    assert data["facility_id"] == "F1"
    assert data["facility_name"] == "Hospital A"
    assert data["population"] == 1000
    
    # Verify mock was called correctly
    mock_dcel_computed.point_query.assert_called_with(10.0, 20.0)

def test_range_query_success(mock_dcel_computed):
    set_current_dcel(mock_dcel_computed)
    
    response = client.post("/api/dcel/range-query", json={
        "min_lat": 0, "min_lng": 0, "max_lat": 10, "max_lng": 10
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert len(data["facilities"]) == 2
    assert data["facilities"][0]["facility_id"] == "F1"

def test_top_facilities_success(mock_dcel_computed):
    set_current_dcel(mock_dcel_computed)
    
    # Test with float top_n (Gemini style)
    response = client.post("/api/dcel/top-by-population", json={"top_n": 5.0})
    
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert data["facilities"][0]["population"] == 1000
    
    # Verify mock called with INT 5, not float 5.0
    mock_dcel_computed.get_facilities_by_population.assert_called_with(top_n=5, state=None)

def test_adjacent_facilities_success(mock_dcel_computed):
    set_current_dcel(mock_dcel_computed)
    
    response = client.get("/api/dcel/adjacent/F1")
    
    assert response.status_code == 200
    data = response.json()
    assert data["facility_id"] == "F1"
    assert data["adjacent_count"] == 2
    assert data["adjacent_facilities"][0]["facility_id"] == "F2"

def test_dcel_summary_success(mock_dcel_computed):
    set_current_dcel(mock_dcel_computed)
    
    response = client.get("/api/dcel/summary")
    
    assert response.status_code == 200
    data = response.json()
    assert data["available"] is True
    assert data["data"]["num_sites"] == 10
