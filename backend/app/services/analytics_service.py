"""
Analytics Service - Geometric analysis for facility coverage insights.

Provides:
- Minimum Enclosing Circle (MEC): Smallest circle containing all facilities
- Largest Empty Circle: Identifies underserved areas
- Overburdened/Underserved facility analysis
"""
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
from scipy.spatial import Voronoi, Delaunay
from shapely.geometry import Point, Polygon, MultiPolygon
from shapely.ops import unary_union
import geopandas as gpd
import pyproj
import time


class AnalyticsService:
    """
    Provides geometric analytics for facility coverage analysis.
    """
    
    # Coordinate reference systems
    CRS_WGS84 = "EPSG:4326"
    CRS_PROJECTED = "EPSG:32644"  # UTM zone 44N (covers central India)
    
    def __init__(self):
        self.wgs84 = pyproj.CRS(self.CRS_WGS84)
        self.projected = pyproj.CRS(self.CRS_PROJECTED)
        
        self.to_projected = pyproj.Transformer.from_crs(
            self.wgs84, self.projected, always_xy=True
        )
        self.to_wgs84 = pyproj.Transformer.from_crs(
            self.projected, self.wgs84, always_xy=True
        )
    
    def _project_coords(self, coords: List[Tuple[float, float]]) -> np.ndarray:
        """Project WGS84 (lng, lat) coordinates to UTM"""
        projected = []
        for lng, lat in coords:
            x, y = self.to_projected.transform(lng, lat)
            projected.append([x, y])
        return np.array(projected)
    
    def _unproject_point(self, x: float, y: float) -> Tuple[float, float]:
        """Unproject UTM coordinates back to WGS84 (lng, lat)"""
        lng, lat = self.to_wgs84.transform(x, y)
        return (lng, lat)
    
    def compute_minimum_enclosing_circle(
        self, 
        coords: List[Tuple[float, float]]
    ) -> Dict[str, Any]:
        """
        Compute the Minimum Enclosing Circle (MEC) for a set of points.
        Uses Welzl's algorithm via iterative approach.
        
        Args:
            coords: List of (longitude, latitude) tuples
            
        Returns:
            Dictionary with center (lng, lat) and radius in km
        """
        if len(coords) < 1:
            return {"center": None, "radius_km": 0}
        
        if len(coords) == 1:
            return {"center": list(coords[0]), "radius_km": 0}
        
        # Project to UTM for accurate distance calculations
        projected = self._project_coords(coords)
        
        # Use Welzl's algorithm (iterative version)
        center, radius = self._welzl_mec(projected)
        
        # Convert center back to WGS84
        center_wgs84 = self._unproject_point(center[0], center[1])
        
        return {
            "center": [center_wgs84[0], center_wgs84[1]],
            "radius_km": radius / 1000  # Convert meters to km
        }
    
    def _welzl_mec(self, points: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Welzl's algorithm for minimum enclosing circle.
        Returns (center, radius) in projected coordinates.
        Implemented iteratively to avoid RecursionError for large datasets.
        """
        def circle_from_two_points(p1, p2):
            center = (p1 + p2) / 2
            radius = np.linalg.norm(p1 - p2) / 2
            return center, radius

        def point_in_circle(p, center, radius):
            if center is None: return False
            return np.linalg.norm(p - center) <= radius * 1.0001

        # Shuffle points for expected O(n) performance
        pts = points.copy()
        np.random.shuffle(pts)
        n = len(pts)
        
        if n == 0: return np.array([0.0, 0.0]), 0.0
        if n == 1: return pts[0], 0.0
        
        center, radius = circle_from_two_points(pts[0], pts[1])
        
        for i in range(2, n):
            if not point_in_circle(pts[i], center, radius):
                center, radius = self._mec_with_one_point(pts[:i], pts[i])
        
        return center, radius

    def _mec_with_one_point(self, pts, q) -> Tuple[np.ndarray, float]:
        def circle_from_two_points(p1, p2):
            center = (p1 + p2) / 2
            radius = np.linalg.norm(p1 - p2) / 2
            return center, radius
        
        def point_in_circle(p, center, radius):
            return np.linalg.norm(p - center) <= radius * 1.0001

        center, radius = circle_from_two_points(pts[0], q)
        for i in range(1, len(pts)):
            if not point_in_circle(pts[i], center, radius):
                center, radius = self._mec_with_two_points(pts[:i], pts[i], q)
        return center, radius

    def _mec_with_two_points(self, pts, q1, q2) -> Tuple[np.ndarray, float]:
        def circle_from_two_points(p1, p2):
            center = (p1 + p2) / 2
            radius = np.linalg.norm(p1 - p2) / 2
            return center, radius
        
        def circle_from_three_points(p1, p2, p3):
            ax, ay = p1
            bx, by = p2
            cx, cy = p3
            d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
            if abs(d) < 1e-10:
                dists = [
                    (np.linalg.norm(p1 - p2), p1, p2),
                    (np.linalg.norm(p2 - p3), p2, p3),
                    (np.linalg.norm(p1 - p3), p1, p3)
                ]
                max_dist = max(dists, key=lambda x: x[0])
                return circle_from_two_points(max_dist[1], max_dist[2])
            ux = ((ax*ax + ay*ay) * (by - cy) + (bx*bx + by*by) * (cy - ay) + (cx*cx + cy*cy) * (ay - by)) / d
            uy = ((ax*ax + ay*ay) * (cx - bx) + (bx*bx + by*by) * (ax - cx) + (cx*cx + cy*cy) * (bx - ax)) / d
            center = np.array([ux, uy])
            radius = np.linalg.norm(p1 - center)
            return center, radius

        def point_in_circle(p, center, radius):
            return np.linalg.norm(p - center) <= radius * 1.0001

        center, radius = circle_from_two_points(q1, q2)
        for i in range(len(pts)):
            if not point_in_circle(pts[i], center, radius):
                center, radius = circle_from_three_points(pts[i], q1, q2)
        return center, radius
    
    def find_largest_empty_circle(
        self,
        facility_coords: List[Tuple[float, float]],
        boundary_geom: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Find the largest circle that contains no facilities.
        Uses Voronoi diagram to find candidate centers.
        
        The largest empty circle center must be at a Voronoi vertex
        or on the boundary of the region.
        
        Args:
            facility_coords: List of facility (longitude, latitude) tuples
            boundary_geom: Optional Shapely geometry (Polygon/MultiPolygon)
            
        Returns:
            Dictionary with center (lng, lat) and radius in km
        """
        if len(facility_coords) < 3:
            return {"center": None, "radius_km": 0, "message": "Need at least 3 facilities"}
        
        # Project coordinates
        projected = self._project_coords(facility_coords)
        
        # Project boundary if provided
        boundary_projected = None
        if boundary_geom:
            try:
                # Convert geometry to GeoSeries to project easily
                gs = gpd.GeoSeries([boundary_geom], crs="EPSG:4326")
                gs_proj = gs.to_crs(self.CRS_PROJECTED)
                boundary_projected = gs_proj.iloc[0]
            except Exception as e:
                print(f"Error projecting boundary for LEC: {e}")

        try:
            # Compute Voronoi diagram
            vor = Voronoi(projected)
            
            # Find the vertex farthest from all facilities
            best_center = None
            best_radius = 0
            
            for vertex in vor.vertices:
                # IMPORTANT: Circle center must be within the boundary if provided
                if boundary_projected and not boundary_projected.contains(Point(vertex)):
                    continue

                # Calculate distance to nearest facility
                distances = np.linalg.norm(projected - vertex, axis=1)
                min_dist = np.min(distances)
                
                if min_dist > best_radius:
                    best_radius = min_dist
                    best_center = vertex
        except Exception as e:
            return {"center": None, "radius_km": 0, "message": f"Could not compute Voronoi: {str(e)}"}
        
        if best_center is None:
            return {"center": None, "radius_km": 0}
        
        # Convert back to WGS84
        center_wgs84 = self._unproject_point(best_center[0], best_center[1])
        
        return {
            "center": [center_wgs84[0], center_wgs84[1]],
            "radius_km": best_radius / 1000
        }
    
    def find_optimal_facility_location(
        self,
        facility_coords: List[Tuple[float, float]],
        boundary_geom: Optional[Any] = None,
        districts_gdf: Optional[gpd.GeoDataFrame] = None
    ) -> Dict[str, Any]:
        """
        Find the optimal location for a new facility based on population impact.
        Uses Voronoi vertices as candidate locations and scores each by
        the population that would be within its catchment area.
        
        Args:
            facility_coords: List of existing facility (lng, lat) tuples
            boundary_geom: Optional boundary geometry (Polygon) to constrain search
            districts_gdf: GeoDataFrame with district boundaries and population data
            
        Returns:
            Dictionary with optimal location, estimated population, and reasoning
        """
        if len(facility_coords) < 3:
            return {"success": False, "message": "Need at least 3 facilities"}
        
        if districts_gdf is None:
            # Try to load from PopulationService
            try:
                from app.services.population_calc import PopulationService
                pop_service = PopulationService()
                districts_gdf = pop_service._districts_gdf
            except Exception as e:
                return {"success": False, "message": f"Could not load population data: {e}"}
        
        if districts_gdf is None or len(districts_gdf) == 0:
            return {"success": False, "message": "No district population data available"}
        
        # Project coordinates
        projected = self._project_coords(facility_coords)
        
        # Project boundary if provided
        boundary_projected = None
        if boundary_geom:
            try:
                gs = gpd.GeoSeries([boundary_geom], crs="EPSG:4326")
                gs_proj = gs.to_crs(self.CRS_PROJECTED)
                boundary_projected = gs_proj.iloc[0]
            except Exception as e:
                print(f"Error projecting boundary: {e}")
        
        # Project districts
        try:
            districts_proj = districts_gdf.to_crs(self.CRS_PROJECTED)
        except Exception as e:
            return {"success": False, "message": f"Error projecting districts: {e}"}
        
        try:
            # Compute Voronoi diagram
            vor = Voronoi(projected)
            
            candidates = []
            
            for vertex in vor.vertices:
                # Must be within boundary if provided
                if boundary_projected and not boundary_projected.contains(Point(vertex)):
                    continue
                
                # Calculate distance to nearest facility (catchment radius)
                distances = np.linalg.norm(projected - vertex, axis=1)
                radius = np.min(distances)
                
                # Skip very small radii
                if radius < 1000:  # Less than 1km
                    continue
                
                # Create catchment circle
                catchment = Point(vertex).buffer(radius)
                
                # Calculate population in catchment area
                total_pop = 0
                intersecting = districts_proj.sindex.query(catchment, predicate='intersects')
                
                for idx in intersecting:
                    district = districts_proj.iloc[idx]
                    intersection = catchment.intersection(district.geometry)
                    if not intersection.is_empty:
                        # Weighted population based on area overlap
                        if district.geometry.area > 0:
                            ratio = intersection.area / district.geometry.area
                            pop = district.get('population', 0) or 0
                            total_pop += pop * ratio
                
                candidates.append({
                    'center_proj': vertex,
                    'radius_m': radius,
                    'population': total_pop
                })
            
            if not candidates:
                return {"success": False, "message": "No valid candidate locations found within boundary"}
            
            # Sort by population (highest first)
            candidates.sort(key=lambda x: x['population'], reverse=True)
            best = candidates[0]
            
            # Convert back to WGS84
            center_wgs84 = self._unproject_point(best['center_proj'][0], best['center_proj'][1])
            
            return {
                "success": True,
                "optimal_location": {
                    "lng": center_wgs84[0],
                    "lat": center_wgs84[1]
                },
                "catchment_radius_km": round(best['radius_m'] / 1000, 2),
                "estimated_population": int(best['population']),
                "candidates_evaluated": len(candidates),
                "top_alternatives": [
                    {
                        "lng": self._unproject_point(c['center_proj'][0], c['center_proj'][1])[0],
                        "lat": self._unproject_point(c['center_proj'][0], c['center_proj'][1])[1],
                        "population": int(c['population'])
                    }
                    for c in candidates[1:4]  # Top 3 alternatives
                ]
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "message": f"Error computing optimal location: {e}"}
    
    def find_nearest_facility_index(
        self,
        click_coords: Tuple[float, float],
        facility_coords: List[Tuple[float, float]]
    ) -> int:
        """
        Find the index of the facility nearest to the clicked point.
        
        Args:
            click_coords: (longitude, latitude) of click location
            facility_coords: List of facility (longitude, latitude) tuples
            
        Returns:
            Index of nearest facility
        """
        if len(facility_coords) == 0:
            return -1
        
        # Project all coordinates
        click_projected = self._project_coords([click_coords])[0]
        facilities_projected = self._project_coords(facility_coords)
        
        # Find nearest
        distances = np.linalg.norm(facilities_projected - click_projected, axis=1)
        return int(np.argmin(distances))
    
    def compute_facility_insights(
        self,
        voronoi_features: List[Dict[str, Any]],
        facilities: List[Dict[str, Any]],
        boundary_geom: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Compute comprehensive insights about facility coverage.
        
        Args:
            voronoi_features: GeoJSON features from Voronoi computation
            facilities: List of facility dictionaries with lat, lng, name
            boundary_geom: Optional boundary geometry to filter by
            
        Returns:
            Dictionary with various insights
        """
        insights = {
            "most_overburdened": [],
            "most_underserved": [],
            "coverage_stats": {
                "total_population": 0,
                "total_area_sq_km": 0,
                "avg_population_per_facility": 0,
                "avg_area_per_facility": 0,
                "facility_count": 0
            },
            "minimum_enclosing_circle": {"center": None, "radius_km": 0},
            "largest_empty_circle": {"center": None, "radius_km": 0},
            "recommendations": []
        }
        
        # 1. Filter facilities by boundary if provided (VECTORIZED)
        filtered_facilities = facilities
        filtered_indices = list(range(len(facilities)))
        
        if boundary_geom:
            start_filter = time.time()
            # Apply a small buffer (approx 1km) to handle points exactly on the border/coast
            robust_boundary = boundary_geom.buffer(0.01) if hasattr(boundary_geom, 'buffer') else boundary_geom
            
            # Use GeoPandas for vectorized filtering
            lats = [f.get("lat") for f in facilities]
            lngs = [f.get("lng") for f in facilities]
            points = gpd.points_from_xy(lngs, lats)
            gdf = gpd.GeoDataFrame(geometry=points, crs="EPSG:4326")
            
            # Mask of points inside boundary
            mask = gdf.within(robust_boundary)
            filtered_indices = np.where(mask)[0].tolist()
            filtered_facilities = [facilities[i] for i in filtered_indices]
            
            print(f"Vectorized filtering took {time.time() - start_filter:.4f}s")
            print(f"Filtered facilities: {len(filtered_facilities)} of {len(facilities)} inside buffered boundary")

        # 2. Extract features with population data
        # Use a set of filtered IDs for O(1) matching
        filtered_ids = {str(f.get("id", i)) for i, f in zip(filtered_indices, filtered_facilities)}
        
        features_with_data = []
        for feature in voronoi_features:
            props = feature.get("properties", {})
            fid = str(props.get("facility_id"))
            
            if fid in filtered_ids:
                if props.get("population") and props.get("area_sq_km"):
                    pop = props["population"]
                    area = props["area_sq_km"]
                    features_with_data.append({
                        "name": props.get("name", "Unknown"),
                        "facility_id": fid,
                        "population": pop,
                        "area_sq_km": area,
                        "density": pop / area if area > 0 else 0,
                        "lat": props.get("centroid_lat"),
                        "lng": props.get("centroid_lng")
                    })
        
        if not features_with_data:
            return insights
        
        # Sort by population (overburdened = high population)
        by_population = sorted(features_with_data, key=lambda x: x["population"], reverse=True)
        insights["most_overburdened"] = by_population[:5]
        
        # Sort by area (underserved = large area per facility)
        by_area = sorted(features_with_data, key=lambda x: x["area_sq_km"], reverse=True)
        insights["most_underserved"] = by_area[:5]
        
        # Coverage statistics
        total_pop = sum(f["population"] for f in features_with_data)
        total_area = sum(f["area_sq_km"] for f in features_with_data)
        
        insights["coverage_stats"] = {
            "total_population": total_pop,
            "total_area_sq_km": total_area,
            "avg_population_per_facility": total_pop / len(features_with_data) if features_with_data else 0,
            "avg_area_per_facility": total_area / len(features_with_data) if features_with_data else 0,
            "facility_count": len(features_with_data)
        }
        
        # Compute enclosing circles if we have facility coordinates
        if filtered_facilities:
            coords = [(f.get("lng"), f.get("lat")) for f in filtered_facilities if f.get("lng") and f.get("lat")]
            if len(coords) >= 1:
                insights["minimum_enclosing_circle"] = self.compute_minimum_enclosing_circle(coords)
            if len(coords) >= 3:
                insights["largest_empty_circle"] = self.find_largest_empty_circle(coords, boundary_geom)
        
        # Generate Prescriptive Recommendations
        self._generate_recommendations(insights)
        
        return insights

    def _generate_recommendations(self, insights: Dict[str, Any]):
        """
        AI-like prescriptive suggestions based on computed metrics.
        """
        recs = []
        stats = insights.get("coverage_stats", {})
        
        # 1. Underserved area recommendation
        empty_circle = insights.get("largest_empty_circle", {})
        if empty_circle.get("radius_km", 0) > 10:  # Threshold of 10km gap
            radius = empty_circle["radius_km"]
            center = empty_circle["center"]
            recs.append({
                "type": "CRITICAL_GAP",
                "priority": "HIGH" if radius > 25 else "MEDIUM",
                "message": f"Critical coverage gap detected! There is a {radius:.1f}km radius area without any facility.",
                "action": "Consider placing a new facility at the suggested orange marker to optimize coverage.",
                "coords": center
            })
            
        # 2. Overburdened facility recommendation
        overburdened = insights.get("most_overburdened", [])
        if overburdened:
            top = overburdened[0]
            avg = stats.get("avg_population_per_facility", 0)
            if top["population"] > avg * 2:
                recs.append({
                    "type": "OVERBURDENED",
                    "priority": "HIGH",
                    "message": f"Facility '{top['name']}' is serving {top['population']:,} people, which is {top['population']/avg:.1f}x the average.",
                    "action": f"Add a nearby facility to relieve pressure from {top['name']}.",
                    "coords": [top["lng"], top["lat"]]
                })
        
        # 3. Overall efficiency
        count = stats.get("facility_count", 0)
        total_pop = stats.get("total_population", 0)
        if count > 0 and total_pop > 0:
            avg_pop = total_pop / count
            if avg_pop > 1000000: # Over 1M people per facility
                recs.append({
                    "type": "CAPACITY",
                    "priority": "MEDIUM",
                    "message": "Average population per facility is very high (>1M).",
                    "action": "Scale up infrastructure across the region."
                })

        insights["recommendations"] = recs
