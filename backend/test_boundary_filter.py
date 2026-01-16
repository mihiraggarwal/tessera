import requests
import json

def test_insights_boundary_filtering():
    url = "http://localhost:8000/api/voronoi/insights"
    
    facilities = [
        {"name": "Delhi", "lat": 28.6139, "lng": 77.2090, "id": "delhi"},
        {"name": "Mumbai", "lat": 19.0760, "lng": 72.8777, "id": "mumbai"},
        {"name": "Chennai", "lat": 13.0827, "lng": 80.2707, "id": "chennai"},
        {"name": "London", "lat": 51.5074, "lng": -0.1278, "id": "london"},
        {"name": "New York", "lat": 40.7128, "lng": -74.0060, "id": "ny"}
    ]
    
    payload = {
        "facilities": facilities,
        "clip_to_india": True,
        "include_population": False
    }
    
    print(f"Testing with {len(facilities)} facilities (3 inside India, 2 outside)...")
    
    try:
        response = requests.post(url, json=payload)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            
            # Check coverage stats
            stats = data.get('coverage_stats', {})
            count = stats.get('facility_count')
            print(f"Facility count in stats: {count}")
            
            # Check most overburdened list
            overburdened = data.get('most_overburdened', [])
            names = [o['name'] for o in overburdened]
            print(f"Facilities kept: {names}")
            
            # Check recommendations - search for CRITICAL_GAP which uses MEC/LEC
            recs = data.get('recommendations', [])
            print(f"Found {len(recs)} recommendations")
            
            if count == 3:
                print("SUCCESS: Boundary filtering is working correctly!")
            else:
                print(f"FAILURE: Expected 3 facilities, got {count}.")
                
        else:
            print(f"Error: {response.content.decode()}")
    except Exception as e:
        print(f"Exception: {str(e)}")

if __name__ == "__main__":
    test_insights_boundary_filtering()
