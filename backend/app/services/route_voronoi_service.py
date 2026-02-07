"""
Route Voronoi Engine - Computes Voronoi diagrams based on road network distance.

Uses a candidate-filtered approach:
1. Filter: Use DCEL k-NN to get candidate facilities by Euclidean distance
2. Refine: Query routing API for road distance to candidates
3. Assign: Pick nearest by road distance
4. Interpolate: Generate polygons from grid point assignments
"""

import asyncio
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from shapely.geometry import Point, Polygon, MultiPolygon, shape
from shapely.ops import unary_union
from scipy.spatial import Delaunay
import numpy as np

from .dcel import DCEL, DCELFace, get_current_dcel
from .routing_service import RoutingService, RouteResult, get_routing_service

logger = logging.getLogger(__name__)


@dataclass
class GridPointAssignment:
    """Assignment of a grid point to a facility with route distance metrics."""
    lat: float
    lng: float
    facility_id: str
    facility_name: str
    route_distance_km: float
    route_duration_min: float
    euclidean_distance_km: float
    distortion_ratio: float  # route / euclidean
    confidence: float  # 1.0 if clear winner, <1.0 if ambiguous
    k_used: int
    connected: bool  # True if route exists


@dataclass 
class RouteVoronoiConfig:
    """Configuration for route Voronoi computation."""
    grid_density: int = 50  # Points per axis within bounding box
    base_k: int = 5  # Base number of candidates
    adaptive_k: bool = True  # Whether to expand k based on distortion
    distortion_threshold: float = 3.0  # Ratio for k expansion
    connectivity_check: bool = True  # Check route connectivity
    confidence_threshold: float = 0.3  # Below this marks as ambiguous


@dataclass
class RouteVoronoiResult:
    """Result of route Voronoi computation."""
    type: str = "route_voronoi"
    computation_method: str = ""
    grid_size: int = 0
    total_route_queries: int = 0
    computation_time_sec: float = 0.0
    features: List[Dict] = field(default_factory=list)
    assignments: List[GridPointAssignment] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


class RouteVoronoiEngine:
    """
    Computes Voronoi diagrams based on road network distance.
    
    Algorithm:
    1. Generate uniform grid of sample points within boundary
    2. For each grid point, get k nearest facilities (Euclidean filter)
    3. Query routing API for road distance to k candidates
    4. Assign grid point to facility with minimum road distance
    5. Interpolate grid point assignments into polygons
    """
    
    def __init__(self, dcel: Optional[DCEL] = None, routing: Optional[RoutingService] = None):
        self.dcel = dcel or get_current_dcel()
        self.routing = routing or get_routing_service()
        self._cache: Dict[str, RouteResult] = {}  # Cache route results
    
    def _generate_grid(self, boundary: Polygon, density: int) -> List[Tuple[float, float]]:
        """
        Generate uniform grid of points within boundary.
        
        Args:
            boundary: Shapely Polygon defining the region
            density: Number of points along each axis
            
        Returns:
            List of (lat, lng) tuples for grid points within boundary
        """
        minx, miny, maxx, maxy = boundary.bounds
        
        x_coords = np.linspace(minx, maxx, density)
        y_coords = np.linspace(miny, maxy, density)
        
        grid_points = []
        for y in y_coords:
            for x in x_coords:
                point = Point(x, y)
                if boundary.contains(point):
                    grid_points.append((y, x))  # (lat, lng)
        
        return grid_points
    
    def _cache_key(self, origin: Tuple[float, float], dest: Tuple[float, float]) -> str:
        """Generate cache key for route query."""
        return f"{origin[0]:.5f},{origin[1]:.5f}->{dest[0]:.5f},{dest[1]:.5f}"
    
    def _euclidean_distance_km(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate approximate Euclidean distance in km."""
        # Approximate degrees to km at Indian latitudes (~20-30°N)
        lat_km = abs(lat2 - lat1) * 111.0
        lng_km = abs(lng2 - lng1) * 111.0 * 0.866  # cos(25°) ≈ 0.866
        return (lat_km ** 2 + lng_km ** 2) ** 0.5
    
    def _assign_grid_point_sync(
        self,
        lat: float,
        lng: float,
        config: RouteVoronoiConfig
    ) -> GridPointAssignment:
        """
        Assign a single grid point to nearest facility by road distance.
        
        Synchronous version for use in non-async contexts.
        """
        if not self.dcel:
            raise ValueError("DCEL not initialized")
        
        # Get candidate facilities using DCEL k-NN
        if config.adaptive_k:
            k_used, candidates = self.dcel.adaptive_k(
                lat, lng, 
                base_k=config.base_k,
                distortion_threshold=config.distortion_threshold
            )
        else:
            k_used = config.base_k
            candidates = self.dcel.k_nearest_neighbors(lat, lng, k=config.base_k)
        
        if not candidates:
            return GridPointAssignment(
                lat=lat, lng=lng,
                facility_id="unknown", facility_name="Unknown",
                route_distance_km=float('inf'), route_duration_min=float('inf'),
                euclidean_distance_km=float('inf'), distortion_ratio=1.0,
                confidence=0.0, k_used=k_used, connected=False
            )
        
        # Get facility locations
        destinations = []
        facility_info = []
        for face in candidates:
            centroid = self.dcel.get_facility_centroid(face.facility_id)
            if centroid:
                destinations.append(centroid)
                facility_info.append((face.facility_id, face.facility_name))
        
        if not destinations:
            # Fall back to first candidate
            face = candidates[0]
            return GridPointAssignment(
                lat=lat, lng=lng,
                facility_id=face.facility_id, facility_name=face.facility_name,
                route_distance_km=float('inf'), route_duration_min=float('inf'),
                euclidean_distance_km=0.0, distortion_ratio=1.0,
                confidence=0.5, k_used=k_used, connected=False
            )
        
        # Query routing API for distances
        route_results = self.routing.batch_distance_sync(lat, lng, destinations)
        
        # Find nearest by route distance
        best_idx = 0
        best_distance = float('inf')
        second_best_distance = float('inf')
        
        for i, result in enumerate(route_results):
            if result.connected and result.distance_km < best_distance:
                second_best_distance = best_distance
                best_distance = result.distance_km
                best_idx = i
            elif result.connected and result.distance_km < second_best_distance:
                second_best_distance = result.distance_km
        
        best_result = route_results[best_idx]
        best_facility = facility_info[best_idx]
        
        # Calculate Euclidean distance
        dest = destinations[best_idx]
        euclidean_km = self._euclidean_distance_km(lat, lng, dest[0], dest[1])
        
        # Calculate distortion ratio
        distortion = best_result.distance_km / euclidean_km if euclidean_km > 0 else 1.0
        
        # Calculate confidence (based on gap to second best)
        if second_best_distance < float('inf') and best_distance < float('inf'):
            gap_ratio = (second_best_distance - best_distance) / best_distance if best_distance > 0 else 1.0
            confidence = min(1.0, gap_ratio)  # Higher gap = higher confidence
        else:
            confidence = 1.0 if best_result.connected else 0.0
        
        return GridPointAssignment(
            lat=lat, lng=lng,
            facility_id=best_facility[0], facility_name=best_facility[1],
            route_distance_km=best_result.distance_km,
            route_duration_min=best_result.duration_min,
            euclidean_distance_km=euclidean_km,
            distortion_ratio=distortion,
            confidence=confidence,
            k_used=k_used,
            connected=best_result.connected
        )
    
    def _interpolate_polygons(
        self, 
        assignments: List[GridPointAssignment],
        boundary: Polygon
    ) -> Dict[str, Polygon]:
        """
        Interpolate grid point assignments into polygons using Delaunay triangulation.
        
        Args:
            assignments: List of grid point assignments
            boundary: Original boundary for clipping
            
        Returns:
            Dict mapping facility_id to Polygon
        """
        if len(assignments) < 3:
            return {}
        
        # Extract points and facility assignments
        points = np.array([[a.lng, a.lat] for a in assignments])
        facility_ids = [a.facility_id for a in assignments]
        
        # Compute Delaunay triangulation
        try:
            tri = Delaunay(points)
        except Exception as e:
            logger.error(f"Delaunay triangulation failed: {e}")
            return {}
        
        # Group triangles by majority facility
        facility_triangles: Dict[str, List[Polygon]] = {}
        
        for simplex in tri.simplices:
            # Get facility IDs for triangle vertices
            vertex_facilities = [facility_ids[i] for i in simplex]
            
            # Majority vote
            from collections import Counter
            majority_facility = Counter(vertex_facilities).most_common(1)[0][0]
            
            # Create triangle polygon
            triangle_coords = points[simplex].tolist()
            triangle_coords.append(triangle_coords[0])  # Close the ring
            triangle = Polygon(triangle_coords)
            
            if majority_facility not in facility_triangles:
                facility_triangles[majority_facility] = []
            facility_triangles[majority_facility].append(triangle)
        
        # Dissolve triangles into facility polygons
        facility_polygons = {}
        for facility_id, triangles in facility_triangles.items():
            try:
                merged = unary_union(triangles)
                # Clip to boundary
                clipped = merged.intersection(boundary)
                if not clipped.is_empty:
                    facility_polygons[facility_id] = clipped
            except Exception as e:
                logger.error(f"Failed to merge triangles for {facility_id}: {e}")
        
        return facility_polygons
    
    def compute_sync(
        self,
        boundary: Polygon,
        config: Optional[RouteVoronoiConfig] = None
    ) -> RouteVoronoiResult:
        """
        Compute route-based Voronoi diagram synchronously.
        
        Args:
            boundary: Shapely Polygon defining the region
            config: Configuration options
            
        Returns:
            RouteVoronoiResult with features and metadata
        """
        import time
        start_time = time.time()
        
        config = config or RouteVoronoiConfig()
        
        if not self.dcel:
            raise ValueError("DCEL not initialized. Compute Euclidean Voronoi first.")
        
        # Generate grid points
        grid_points = self._generate_grid(boundary, config.grid_density)
        logger.info(f"Generated {len(grid_points)} grid points")
        
        # Assign each grid point
        assignments = []
        total_queries = 0
        
        for i, (lat, lng) in enumerate(grid_points):
            if i % 100 == 0:
                logger.info(f"Processing grid point {i}/{len(grid_points)}")
            
            assignment = self._assign_grid_point_sync(lat, lng, config)
            assignments.append(assignment)
            total_queries += assignment.k_used
        
        # Interpolate into polygons
        facility_polygons = self._interpolate_polygons(assignments, boundary)
        
        # Build GeoJSON features
        features = []
        for facility_id, polygon in facility_polygons.items():
            # Get facility info from DCEL
            face = self.dcel.get_face_by_facility_id(facility_id)
            
            # Calculate metrics for this facility
            facility_assignments = [a for a in assignments if a.facility_id == facility_id]
            avg_route_dist = np.mean([a.route_distance_km for a in facility_assignments]) if facility_assignments else 0
            max_route_dist = max([a.route_distance_km for a in facility_assignments]) if facility_assignments else 0
            avg_distortion = np.mean([a.distortion_ratio for a in facility_assignments]) if facility_assignments else 1.0
            avg_confidence = np.mean([a.confidence for a in facility_assignments]) if facility_assignments else 1.0
            
            feature = {
                "type": "Feature",
                "properties": {
                    "facility_id": facility_id,
                    "facility_name": face.facility_name if face else facility_id,
                    "cell_type": "route_based",
                    "avg_route_distance_km": round(avg_route_dist, 2),
                    "max_route_distance_km": round(max_route_dist, 2),
                    "avg_distortion_ratio": round(avg_distortion, 2),
                    "avg_confidence": round(avg_confidence, 2),
                    "grid_points_count": len(facility_assignments),
                    "original_properties": face.properties if face else {}
                },
                "geometry": {
                    "type": polygon.geom_type,
                    "coordinates": self._polygon_to_geojson_coords(polygon)
                }
            }
            features.append(feature)
        
        computation_time = time.time() - start_time
        
        # Calculate summary metrics
        all_distortions = [a.distortion_ratio for a in assignments if a.connected]
        all_confidences = [a.confidence for a in assignments]
        disconnected_count = sum(1 for a in assignments if not a.connected)
        ambiguous_count = sum(1 for a in assignments if a.confidence < config.confidence_threshold)
        
        return RouteVoronoiResult(
            type="route_voronoi",
            computation_method=f"candidate_filtered_k{config.base_k}{'_adaptive' if config.adaptive_k else ''}",
            grid_size=len(grid_points),
            total_route_queries=total_queries,
            computation_time_sec=round(computation_time, 2),
            features=features,
            assignments=assignments,
            metadata={
                "avg_distortion_ratio": round(np.mean(all_distortions), 2) if all_distortions else 1.0,
                "max_distortion_ratio": round(max(all_distortions), 2) if all_distortions else 1.0,
                "avg_confidence": round(np.mean(all_confidences), 2) if all_confidences else 1.0,
                "disconnected_count": disconnected_count,
                "ambiguous_count": ambiguous_count,
                "config": {
                    "grid_density": config.grid_density,
                    "base_k": config.base_k,
                    "adaptive_k": config.adaptive_k,
                    "distortion_threshold": config.distortion_threshold
                }
            }
        )
    
    def _polygon_to_geojson_coords(self, polygon) -> List:
        """Convert Shapely polygon to GeoJSON coordinates."""
        if polygon.geom_type == 'Polygon':
            return [list(polygon.exterior.coords)]
        elif polygon.geom_type == 'MultiPolygon':
            return [[list(p.exterior.coords)] for p in polygon.geoms]
        return []
    
    def to_geojson(self, result: RouteVoronoiResult) -> Dict:
        """Convert result to GeoJSON FeatureCollection."""
        return {
            "type": "FeatureCollection",
            "properties": {
                "computation_method": result.computation_method,
                "grid_size": result.grid_size,
                "total_route_queries": result.total_route_queries,
                "computation_time_sec": result.computation_time_sec,
                **result.metadata
            },
            "features": result.features
        }


# Global engine instance
_route_voronoi_engine: Optional[RouteVoronoiEngine] = None


def get_route_voronoi_engine() -> RouteVoronoiEngine:
    """Get or create the global route Voronoi engine."""
    global _route_voronoi_engine
    if _route_voronoi_engine is None:
        _route_voronoi_engine = RouteVoronoiEngine()
    return _route_voronoi_engine


def reset_route_voronoi_engine():
    """Reset the global engine (e.g., when DCEL changes)."""
    global _route_voronoi_engine
    _route_voronoi_engine = None
