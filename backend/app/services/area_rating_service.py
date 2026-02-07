"""
Area Rating Service - Computes area ratings based on facility coverage.
"""
from typing import Dict, Any, List, Optional
import math
import os
import json

from app.services.pincode_service import PincodeService, PincodeInfo
from app.services.precompute_service import PrecomputeService
from app.services.dataset_registry import (
    get_datasets_for_type,
    get_weights_for_type,
    calculate_distance_score,
    calculate_grade,
    EMERGENCY_DATASETS,
    LIVING_DATASETS,
)


class AreaRatingService:
    """Service for computing area ratings based on facility proximity."""
    
    CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache", "heatmaps")
    
    def __init__(self):
        self._pincode_service = PincodeService()
        self._precompute_service = PrecomputeService()
        os.makedirs(self.CACHE_DIR, exist_ok=True)
    
    def analyze_by_pincode(
        self, 
        pincode: str, 
        analysis_type: str
    ) -> Dict[str, Any]:
        """
        Analyze an area by pincode.
        
        Args:
            pincode: Indian postal code
            analysis_type: 'emergency' or 'living'
            
        Returns:
            Dictionary with rating information
        """
        # Get pincode info
        pincode_info = self._pincode_service.get_pincode(pincode)
        if not pincode_info:
            raise ValueError(f"Pincode not found: {pincode}")
        
        return self._analyze_location(
            lat=pincode_info.lat,
            lng=pincode_info.lng,
            analysis_type=analysis_type,
            pincode_info=pincode_info,
        )
    
    def analyze_by_location(
        self,
        lat: float,
        lng: float,
        analysis_type: str
    ) -> Dict[str, Any]:
        """
        Analyze an area by lat/lng coordinates.
        
        Args:
            lat: Latitude
            lng: Longitude
            analysis_type: 'emergency' or 'living'
            
        Returns:
            Dictionary with rating information
        """
        # Try to find nearest pincode for context
        pincode_info = self._pincode_service.reverse_geocode(lat, lng)
        
        return self._analyze_location(
            lat=lat,
            lng=lng,
            analysis_type=analysis_type,
            pincode_info=pincode_info,
        )
    
    def _analyze_location(
        self,
        lat: float,
        lng: float,
        analysis_type: str,
        pincode_info: Optional[PincodeInfo] = None,
    ) -> Dict[str, Any]:
        """Core analysis logic for a location."""
        
        datasets = get_datasets_for_type(analysis_type)
        weights = get_weights_for_type(analysis_type)
        
        # Analyze each dataset
        breakdown = {}
        nearest_facilities = []
        
        for dataset in datasets:
            facility = self._precompute_service.get_facility_for_point(
                dataset_name=dataset,
                lat=lat,
                lng=lng,
            )
            
            if facility and facility.get("lat") and facility.get("lng"):
                distance = self._haversine_distance(
                    lat, lng,
                    facility["lat"], facility["lng"]
                )
                score = calculate_distance_score(distance)
                
                breakdown[dataset] = {
                    "score": score,
                    "distance_km": round(distance, 2),
                    "facility_name": facility.get("name"),
                    "weight": weights.get(dataset, 0.0),
                }
                
                nearest_facilities.append({
                    "type": dataset,
                    "name": facility.get("name"),
                    "distance_km": round(distance, 2),
                    "lat": facility.get("lat"),
                    "lng": facility.get("lng"),
                })
            else:
                # No facility found for this dataset
                breakdown[dataset] = {
                    "score": 0,
                    "distance_km": None,
                    "facility_name": None,
                    "weight": weights.get(dataset, 0.0),
                }
        
        # Calculate overall score
        weighted_sum = 0.0
        total_weight = 0.0
        
        for dataset, data in breakdown.items():
            weight = data["weight"]
            if data["score"] > 0:
                weighted_sum += data["score"] * weight
                total_weight += weight
        
        # Normalize by actual total weight used
        overall_score = weighted_sum / total_weight if total_weight > 0 else 0
        grade = calculate_grade(overall_score)
        
        # Sort nearest facilities by distance
        nearest_facilities.sort(key=lambda x: x.get("distance_km") or float('inf'))
        
        # Generate recommendations
        recommendations = self._generate_recommendations(breakdown, analysis_type)
        
        result = {
            "overall_score": round(overall_score, 1),
            "grade": grade,
            "analysis_type": analysis_type,
            "location": {
                "lat": lat,
                "lng": lng,
            },
            "breakdown": breakdown,
            "nearest_facilities": nearest_facilities[:5],  # Top 5 nearest
            "recommendations": recommendations,
        }
        
        if pincode_info:
            result["pincode_info"] = pincode_info.to_dict()
        
        return result
    
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
    
    def _generate_recommendations(
        self,
        breakdown: Dict[str, Dict[str, Any]],
        analysis_type: str
    ) -> List[Dict[str, Any]]:
        """Generate insightful, contextual recommendations based on analysis."""
        recommendations = []
        
        # Categorize facilities by score
        excellent = []  # score >= 80
        good = []       # 60-79
        fair = []       # 40-59
        poor = []       # < 40
        
        for dataset, data in breakdown.items():
            score = data["score"]
            distance = data.get("distance_km")
            name = data.get("facility_name")
            
            entry = {"dataset": dataset, "score": score, "distance": distance, "name": name}
            if score >= 80:
                excellent.append(entry)
            elif score >= 60:
                good.append(entry)
            elif score >= 40:
                fair.append(entry)
            else:
                poor.append(entry)
        
        # Generate insights for poor accessibility areas
        for entry in poor:
            dataset = entry["dataset"]
            distance = entry["distance"]
            priority = "HIGH" if entry["score"] < 20 else "MEDIUM"
            
            # Specific, actionable recommendations with actual data
            if dataset == "hospitals":
                if distance:
                    msg = f"Nearest hospital is {distance:.1f}km away. Keep a first-aid kit and save ambulance numbers (102/108)."
                else:
                    msg = "No hospital found nearby. Consider proximity to healthcare when planning."
            elif dataset == "fire_stations":
                msg = f"Fire response may take longer (~{distance:.1f}km coverage gap). Install smoke detectors and keep fire extinguisher."
            elif dataset == "police_stations":
                msg = f"Police station is {distance:.1f}km away. Save local police helpline and consider home security."
            elif dataset == "blood_banks":
                msg = f"Nearest blood bank is {distance:.1f}km away. Know your blood type and register as a donor."
            elif dataset == "train_stations":
                msg = f"Railway connectivity is limited ({distance:.1f}km). Plan for alternative transport during emergencies."
            elif dataset == "metro_stations":
                msg = f"No metro access within {distance:.1f}km. Budget for cab/auto for daily commute."
            elif dataset == "airports":
                if analysis_type == "emergency":
                    msg = f"Airport is {distance:.1f}km away. May impact air evacuation during disasters."
                else:
                    msg = f"Airport is {distance:.1f}km away. Plan extra travel time for flights."
            elif dataset == "schools":
                msg = f"Nearest school is {distance:.1f}km away. Consider transport arrangements for children."
            elif dataset == "parks":
                msg = f"Green spaces are {distance:.1f}km away. Look for local community gardens or indoor activities."
            elif dataset == "banks":
                msg = f"Banking services are {distance:.1f}km away. Consider using digital banking and UPI."
            elif dataset == "petrol_pumps":
                msg = f"Nearest petrol pump is {distance:.1f}km away. Keep vehicle tank above 25% capacity."
            else:
                clean_name = dataset.replace("_", " ")
                msg = f"Nearest {clean_name} is {distance:.1f}km away, which may affect daily convenience."
            
            recommendations.append({
                "type": dataset,
                "priority": priority,
                "message": msg,
            })
        
        # Add positive highlights if there are excellent facilities
        if excellent and len(recommendations) < 3:
            best = sorted(excellent, key=lambda x: x["distance"] or 999)[0]
            name = best.get("name") or best["dataset"].replace("_", " ")
            if best["distance"] and best["distance"] < 1:
                msg = f"Great location! {name} is just {best['distance']*1000:.0f}m away."
            elif best["distance"]:
                msg = f"Well-connected area with {name} only {best['distance']:.1f}km away."
            else:
                msg = f"Good access to {best['dataset'].replace('_', ' ')} in this area."
            
            recommendations.append({
                "type": "strength",
                "priority": "LOW",
                "message": msg,
            })
        
        # Comparative insight
        total_score = sum(d["score"] for d in breakdown.values()) / len(breakdown) if breakdown else 0
        if total_score >= 75 and not poor:
            recommendations.append({
                "type": "overall",
                "priority": "LOW", 
                "message": f"Excellent area! Better than 80% of locations for {analysis_type.replace('_', ' ')} readiness.",
            })
        elif total_score >= 50 and len(poor) <= 2:
            weak_areas = ", ".join([p["dataset"].replace("_", " ") for p in poor[:2]])
            recommendations.append({
                "type": "summary",
                "priority": "LOW",
                "message": f"Decent area overall. Main gaps: {weak_areas}." if weak_areas else "Balanced facility coverage.",
            })
        
        return recommendations[:4]  # Limit to 4 most relevant recommendations

    def get_heatmap_data(self, analysis_type: str) -> List[Dict[str, Any]]:
        """
        Get precomputed heatmap data for all pincodes.
        Uses a cache to avoid recomputing every time.
        """
        cache_path = os.path.join(self.CACHE_DIR, f"{analysis_type}.json")
        
        # Check cache (valid for 24 hours or just check existence for now)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error reading heatmap cache: {e}")
        
        # If not cached, compute for all pincodes
        print(f"Computing heatmap for {analysis_type}...")
        
        # Load datasets and build KDTrees for speed
        from scipy.spatial import KDTree
        import numpy as np
        
        datasets = get_datasets_for_type(analysis_type)
        weights = get_weights_for_type(analysis_type)
        
        dataset_trees = {}
        for dataset in datasets:
            facilities = self._precompute_service.load_dataset(dataset)
            if facilities:
                coords = np.array([[f["lat"], f["lng"]] for f in facilities])
                dataset_trees[dataset] = {
                    "tree": KDTree(coords),
                    "weight": weights.get(dataset, 0.0)
                }
        
        if not dataset_trees:
            print(f"No facilities found for {analysis_type}")
            return []
            
        heatmap_points = []
        
        # Get all pincodes from service
        pincodes = self._pincode_service._pincodes
        total = len(pincodes)
        count = 0
        
        print(f"Processing {total} pincodes using KDTree...")
        
        for pincode, info in pincodes.items():
            count += 1
            if count % 5000 == 0 or count == 1:
                print(f"Heatmap progress ({analysis_type}): {count}/{total} ({(count/total*100):.1f}%)")
            
            try:
                weighted_sum = 0.0
                total_weight = 0.0
                
                for dataset, data in dataset_trees.items():
                    tree = data["tree"]
                    weight = data["weight"]
                    
                    # Query KDTree for nearest point
                    # d is Euclidean distance in degrees (approximate but enough for rating)
                    d, idx = tree.query([info.lat, info.lng])
                    
                    # Convert degree distance to approximate km (1 degree ~ 111km)
                    distance_km = d * 111.0
                    
                    score = calculate_distance_score(distance_km)
                    weighted_sum += score * weight
                    total_weight += weight
                
                overall_score = weighted_sum / total_weight if total_weight > 0 else 0
                
                if overall_score > 0:
                    heatmap_points.append({
                        "lat": info.lat,
                        "lng": info.lng,
                        "weight": round(overall_score / 100.0, 3)
                    })
            except Exception as e:
                continue
        
        print(f"Heatmap computation for {analysis_type} complete! Generated {len(heatmap_points)} points.")
        # Cache the result
        try:
            with open(cache_path, 'w') as f:
                json.dump(heatmap_points, f)
            print(f"Heatmap for {analysis_type} cached to {cache_path}")
        except Exception as e:
            print(f"Error caching heatmap: {e}")
            
        return heatmap_points


def calculate_distance_score(distance: float) -> int:
    """Calculate a score (0-100) based on distance."""
    if distance < 2: return 100
    if distance < 5: return 80
    if distance < 10: return 60
    if distance < 20: return 40
    if distance < 40: return 20
    return 10
