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


def fetch_hospitals() -> List[Dict[str, Any]]:
    """Fetch hospitals in India."""
    print("Fetching hospitals...")
    
    query = """
    [out:json][timeout:180];
    area["ISO3166-1"="IN"]->.india;
    (
      node["amenity"="hospital"](area.india);
      way["amenity"="hospital"](area.india);
      relation["amenity"="hospital"](area.india);
    );
    out center;
    """
    
    result = query_overpass(query)
    hospitals = []
    seen_ids = set()
    
    for element in result.get("elements", []):
        elem_id = f"{element['type']}/{element['id']}"
        if elem_id in seen_ids:
            continue
        seen_ids.add(elem_id)
        
        tags = element.get("tags", {})
        
        if element.get("type") == "node":
            lat, lng = element["lat"], element["lon"]
        else:
            center = element.get("center", {})
            lat, lng = center.get("lat"), center.get("lon")
            if not lat or not lng:
                continue
        
        hospitals.append({
            "name": tags.get("name", tags.get("name:en", "Hospital")),
            "lat": lat,
            "lng": lng,
            "type": "hospital",
            "state": tags.get("addr:state", ""),
            "district": tags.get("addr:district", ""),
            "emergency": tags.get("emergency", ""),
            "beds": tags.get("beds", "")
        })
    
    print(f"  Found {len(hospitals)} hospitals")
    return hospitals


def fetch_blood_banks() -> List[Dict[str, Any]]:
    """Fetch blood banks in India."""
    print("Fetching blood banks...")
    
    query = """
    [out:json][timeout:180];
    area["ISO3166-1"="IN"]->.india;
    (
      node["healthcare"="blood_bank"](area.india);
      way["healthcare"="blood_bank"](area.india);
      node["amenity"="blood_bank"](area.india);
      way["amenity"="blood_bank"](area.india);
    );
    out center;
    """
    
    result = query_overpass(query)
    banks = []
    seen_ids = set()
    
    for element in result.get("elements", []):
        elem_id = f"{element['type']}/{element['id']}"
        if elem_id in seen_ids:
            continue
        seen_ids.add(elem_id)
        
        tags = element.get("tags", {})
        
        if element.get("type") == "node":
            lat, lng = element["lat"], element["lon"]
        else:
            center = element.get("center", {})
            lat, lng = center.get("lat"), center.get("lon")
            if not lat or not lng:
                continue
        
        banks.append({
            "name": tags.get("name", tags.get("name:en", "Blood Bank")),
            "lat": lat,
            "lng": lng,
            "type": "blood_bank",
            "state": tags.get("addr:state", ""),
            "district": tags.get("addr:district", ""),
            "phone": tags.get("phone", tags.get("contact:phone", ""))
        })
    
    print(f"  Found {len(banks)} blood banks")
    return banks


def fetch_schools() -> List[Dict[str, Any]]:
    """Fetch schools in India."""
    print("Fetching schools...")
    
    query = """
    [out:json][timeout:180];
    area["ISO3166-1"="IN"]->.india;
    (
      node["amenity"="school"](area.india);
      way["amenity"="school"](area.india);
    );
    out center;
    """
    
    result = query_overpass(query)
    schools = []
    
    for element in result.get("elements", []):
        tags = element.get("tags", {})
        
        if element.get("type") == "node":
            lat, lng = element["lat"], element["lon"]
        else:
            center = element.get("center", {})
            lat, lng = center.get("lat"), center.get("lon")
            if not lat or not lng:
                continue
        
        schools.append({
            "name": tags.get("name", tags.get("name:en", "School")),
            "lat": lat,
            "lng": lng,
            "type": "school",
            "state": tags.get("addr:state", ""),
            "district": tags.get("addr:district", "")
        })
    
    print(f"  Found {len(schools)} schools")
    return schools


def fetch_universities() -> List[Dict[str, Any]]:
    """Fetch universities in India."""
    print("Fetching universities...")
    
    query = """
    [out:json][timeout:180];
    area["ISO3166-1"="IN"]->.india;
    (
      node["amenity"="university"](area.india);
      way["amenity"="university"](area.india);
    );
    out center;
    """
    
    result = query_overpass(query)
    universities = []
    
    for element in result.get("elements", []):
        tags = element.get("tags", {})
        
        if element.get("type") == "node":
            lat, lng = element["lat"], element["lon"]
        else:
            center = element.get("center", {})
            lat, lng = center.get("lat"), center.get("lon")
            if not lat or not lng:
                continue
        
        universities.append({
            "name": tags.get("name", tags.get("name:en", "University")),
            "lat": lat,
            "lng": lng,
            "type": "university",
            "state": tags.get("addr:state", ""),
            "district": tags.get("addr:district", "")
        })
    
    print(f"  Found {len(universities)} universities")
    return universities


def fetch_banks() -> List[Dict[str, Any]]:
    """Fetch banks in India."""
    print("Fetching banks...")
    
    query = """
    [out:json][timeout:180];
    area["ISO3166-1"="IN"]->.india;
    (
      node["amenity"="bank"](area.india);
      way["amenity"="bank"](area.india);
    );
    out center;
    """
    
    result = query_overpass(query)
    banks = []
    
    for element in result.get("elements", []):
        tags = element.get("tags", {})
        
        if element.get("type") == "node":
            lat, lng = element["lat"], element["lon"]
        else:
            center = element.get("center", {})
            lat, lng = center.get("lat"), center.get("lon")
            if not lat or not lng:
                continue
        
        banks.append({
            "name": tags.get("name", tags.get("name:en", "Bank")),
            "lat": lat,
            "lng": lng,
            "type": "bank",
            "state": tags.get("addr:state", ""),
            "district": tags.get("addr:district", "")
        })
    
    print(f"  Found {len(banks)} banks")
    return banks


def fetch_atms() -> List[Dict[str, Any]]:
    """Fetch ATMs in India."""
    print("Fetching ATMs...")
    
    query = """
    [out:json][timeout:180];
    area["ISO3166-1"="IN"]->.india;
    (
      node["amenity"="atm"](area.india);
    );
    out body;
    """
    
    result = query_overpass(query)
    atms = []
    
    for element in result.get("elements", []):
        if element.get("type") == "node":
            tags = element.get("tags", {})
            atms.append({
                "name": tags.get("name", tags.get("operator", "ATM")),
                "lat": element["lat"],
                "lng": element["lon"],
                "type": "atm",
                "state": tags.get("addr:state", ""),
                "district": tags.get("addr:district", ""),
                "operator": tags.get("operator", "")
            })
    
    print(f"  Found {len(atms)} ATMs")
    return atms


def fetch_airports() -> List[Dict[str, Any]]:
    """Fetch airports in India."""
    print("Fetching airports...")
    
    query = """
    [out:json][timeout:180];
    area["ISO3166-1"="IN"]->.india;
    (
      node["aeroway"="aerodrome"](area.india);
      way["aeroway"="aerodrome"](area.india);
    );
    out center;
    """
    
    result = query_overpass(query)
    airports = []
    
    for element in result.get("elements", []):
        tags = element.get("tags", {})
        
        if element.get("type") == "node":
            lat, lng = element["lat"], element["lon"]
        else:
            center = element.get("center", {})
            lat, lng = center.get("lat"), center.get("lon")
            if not lat or not lng:
                continue
        
        airports.append({
            "name": tags.get("name", tags.get("name:en", "Airport")),
            "lat": lat,
            "lng": lng,
            "type": "airport",
            "state": tags.get("addr:state", ""),
            "district": tags.get("addr:district", ""),
            "iata": tags.get("iata", "")
        })
    
    print(f"  Found {len(airports)} airports")
    return airports


def fetch_petrol_pumps() -> List[Dict[str, Any]]:
    """Fetch petrol pumps in India."""
    print("Fetching petrol pumps...")
    
    query = """
    [out:json][timeout:180];
    area["ISO3166-1"="IN"]->.india;
    (
      node["amenity"="fuel"](area.india);
      way["amenity"="fuel"](area.india);
    );
    out center;
    """
    
    result = query_overpass(query)
    pumps = []
    
    for element in result.get("elements", []):
        tags = element.get("tags", {})
        
        if element.get("type") == "node":
            lat, lng = element["lat"], element["lon"]
        else:
            center = element.get("center", {})
            lat, lng = center.get("lat"), center.get("lon")
            if not lat or not lng:
                continue
        
        pumps.append({
            "name": tags.get("name", tags.get("brand", "Petrol Pump")),
            "lat": lat,
            "lng": lng,
            "type": "petrol_pump",
            "state": tags.get("addr:state", ""),
            "district": tags.get("addr:district", ""),
            "operator": tags.get("operator", "")
        })
    
    print(f"  Found {len(pumps)} petrol pumps")
    return pumps


def fetch_parks() -> List[Dict[str, Any]]:
    """Fetch parks in India."""
    print("Fetching parks...")
    
    query = """
    [out:json][timeout:180];
    area["ISO3166-1"="IN"]->.india;
    (
      node["leisure"="park"](area.india);
      way["leisure"="park"](area.india);
    );
    out center;
    """
    
    result = query_overpass(query)
    parks = []
    
    for element in result.get("elements", []):
        tags = element.get("tags", {})
        
        if element.get("type") == "node":
            lat, lng = element["lat"], element["lon"]
        else:
            center = element.get("center", {})
            lat, lng = center.get("lat"), center.get("lon")
            if not lat or not lng:
                continue
        
        parks.append({
            "name": tags.get("name", tags.get("name:en", "Park")),
            "lat": lat,
            "lng": lng,
            "type": "park",
            "state": tags.get("addr:state", ""),
            "district": tags.get("addr:district", "")
        })
    
    print(f"  Found {len(parks)} parks")
    return parks


def fetch_post_offices() -> List[Dict[str, Any]]:
    """Fetch post offices in India."""
    print("Fetching post offices...")
    
    query = """
    [out:json][timeout:180];
    area["ISO3166-1"="IN"]->.india;
    (
      node["amenity"="post_office"](area.india);
      way["amenity"="post_office"](area.india);
    );
    out center;
    """
    
    result = query_overpass(query)
    post_offices = []
    
    for element in result.get("elements", []):
        tags = element.get("tags", {})
        
        if element.get("type") == "node":
            lat, lng = element["lat"], element["lon"]
        else:
            center = element.get("center", {})
            lat, lng = center.get("lat"), center.get("lon")
            if not lat or not lng:
                continue
        
        post_offices.append({
            "name": tags.get("name", tags.get("name:en", "Post Office")),
            "lat": lat,
            "lng": lng,
            "type": "post_office",
            "state": tags.get("addr:state", ""),
            "district": tags.get("addr:district", "")
        })
    
    print(f"  Found {len(post_offices)} post offices")
    return post_offices


def fetch_preschools() -> List[Dict[str, Any]]:
    """Fetch preschools/kindergartens in India."""
    print("Fetching preschools...")
    
    query = """
    [out:json][timeout:180];
    area["ISO3166-1"="IN"]->.india;
    (
      node["amenity"="kindergarten"](area.india);
      way["amenity"="kindergarten"](area.india);
    );
    out center;
    """
    
    result = query_overpass(query)
    preschools = []
    
    for element in result.get("elements", []):
        tags = element.get("tags", {})
        
        if element.get("type") == "node":
            lat, lng = element["lat"], element["lon"]
        else:
            center = element.get("center", {})
            lat, lng = center.get("lat"), center.get("lon")
            if not lat or not lng:
                continue
        
        preschools.append({
            "name": tags.get("name", tags.get("name:en", "Preschool")),
            "lat": lat,
            "lng": lng,
            "type": "preschool",
            "state": tags.get("addr:state", ""),
            "district": tags.get("addr:district", "")
        })
    
    print(f"  Found {len(preschools)} preschools")
    return preschools


def fetch_daycares() -> List[Dict[str, Any]]:
    """Fetch daycare centers in India."""
    print("Fetching daycares...")
    
    query = """
    [out:json][timeout:180];
    area["ISO3166-1"="IN"]->.india;
    (
      node["amenity"="childcare"](area.india);
      way["amenity"="childcare"](area.india);
    );
    out center;
    """
    
    result = query_overpass(query)
    daycares = []
    
    for element in result.get("elements", []):
        tags = element.get("tags", {})
        
        if element.get("type") == "node":
            lat, lng = element["lat"], element["lon"]
        else:
            center = element.get("center", {})
            lat, lng = center.get("lat"), center.get("lon")
            if not lat or not lng:
                continue
        
        daycares.append({
            "name": tags.get("name", tags.get("name:en", "Daycare")),
            "lat": lat,
            "lng": lng,
            "type": "daycare",
            "state": tags.get("addr:state", ""),
            "district": tags.get("addr:district", "")
        })
    
    print(f"  Found {len(daycares)} daycares")
    return daycares




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
    
    # Track results
    results = []
    
    services = [
        ("hospitals", fetch_hospitals, "hospitals.csv"),
        ("blood_banks", fetch_blood_banks, "blood_banks.csv"),
        ("schools", fetch_schools, "schools.csv"),
        ("universities", fetch_universities, "universities.csv"),
        ("banks", fetch_banks, "banks.csv"),
        ("atms", fetch_atms, "atms.csv"),
        ("airports", fetch_airports, "airports.csv"),
        ("petrol_pumps", fetch_petrol_pumps, "petrol_pumps.csv"),
        ("parks", fetch_parks, "parks.csv"),
        ("post_offices", fetch_post_offices, "post_offices.csv"),
        ("preschools", fetch_preschools, "preschools.csv"),
        ("daycares", fetch_daycares, "daycares.csv"),
    ]
    
    for service_name, fetch_func, filename in services:
        try:
            print(f"\n[{service_name.upper()}]")
            data = fetch_func()
            save_to_csv(data, filename)
            results.append((service_name, len(data), "✓"))
            time.sleep(10)  # Be nice to the Overpass API
        except Exception as e:
            print(f"  ✗ Error fetching {service_name}: {e}")
            results.append((service_name, 0, "✗"))
    
    # Print summary
    print("\n" + "=" * 60)
    print("FETCH SUMMARY")
    print("=" * 60)
    print(f"{'Service':<20} {'Records':<10} {'Status'}")
    print("-" * 60)
    for service, count, status in results:
        print(f"{service:<20} {count:<10} {status}")
    print("=" * 60)
    print(f"Done! Files saved to {DATA_DIR}")
    print("=" * 60)



if __name__ == "__main__":
    main()
