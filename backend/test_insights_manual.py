import requests
import json

def test_insights():
    url = "http://localhost:8000/api/voronoi/insights"
    # Generate 2000 random points in India coordinates
    facilities = []
    for i in range(2000):
        facilities.append({
            "name": f"Facility {i}",
            "lat": 20.0 + (i * 0.005),
            "lng": 75.0 + (i * 0.005)
        })
    
    payload = {
        "facilities": facilities,
        "clip_to_india": True,
        "include_population": True
    }
    
    try:
        response = requests.post(url, json=payload)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("Recommendations keys:", data.get('recommendations', []))
            print("MEC:", data.get('minimum_enclosing_circle'))
            print("Empty Circle:", data.get('largest_empty_circle'))
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {str(e)}")

if __name__ == "__main__":
    test_insights()
