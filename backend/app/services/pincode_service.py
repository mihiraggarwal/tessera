"""
Pincode Service - Handles pincode lookup and reverse geocoding.
"""
import os
import csv
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass
from functools import lru_cache
import math


@dataclass
class PincodeInfo:
    """Information about a pincode."""
    pincode: str
    place_name: str
    state: str
    district: str
    lat: float
    lng: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pincode": self.pincode,
            "place_name": self.place_name,
            "state": self.state,
            "district": self.district,
            "lat": self.lat,
            "lng": self.lng,
        }


class PincodeService:
    """Service for pincode lookup and reverse geocoding."""
    
    _instance = None
    _pincodes: Dict[str, PincodeInfo] = {}
    _pincode_coords: List[Tuple[float, float, str]] = []  # (lat, lng, pincode)
    _loaded = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not PincodeService._loaded:
            self._load_pincodes()
    
    def _load_pincodes(self):
        """Load pincode data from GeoNames file."""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        pincode_file = os.path.join(base_dir, "..", "data", "public", "pincodes", "IN.txt")
        
        if not os.path.exists(pincode_file):
            print(f"Warning: Pincode file not found at {pincode_file}")
            return
        
        try:
            # GeoNames format: country_code, postal_code, place_name, 
            # admin_name1 (state), admin_code1, admin_name2 (district), 
            # admin_code2, admin_name3, admin_code3, latitude, longitude, accuracy
            with open(pincode_file, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split('\t')
                    if len(parts) >= 11:
                        pincode = parts[1]
                        place_name = parts[2]
                        state = parts[3]
                        district = parts[5] if parts[5] else parts[3]
                        
                        try:
                            lat = float(parts[9])
                            lng = float(parts[10])
                        except (ValueError, IndexError):
                            continue
                        
                        info = PincodeInfo(
                            pincode=pincode,
                            place_name=place_name,
                            state=state,
                            district=district,
                            lat=lat,
                            lng=lng,
                        )
                        
                        # Store in dict (may overwrite if same pincode appears multiple times)
                        # We keep track of all locations for a pincode
                        if pincode not in PincodeService._pincodes:
                            PincodeService._pincodes[pincode] = info
                            PincodeService._pincode_coords.append((lat, lng, pincode))
            
            PincodeService._loaded = True
            print(f"Loaded {len(PincodeService._pincodes)} unique pincodes")
            
        except Exception as e:
            print(f"Error loading pincodes: {e}")
    
    def get_pincode(self, pincode: str) -> Optional[PincodeInfo]:
        """Get pincode information by pincode."""
        return PincodeService._pincodes.get(pincode)
    
    def validate_pincode(self, pincode: str) -> bool:
        """Check if a pincode exists."""
        return pincode in PincodeService._pincodes
    
    def search_pincodes(self, query: str, limit: int = 10) -> List[PincodeInfo]:
        """Search pincodes by partial match."""
        results = []
        query_lower = query.lower()
        
        for pincode, info in PincodeService._pincodes.items():
            if (pincode.startswith(query) or 
                query_lower in info.place_name.lower() or
                query_lower in info.state.lower() or
                query_lower in info.district.lower()):
                results.append(info)
                if len(results) >= limit:
                    break
        
        return results
    
    def reverse_geocode(self, lat: float, lng: float) -> Optional[PincodeInfo]:
        """Find the nearest pincode for a given lat/lng coordinate."""
        if not PincodeService._pincode_coords:
            return None
        
        min_dist = float('inf')
        nearest_pincode = None
        
        for plat, plng, pincode in PincodeService._pincode_coords:
            # Haversine distance approximation (good enough for nearest neighbor)
            dist = self._haversine_distance(lat, lng, plat, plng)
            if dist < min_dist:
                min_dist = dist
                nearest_pincode = pincode
        
        if nearest_pincode:
            return PincodeService._pincodes.get(nearest_pincode)
        return None
    
    def _haversine_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate Haversine distance between two points in km."""
        R = 6371  # Earth's radius in km
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def get_distance_to_facility(self, pincode: str, facility_lat: float, facility_lng: float) -> Optional[float]:
        """Calculate distance from pincode centroid to a facility."""
        info = self.get_pincode(pincode)
        if not info:
            return None
        return self._haversine_distance(info.lat, info.lng, facility_lat, facility_lng)
