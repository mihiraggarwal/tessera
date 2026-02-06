from fastapi.testclient import TestClient
from app.main import app
from app.services.dcel import set_current_dcel, DCEL
import pytest

client = TestClient(app)

# Mock DCEL with some dummy data for testing
@pytest.fixture
def mock_dcel():
    dcel = DCEL()
    # Manually add some dummy data if needed, or mock methods directly
    # For now, we'll just set it so the endpoints don't return 400 "No Voronoi"
    
    # We need to mock the methods called by the endpoints
    # But since DCEL is a complex object, it might be easier to mock the get_current_dcel dependency
    # or populate a real DCEL with minimal data
    return dcel

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "api_version": "0.2.0"}

def test_dcel_endpoints_no_data():
    # Ensure we start with no DCEL
    set_current_dcel(None)
    
    # Test top-by-population without computed Voronoi
    response = client.post("/api/dcel/top-by-population", json={"top_n": 5})
    assert response.status_code == 400
    assert "No Voronoi diagram has been computed yet" in response.json()["detail"]

    # Test point query without computed Voronoi
    response = client.post("/api/dcel/query-point", json={"lat": 10.0, "lng": 20.0})
    assert response.status_code == 400

def test_top_facilities_type_coercion():
    # This tests the Pydantic model validation specifically, enabling it even without DCEL
    # We want to verify that passing a float doesn't cause a validation error (422)
    # but proceeds to the logic (which returns 400 because no DCEL)
    
    set_current_dcel(None)
    
    # Pass float 5.0 - should be coerced to 5 by Pydantic
    # If coercion fails, we'd get 422 Unprocessable Entity
    # If coercion works, we get 400 Bad Request (business logic error)
    response = client.post("/api/dcel/top-by-population", json={"top_n": 5.0})
    
    assert response.status_code == 400  # Business logic error, meaning validation passed
    assert response.status_code != 422  # Validation error
