"""
Dominating-Set Road Voronoi Engine

Implements a 5-step algorithm to reshape Voronoi cells using road network distances:
1. Euclidean Voronoi + adjacency graph
2. Greedy dominating set selection  
3. Local region definition (1-hop neighborhoods)
4. Batched OSRM queries for road distance reassignment
5. Global grid merge and polygon interpolation
"""

import logging
import time
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
import numpy as np
from scipy.spatial import Voronoi, Delaunay
from shapely.geometry import Point, Polygon, MultiPolygon
from shapely.ops import unary_union
from collections import defaultdict

from .voronoi_engine import VoronoiEngine
from .dcel import DCEL, DCELFace, set_current_dcel
from .routing_service import RoutingService, get_routing_service

logger = logging.getLogger(__name__)


@dataclass
class DominatingVoronoiConfig:
    """Configuration for dominating-set road Voronoi computation."""
    grid_density: int = 50  # Points per axis within each region
    grid_step_m: float = 2000.0  # Grid step in meters (alternative to density)
    use_step_size: bool = False  # If True, use grid_step_m instead of grid_density
    batch_size: int = 100  # Max sources per OSRM /table query
    margin_threshold: float = 0.1  # Only overwrite if winner differs by this ratio


@dataclass
class DominatingVoronoiResult:
    """Result of dominating-set road Voronoi computation."""
    type: str = "dominating_road_voronoi"
    num_facilities: int = 0
    num_centers: int = 0  # Size of dominating set
    grid_size: int = 0
    total_route_queries: int = 0
    computation_time_sec: float = 0.0
    features: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


class DominatingVoronoiEngine:
    """
    Computes road-adjusted Voronoi using dominating-set batching.
    
    Algorithm:
    - Step A: Compute Euclidean Voronoi and build adjacency graph
    - Step B: Select "central cells" via greedy dominating set
    - Step C: Define local regions (1-hop neighborhoods) for each center
    - Step D: Batch OSRM queries to reassign grid points by road distance
    - Step E: Merge local refinements into global ownership grid
    """
    
    def __init__(self, routing: Optional[RoutingService] = None):
        self.voronoi_engine = VoronoiEngine()
        self.routing = routing or get_routing_service()
    
    # =========================================================================
    # STEP A: Euclidean Voronoi + Adjacency Graph
    # =========================================================================
    
    def compute_euclidean_voronoi(
        self,
        facilities: List[Dict],
        clip_to_india: bool = True,
        state_filter: Optional[str] = None
    ) -> Tuple[Dict, DCEL, Dict[str, List[str]]]:
        """
        Step A: Compute Euclidean Voronoi and build adjacency graph.
        
        Args:
            facilities: List of {"id", "name", "lat", "lng", "type"} dicts
            clip_to_india: Whether to clip to India boundary
            state_filter: Optional state name to clip to
            
        Returns:
            Tuple of (geojson, dcel, adjacency_graph)
            adjacency_graph maps facility_id -> list of neighbor facility_ids
        """
        coords = [(f["lng"], f["lat"]) for f in facilities]
        names = [f["name"] for f in facilities]
        facility_ids = [f.get("id", str(i)) for i, f in enumerate(facilities)]
        types = [f.get("type") for f in facilities]
        
        # Compute Voronoi with DCEL
        geojson, dcel = self.voronoi_engine.compute_voronoi_with_dcel(
            coords=coords,
            names=names,
            facility_ids=facility_ids,
            types=types,
            clip_to_india=clip_to_india,
            state_filter=state_filter
        )
        
        # Build adjacency graph from polygon touches
        adjacency = self._build_adjacency_graph(dcel, facility_ids)
        
        logger.info(f"Step A complete: {len(facilities)} facilities, {sum(len(v) for v in adjacency.values())//2} edges")
        
        return geojson, dcel, adjacency
    
    def _build_adjacency_graph(self, dcel: DCEL, facility_ids: List[str]) -> Dict[str, List[str]]:
        """Build adjacency graph from DCEL face intersections."""
        adjacency: Dict[str, List[str]] = defaultdict(list)
        
        faces = {f.facility_id: f for f in dcel.faces if f.polygon}
        
        for fid in facility_ids:
            if fid not in faces:
                continue
            face = faces[fid]
            for other_fid, other_face in faces.items():
                if other_fid == fid:
                    continue
                # Check if polygons share a border (touches or intersects boundary)
                if face.polygon.touches(other_face.polygon) or \
                   (face.polygon.intersects(other_face.polygon) and 
                    not face.polygon.intersection(other_face.polygon).is_empty and
                    face.polygon.intersection(other_face.polygon).length > 0):
                    if other_fid not in adjacency[fid]:
                        adjacency[fid].append(other_fid)
        
        return dict(adjacency)
    
    # =========================================================================
    # STEP B: Greedy Dominating Set
    # =========================================================================
    
    def compute_dominating_set(self, adjacency: Dict[str, List[str]]) -> Set[str]:
        """
        Step B: Compute greedy dominating set.
        
        A dominating set S is a subset where every node is either in S or
        adjacent to a node in S.
        
        Greedy approach: repeatedly pick the node that covers most uncovered nodes.
        
        Args:
            adjacency: Adjacency graph (facility_id -> list of neighbor facility_ids)
            
        Returns:
            Set of facility_ids in the dominating set
        """
        all_nodes = set(adjacency.keys())
        for neighbors in adjacency.values():
            all_nodes.update(neighbors)
        
        uncovered = set(all_nodes)
        dominating_set: Set[str] = set()
        
        while uncovered:
            # Find node that covers most uncovered nodes (itself + neighbors)
            best_node = None
            best_coverage = 0
            
            for node in all_nodes:
                if node in dominating_set:
                    continue
                # Coverage = self + uncovered neighbors
                neighbors = set(adjacency.get(node, []))
                coverage = len(({node} | neighbors) & uncovered)
                if coverage > best_coverage:
                    best_coverage = coverage
                    best_node = node
            
            if best_node is None:
                # Pick any uncovered node
                best_node = next(iter(uncovered))
            
            dominating_set.add(best_node)
            # Mark best_node and its neighbors as covered
            uncovered.discard(best_node)
            uncovered -= set(adjacency.get(best_node, []))
        
        logger.info(f"Step B complete: dominating set size = {len(dominating_set)} / {len(all_nodes)} nodes")
        
        return dominating_set
    
    # =========================================================================
    # STEP C: Local Region Definition
    # =========================================================================
    
    def define_local_regions(
        self,
        dominating_set: Set[str],
        adjacency: Dict[str, List[str]],
        dcel: DCEL,
        boundary: Optional[Polygon] = None
    ) -> Dict[str, Tuple[Polygon, List[str]]]:
        """
        Step C: Define local region for each center in dominating set.
        
        For each center s:
        - Neighborhood H(s) = {s} ∪ neighbors[s] (1-hop)
        - Region polygon R(s) = union of Euclidean cells in H(s)
        - Clip to boundary if provided
        
        Args:
            dominating_set: Set of center facility_ids
            adjacency: Adjacency graph
            dcel: DCEL with Voronoi cells
            boundary: Optional boundary polygon for clipping
            
        Returns:
            Dict mapping center_id -> (region_polygon, list of facility_ids in neighborhood)
        """
        regions: Dict[str, Tuple[Polygon, List[str]]] = {}
        
        for center in dominating_set:
            # 1-hop neighborhood
            neighbors = set(adjacency.get(center, []))
            neighborhood = {center} | neighbors
            
            # Collect polygons
            polygons = []
            for fid in neighborhood:
                face = dcel.get_face_by_facility_id(fid)
                if face and face.polygon:
                    polygons.append(face.polygon)
            
            if not polygons:
                continue
            
            # Union of cell polygons
            try:
                region = unary_union(polygons)
                if not region.is_valid:
                    region = region.buffer(0)
                
                # Clip to boundary if provided
                if boundary:
                    region = region.intersection(boundary)
                
                if not region.is_empty:
                    regions[center] = (region, list(neighborhood))
            except Exception as e:
                logger.warning(f"Failed to build region for center {center}: {e}")
        
        logger.info(f"Step C complete: {len(regions)} regions defined")
        
        return regions
    
    # =========================================================================
    # STEP D: Local Road-Distance Reassignment
    # =========================================================================
    
    def reassign_region_by_road(
        self,
        region: Polygon,
        neighborhood_ids: List[str],
        dcel: DCEL,
        config: DominatingVoronoiConfig
    ) -> Tuple[List[Tuple[float, float, str]], int]:
        """
        Step D: Reassign grid points within region by road distance.
        
        Args:
            region: Region polygon to sample
            neighborhood_ids: Facility IDs in this neighborhood (candidates)
            dcel: DCEL for facility locations
            config: Configuration
            
        Returns:
            Tuple of (list of (lat, lng, facility_id) assignments, query_count)
        """
        # Generate grid points within region
        grid_points = self._generate_grid_in_polygon(region, config.grid_density)
        
        if not grid_points:
            return [], 0
        
        # Get facility coordinates
        facility_coords: Dict[str, Tuple[float, float]] = {}
        for fid in neighborhood_ids:
            centroid = dcel.get_facility_centroid(fid)
            if centroid:
                facility_coords[fid] = centroid  # (lat, lng)
        
        if not facility_coords:
            return [], 0
        
        # Batch OSRM table queries
        assignments = []
        query_count = 0
        
        destinations = list(facility_coords.values())
        dest_ids = list(facility_coords.keys())
        
        # Process grid points in batches
        for i in range(0, len(grid_points), config.batch_size):
            batch = grid_points[i:i + config.batch_size]
            
            # Query OSRM table for this batch
            batch_assignments = self._query_osrm_table(batch, destinations, dest_ids)
            assignments.extend(batch_assignments)
            query_count += len(batch)
        
        return assignments, query_count
    
    def _generate_grid_in_polygon(self, polygon: Polygon, density: int) -> List[Tuple[float, float]]:
        """Generate uniform grid of points within polygon."""
        minx, miny, maxx, maxy = polygon.bounds
        
        x_coords = np.linspace(minx, maxx, density)
        y_coords = np.linspace(miny, maxy, density)
        
        grid_points = []
        for y in y_coords:
            for x in x_coords:
                point = Point(x, y)
                if polygon.contains(point):
                    grid_points.append((y, x))  # (lat, lng)
        
        return grid_points
    
    def _query_osrm_table(
        self,
        sources: List[Tuple[float, float]],  # (lat, lng)
        destinations: List[Tuple[float, float]],  # (lat, lng)
        dest_ids: List[str]
    ) -> List[Tuple[float, float, str]]:
        """
        Query OSRM table API for batch distance computation.
        
        Returns list of (lat, lng, nearest_facility_id) for each source.
        Falls back to Euclidean distance when road distance unavailable.
        """
        import httpx
        import math
        
        # Helper to compute Euclidean distance
        def euclidean_dist(lat1, lng1, lat2, lng2):
            return math.sqrt((lat1 - lat2)**2 + (lng1 - lng2)**2)
        
        # Helper to find nearest by Euclidean distance
        def find_nearest_euclidean(lat, lng):
            min_dist = float('inf')
            nearest = dest_ids[0]
            for i, (dlat, dlng) in enumerate(destinations):
                d = euclidean_dist(lat, lng, dlat, dlng)
                if d < min_dist:
                    min_dist = d
                    nearest = dest_ids[i]
            return nearest
        
        # Build coordinate string: sources first, then destinations
        all_coords = []
        for lat, lng in sources:
            all_coords.append(f"{lng},{lat}")
        for lat, lng in destinations:
            all_coords.append(f"{lng},{lat}")
        
        coords_str = ";".join(all_coords)
        
        # Source indices: 0 to len(sources)-1
        # Destination indices: len(sources) to len(sources)+len(destinations)-1
        source_indices = ";".join(str(i) for i in range(len(sources)))
        dest_indices = ";".join(str(i) for i in range(len(sources), len(sources) + len(destinations)))
        
        url = f"{self.routing.config.base_url}/table/v1/car/{coords_str}"
        params = {
            "sources": source_indices,
            "destinations": dest_indices,
            "annotations": "distance"
        }
        
        assignments = []
        
        try:
            client = self.routing._get_sync_client()
            response = client.get(url, params=params, timeout=30.0)
            data = response.json()
            
            if data.get("code") != "Ok":
                logger.warning(f"OSRM table query failed: {data.get('message')}")
                # Fall back to Euclidean distance for all points
                for lat, lng in sources:
                    nearest = find_nearest_euclidean(lat, lng)
                    assignments.append((lat, lng, nearest))
                return assignments
            
            distances = data.get("distances", [])
            
            for i, row in enumerate(distances):
                lat, lng = sources[i]
                
                if not row:
                    # No road distances available - use Euclidean
                    nearest = find_nearest_euclidean(lat, lng)
                    assignments.append((lat, lng, nearest))
                    continue
                
                # Find minimum distance destination (skip nulls)
                min_idx = -1
                min_dist = float('inf')
                for j, dist in enumerate(row):
                    if dist is not None and dist < min_dist:
                        min_dist = dist
                        min_idx = j
                
                if min_idx == -1:
                    # All distances are null - use Euclidean
                    nearest = find_nearest_euclidean(lat, lng)
                    assignments.append((lat, lng, nearest))
                else:
                    assignments.append((lat, lng, dest_ids[min_idx]))
                
        except Exception as e:
            logger.error(f"OSRM table query error: {e}")
            # Fall back to Euclidean for all
            for lat, lng in sources:
                nearest = find_nearest_euclidean(lat, lng)
                assignments.append((lat, lng, nearest))
        
        return assignments
    
    # =========================================================================
    # STEP E: Global Merge
    # =========================================================================
    
    def merge_refinements(
        self,
        euclidean_geojson: Dict,
        region_assignments: Dict[str, List[Tuple[float, float, str]]],
        dcel: DCEL,
        boundary: Polygon,
        config: DominatingVoronoiConfig
    ) -> DominatingVoronoiResult:
        """
        Step E: Merge local refinements into global result.
        
        - Initialize global grid from Euclidean assignments
        - Overwrite with road-based assignments from each region
        - Interpolate into polygons
        - Include Euclidean cells for facilities not in any refined region
        
        Args:
            euclidean_geojson: Original Euclidean Voronoi GeoJSON
            region_assignments: Dict mapping center_id -> list of (lat, lng, facility_id)
            dcel: DCEL for facility info
            boundary: Boundary polygon
            config: Configuration
            
        Returns:
            DominatingVoronoiResult with road-adjusted polygons
        """
        # Collect all assignments
        all_assignments: List[Tuple[float, float, str]] = []
        
        # Track which facilities are covered by road-based refinement
        refined_facilities: Set[str] = set()
        
        for center_id, assignments in region_assignments.items():
            all_assignments.extend(assignments)
            for _, _, fid in assignments:
                refined_facilities.add(fid)
        
        logger.info(f"  Total assignments: {len(all_assignments)}, {len(refined_facilities)} facilities in refined regions")
        
        features = []
        road_refined_fids: Set[str] = set()  # Facilities that actually got polygons
        
        # Only interpolate if we have enough points
        if len(all_assignments) >= 3:
            # Interpolate refined regions into polygons using Delaunay triangulation
            facility_polygons = self._interpolate_polygons(all_assignments, boundary)
            
            logger.info(f"  Interpolated {len(facility_polygons)} polygons from Delaunay")
            
            # Build GeoJSON features for road-refined cells
            for facility_id, polygon in facility_polygons.items():
                face = dcel.get_face_by_facility_id(facility_id)
                
                # Count grid points for this facility
                point_count = sum(1 for a in all_assignments if a[2] == facility_id)
                
                feature = {
                    "type": "Feature",
                    "properties": {
                        "facility_id": facility_id,
                        "name": face.facility_name if face else facility_id,
                        "cell_type": "road_refined",
                        "grid_points_count": point_count,
                        "area_sq_km": self._calculate_area_km2(polygon),
                    },
                    "geometry": self._polygon_to_geojson(polygon)
                }
                features.append(feature)
                road_refined_fids.add(facility_id)
        
        # Add Euclidean cells for facilities that didn't get road-refined polygons
        # (either not in any refined region, OR were in region but Delaunay didn't produce a polygon)
        for euclidean_feature in euclidean_geojson.get("features", []):
            fid = euclidean_feature.get("properties", {}).get("facility_id")
            if fid and fid not in road_refined_fids:
                # This facility didn't get a road-refined polygon - use Euclidean cell
                modified_feature = dict(euclidean_feature)
                modified_feature["properties"] = dict(euclidean_feature.get("properties", {}))
                modified_feature["properties"]["cell_type"] = "euclidean_fallback"
                features.append(modified_feature)
        
        logger.info(f"  Final output: {len(features)} features ({len(road_refined_fids)} road-refined, {len(features) - len(road_refined_fids)} Euclidean fallback)")
        
        return DominatingVoronoiResult(
            features=features,
            grid_size=len(all_assignments)
        )
    
    def _interpolate_polygons(
        self,
        assignments: List[Tuple[float, float, str]],
        boundary: Polygon
    ) -> Dict[str, Polygon]:
        """Interpolate point assignments into polygons via Delaunay."""
        if len(assignments) < 3:
            return {}
        
        points = np.array([[a[1], a[0]] for a in assignments])  # (lng, lat)
        facility_ids = [a[2] for a in assignments]
        
        try:
            tri = Delaunay(points)
        except Exception as e:
            logger.error(f"Delaunay failed: {e}")
            return {}
        
        # Group triangles by majority facility
        from collections import Counter
        facility_triangles: Dict[str, List[Polygon]] = defaultdict(list)
        
        for simplex in tri.simplices:
            vertex_facilities = [facility_ids[i] for i in simplex]
            majority = Counter(vertex_facilities).most_common(1)[0][0]
            
            triangle_coords = points[simplex].tolist()
            triangle_coords.append(triangle_coords[0])
            triangle = Polygon(triangle_coords)
            
            if triangle.is_valid and triangle.area > 0:
                facility_triangles[majority].append(triangle)
        
        # Dissolve triangles and clip to boundary
        result = {}
        for fid, triangles in facility_triangles.items():
            try:
                merged = unary_union(triangles)
                clipped = merged.intersection(boundary)
                if not clipped.is_empty:
                    result[fid] = clipped
            except Exception as e:
                logger.warning(f"Failed to merge triangles for {fid}: {e}")
        
        return result
    
    def _polygon_to_geojson(self, polygon) -> Dict:
        """Convert Shapely polygon to GeoJSON geometry."""
        if polygon.geom_type == 'Polygon':
            return {
                "type": "Polygon",
                "coordinates": [list(polygon.exterior.coords)]
            }
        elif polygon.geom_type == 'MultiPolygon':
            return {
                "type": "MultiPolygon",
                "coordinates": [[list(p.exterior.coords)] for p in polygon.geoms]
            }
        return {"type": "Polygon", "coordinates": []}
    
    def _calculate_area_km2(self, polygon) -> float:
        """Approximate area in km² (rough conversion at Indian latitudes)."""
        # 1 degree ≈ 111 km
        return polygon.area * 111 * 111
    
    # =========================================================================
    # MAIN COMPUTE METHOD
    # =========================================================================
    
    def compute(
        self,
        facilities: List[Dict],
        clip_to_india: bool = True,
        state_filter: Optional[str] = None,
        config: Optional[DominatingVoronoiConfig] = None
    ) -> DominatingVoronoiResult:
        """
        Compute dominating-set road Voronoi diagram.
        
        Args:
            facilities: List of {"id", "name", "lat", "lng", "type"} dicts
            clip_to_india: Whether to clip to India boundary
            state_filter: Optional state name to clip to
            config: Configuration options
            
        Returns:
            DominatingVoronoiResult with road-adjusted polygons
        """
        start_time = time.time()
        config = config or DominatingVoronoiConfig()
        
        if len(facilities) < 3:
            raise ValueError("Need at least 3 facilities")
        
        # Step A: Euclidean Voronoi + adjacency
        logger.info("Step A: Computing Euclidean Voronoi and adjacency...")
        euclidean_geojson, dcel, adjacency = self.compute_euclidean_voronoi(
            facilities, clip_to_india, state_filter
        )
        
        # Step B: Greedy dominating set
        logger.info("Step B: Computing dominating set...")
        dominating_set = self.compute_dominating_set(adjacency)
        
        # Get boundary polygon for clipping
        if state_filter:
            boundary = self.voronoi_engine._get_state_boundary_wgs84(state_filter)
        elif clip_to_india:
            boundary = VoronoiEngine._india_boundary_wgs84
        else:
            # Use convex hull of facilities
            from shapely.geometry import MultiPoint
            coords = [(f["lng"], f["lat"]) for f in facilities]
            boundary = MultiPoint(coords).convex_hull.buffer(0.5)
        
        if boundary is None:
            logger.warning("No boundary found, using facility convex hull")
            from shapely.geometry import MultiPoint
            coords = [(f["lng"], f["lat"]) for f in facilities]
            boundary = MultiPoint(coords).convex_hull.buffer(0.5)
        
        # Step C: Define local regions
        logger.info("Step C: Defining local regions...")
        regions = self.define_local_regions(dominating_set, adjacency, dcel, boundary)
        
        # Step D: Road-distance reassignment for each region
        logger.info("Step D: Reassigning by road distance...")
        region_assignments: Dict[str, List[Tuple[float, float, str]]] = {}
        total_queries = 0
        
        for i, (center, (region_polygon, neighborhood)) in enumerate(regions.items()):
            logger.info(f"  Processing region {i+1}/{len(regions)} (center: {center}, {len(neighborhood)} facilities)")
            assignments, query_count = self.reassign_region_by_road(
                region_polygon, neighborhood, dcel, config
            )
            region_assignments[center] = assignments
            total_queries += query_count
        
        # Step E: Merge refinements
        logger.info("Step E: Merging refinements...")
        result = self.merge_refinements(
            euclidean_geojson, region_assignments, dcel, boundary, config
        )
        
        computation_time = time.time() - start_time
        
        # Update result metadata
        result.num_facilities = len(facilities)
        result.num_centers = len(dominating_set)
        result.total_route_queries = total_queries
        result.computation_time_sec = round(computation_time, 2)
        result.metadata = {
            "dominating_set": list(dominating_set),
            "num_regions": len(regions),
            "config": {
                "grid_density": config.grid_density,
                "batch_size": config.batch_size
            }
        }
        
        logger.info(f"Computation complete: {computation_time:.2f}s, {total_queries} queries")
        
        return result
    
    def to_geojson(self, result: DominatingVoronoiResult) -> Dict:
        """Convert result to GeoJSON FeatureCollection."""
        return {
            "type": "FeatureCollection",
            "properties": {
                "computation_method": "dominating_set_road_voronoi",
                "num_facilities": result.num_facilities,
                "num_centers": result.num_centers,
                "grid_size": result.grid_size,
                "total_route_queries": result.total_route_queries,
                "computation_time_sec": result.computation_time_sec,
                **result.metadata
            },
            "features": result.features
        }


# Module-level helper
def get_dominating_voronoi_engine() -> DominatingVoronoiEngine:
    """Get a new instance of the dominating Voronoi engine."""
    return DominatingVoronoiEngine()
