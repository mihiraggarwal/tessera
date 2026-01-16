import requests
import time

def debug_insights():
    url = "http://localhost:8000/api/voronoi/insights"
    # Create 1999 facilities
    facilities = []
    for i in range(1999):
        facilities.append({
            "name": f"F{i}",
            "lat": 20.0 + (i * 0.0001),
            "lng": 75.0 + (i * 0.0001)
        })
    
    payload = {
        "facilities": facilities,
        "clip_to_india": True,
        "include_population": False
    }
    
    print(f"Sending request with {len(facilities)} facilities...")
    start_time = time.time()
    try:
        response = requests.post(url, json=payload, timeout=300)
        end_time = time.time()
        print(f"Status Code: {response.status_code}")
        print(f"Response Time: {end_time - start_time:.2f}s")
        if response.status_code != 200:
            print("Response text:")
            print(response.text)
        else:
            print("Success! Data received.")
            data = response.json()
            print("MEC:", data.get('minimum_enclosing_circle'))
            print("Recommendations count:", len(data.get('recommendations', [])))
    except requests.exceptions.Timeout:
        print("Request timed out after 300s!")
    except Exception as e:
        print(f"Exception: {str(e)}")

if __name__ == "__main__":
    debug_insights()
