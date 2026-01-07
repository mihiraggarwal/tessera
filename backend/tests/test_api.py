"""
Unit tests for the Voronoi Population Mapping API
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints"""
    
    def test_root_health_check(self):
        """Test root endpoint returns OK"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "message" in data

    def test_health_endpoint(self):
        """Test /health endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestVoronoiEndpoints:
    """Test Voronoi computation endpoints"""
    
    def test_sample_voronoi(self):
        """Test sample Voronoi returns valid GeoJSON"""
        response = client.get("/api/voronoi/sample")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert "features" in data
        # Sample has 6 cities, should have features
        assert len(data["features"]) > 0
    
    def test_compute_voronoi_with_4_facilities(self):
        """Test Voronoi computation with 4 facilities"""
        payload = {
            "facilities": [
                {"name": "Delhi", "lat": 28.6139, "lng": 77.2090},
                {"name": "Mumbai", "lat": 19.0760, "lng": 72.8777},
                {"name": "Chennai", "lat": 13.0827, "lng": 80.2707},
                {"name": "Kolkata", "lat": 22.5726, "lng": 88.3639},
            ],
            "clip_to_india": False
        }
        response = client.post("/api/voronoi/compute", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert "features" in data
    
    def test_compute_voronoi_too_few_facilities(self):
        """Test Voronoi with less than 3 facilities returns error"""
        payload = {
            "facilities": [
                {"name": "Delhi", "lat": 28.6139, "lng": 77.2090},
                {"name": "Mumbai", "lat": 19.0760, "lng": 72.8777},
            ],
            "clip_to_india": False
        }
        response = client.post("/api/voronoi/compute", json=payload)
        assert response.status_code == 400
    
    def test_voronoi_feature_properties(self):
        """Test that Voronoi features have expected properties"""
        response = client.get("/api/voronoi/sample")
        data = response.json()
        
        if len(data["features"]) > 0:
            feature = data["features"][0]
            assert feature["type"] == "Feature"
            assert "properties" in feature
            assert "geometry" in feature
            
            props = feature["properties"]
            assert "name" in props
            assert "area_sq_km" in props
            assert props["area_sq_km"] > 0


class TestBoundariesEndpoints:
    """Test boundaries endpoints"""
    
    def test_india_boundary(self):
        """Test India boundary returns valid GeoJSON"""
        response = client.get("/api/boundaries/india")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "Feature"
        assert data["properties"]["name"] == "India"
        assert data["geometry"]["type"] == "Polygon"
    
    def test_invalid_boundary_level(self):
        """Test invalid boundary level returns error"""
        response = client.get("/api/boundaries/invalid")
        assert response.status_code == 400


class TestUploadEndpoints:
    """Test CSV upload endpoints"""
    
    def test_upload_requires_csv_file(self):
        """Test that non-CSV files are rejected"""
        from io import BytesIO
        
        # Create a fake text file
        file_content = b"some,data\n1,2"
        files = {"file": ("test.txt", BytesIO(file_content), "text/plain")}
        
        response = client.post("/api/upload/csv", files=files)
        assert response.status_code == 400
    
    def test_upload_valid_csv(self):
        """Test uploading a valid CSV file"""
        from io import BytesIO
        
        csv_content = b"name,latitude,longitude,type\nTest Hospital,28.6139,77.2090,hospital\nTest Clinic,19.0760,72.8777,clinic"
        files = {"file": ("test.csv", BytesIO(csv_content), "text/csv")}
        
        response = client.post("/api/upload/csv", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["valid_facilities"] == 2
        assert len(data["facilities"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
