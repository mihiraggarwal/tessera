"""
Fetch public facilities data from OpenStreetMap using Overpass API.

This script fetches:
- Metro/Subway stations
- Fire stations
- Police stations

For India and saves them as CSVs in data/public/
"""
import requests
import csv
import time
from pathlib import Path
from typing import List, Dict, Any

# Overpass API endpoint
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Output directory
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "public"


def query_overpass(query: str, max_retries: int = 3) -> Dict[str, Any]:
    """Execute an Overpass API query with retries."""
    for attempt in range(max_retries):
        try:
            response = requests.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=180  # 3 minutes timeout for large queries
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"  Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                wait_time = 30 * (attempt + 1)
                print(f"  Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                raise
    return {}


def fetch_metro_stations() -> List[Dict[str, Any]]:
    """Fetch metro/subway stations in India."""
    print("Fetching metro stations...")
    
    query = """
    [out:json][timeout:180];
    area["ISO3166-1"="IN"]->.india;
    (
      node["railway"="station"]["station"="subway"](area.india);
      node["railway"="station"]["station"="metro"](area.india);
      node["station"="subway"](area.india);
      node["station"="metro"](area.india);
    );
    out body;
    """
    
    result = query_overpass(query)
    stations = []
    
    for element in result.get("elements", []):
        if element.get("type") == "node":
            tags = element.get("tags", {})
            stations.append({
                "name": tags.get("name", tags.get("name:en", "Unknown Metro Station")),
                "lat": element["lat"],
                "lng": element["lon"],
                "type": "metro_station",
                "state": tags.get("addr:state", ""),
                "district": tags.get("addr:district", ""),
                "operator": tags.get("operator", ""),
                "line": tags.get("line", tags.get("railway:line", ""))
            })
    
    print(f"  Found {len(stations)} metro stations")
    return stations


def fetch_fire_stations() -> List[Dict[str, Any]]:
    """Fetch fire stations in India."""
    print("Fetching fire stations...")
    
    # Broader query to catch more stations
    query = """
    [out:json][timeout:180];
    area["ISO3166-1"="IN"]->.india;
    (
      node["amenity"="fire_station"](area.india);
      way["amenity"="fire_station"](area.india);
      relation["amenity"="fire_station"](area.india);
      
      node["building"="fire_station"](area.india);
      way["building"="fire_station"](area.india);
      relation["building"="fire_station"](area.india);
    );
    out center;
    """
    
    result = query_overpass(query)
    stations = []
    seen_ids = set()  # To avoid duplicates from multiple tags
    
    for element in result.get("elements", []):
        elem_id = f"{element['type']}/{element['id']}"
        if elem_id in seen_ids:
            continue
        seen_ids.add(elem_id)
        
        tags = element.get("tags", {})
        
        # Get coordinates
        if element.get("type") == "node":
            lat, lng = element["lat"], element["lon"]
        else:
            center = element.get("center", {})
            lat, lng = center.get("lat"), center.get("lon")
            if not lat or not lng:
                continue
        
        stations.append({
            "name": tags.get("name", tags.get("name:en", "Fire Station")),
            "lat": lat,
            "lng": lng,
            "type": "fire_station",
            "state": tags.get("addr:state", ""),
            "district": tags.get("addr:district", ""),
            "phone": tags.get("phone", tags.get("contact:phone", ""))
        })
    
    print(f"  Found {len(stations)} fire stations")
    return stations


def fetch_police_stations() -> List[Dict[str, Any]]:
    """Fetch police stations in India."""
    print("Fetching police stations...")
    
    query = """
    [out:json][timeout:180];
    area["ISO3166-1"="IN"]->.india;
    (
      node["amenity"="police"](area.india);
      way["amenity"="police"](area.india);
    );
    out center;
    """
    
    result = query_overpass(query)
    stations = []
    
    for element in result.get("elements", []):
        tags = element.get("tags", {})
        
        if element.get("type") == "node":
            lat, lng = element["lat"], element["lon"]
        else:
            center = element.get("center", {})
            lat, lng = center.get("lat"), center.get("lon")
            if not lat or not lng:
                continue
        
        stations.append({
            "name": tags.get("name", tags.get("name:en", "Police Station")),
            "lat": lat,
            "lng": lng,
            "type": "police_station",
            "state": tags.get("addr:state", ""),
            "district": tags.get("addr:district", ""),
            "phone": tags.get("phone", tags.get("contact:phone", ""))
        })
    
    print(f"  Found {len(stations)} police stations")
    return stations


def fetch_bus_stops_for_state(state_name: str) -> List[Dict[str, Any]]:
    """Fetch bus stops for a specific state (dynamic, not pre-generated)."""
    print(f"Fetching bus stops for {state_name}...")
    
    query = f"""
    [out:json][timeout:180];
    area["name"="{state_name}"]["admin_level"="4"]->.state;
    (
      node["highway"="bus_stop"](area.state);
    );
    out body;
    """
    
    result = query_overpass(query)
    stops = []
    
    for element in result.get("elements", []):
        if element.get("type") == "node":
            tags = element.get("tags", {})
            stops.append({
                "name": tags.get("name", tags.get("name:en", "Bus Stop")),
                "lat": element["lat"],
                "lng": element["lon"],
                "type": "bus_stop",
                "state": state_name,
                "district": tags.get("addr:district", ""),
                "route": tags.get("route_ref", "")
            })
    
    print(f"  Found {len(stops)} bus stops in {state_name}")
    return stops


def save_to_csv(data: List[Dict[str, Any]], filename: str):
    """Save facility data to CSV."""
    if not data:
        print(f"  No data to save for {filename}")
        return
    
    filepath = DATA_DIR / filename
    fieldnames = ["name", "lat", "lng", "type", "state", "district"]
    
    # Add extra fields if present
    extra_fields = set()
    for item in data[:10]:  # Check first 10 items for extra fields
        extra_fields.update(item.keys())
    extra_fields = extra_fields - set(fieldnames)
    fieldnames.extend(sorted(extra_fields))
    
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)
    
    print(f"  Saved {len(data)} records to {filepath}")


def main():
    """Main entry point - fetch all facility types."""
    print("=" * 50)
    print("Fetching Public Facilities Data from OpenStreetMap")
    print("=" * 50)
    
    # Ensure output directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Fetch and save each category
    try:
        metros = fetch_metro_stations()
        save_to_csv(metros, "metro_stations.csv")
        time.sleep(10)  # Be nice to the Overpass API
    except Exception as e:
        print(f"Error fetching metro stations: {e}")
    
    try:
        fire = fetch_fire_stations()
        save_to_csv(fire, "fire_stations.csv")
        time.sleep(10)
    except Exception as e:
        print(f"Error fetching fire stations: {e}")
    
    try:
        police = fetch_police_stations()
        save_to_csv(police, "police_stations.csv")
    except Exception as e:
        print(f"Error fetching police stations: {e}")
    
    print("\n" + "=" * 50)
    print("Done! Files saved to data/public/")
    print("=" * 50)


if __name__ == "__main__":
    main()
