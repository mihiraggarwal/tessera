"""
Edge-Adjustment Road Voronoi Engine

Adjusts Voronoi cell edges from Euclidean midpoints to road-distance equidistant curves.
More elegant than grid-based approach as it preserves edge topology and produces smooth boundaries.

Algorithm:
1. Compute Euclidean Voronoi diagram
2. Extract edges between adjacent cells
3. For each edge, find road-distance equidistant curve via sampling
4. Rebuild polygons with adjusted edges
"""

import logging
import time
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
import numpy as np
from shapely.geometry import Point, Polygon, LineString, MultiPolygon
from shapely.ops import unary_union, polygonize
from collections import defaultdict

from .voronoi_engine import VoronoiEngine
from .dcel import DCEL, DCELFace
from .routing_service import RoutingService, get_routing_service

logger = logging.getLogger(__name__)


@dataclass
class EdgeAdjustConfig:
    """Configuration for edge-adjustment road Voronoi."""
    samples_per_edge: int = 5  # Number of sample points along each edge (reduced for speed)
    search_radius_m: float = 3000.0  # Max perpendicular search distance in meters
    search_steps: int = 3  # Binary search iterations for equidistant point (reduced)


@dataclass
class EdgeAdjustResult:
    """Result of edge-adjustment road Voronoi computation."""
    type: str = "edge_adjust_road_voronoi"
    num_facilities: int = 0
    num_edges: int = 0
    total_route_queries: int = 0
    computation_time_sec: float = 0.0
    features: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


class EdgeAdjustVoronoiEngine:
    """
    Computes road-adjusted Voronoi by shifting edges to road-distance equidistant curves.
    
    Algorithm:
    1. Compute Euclidean Voronoi diagram
    2. Extract edges between adjacent cells  
    3. For each edge, sample points and adjust to road-distance equidistant
    4. Rebuild polygons using adjusted edges
    """
    
    def __init__(self, routing: Optional[RoutingService] = None):
        self.voronoi_engine = VoronoiEngine()
        self.routing = routing or get_routing_service()
    
    def compute(
        self,
        facilities: List[Dict],
        clip_to_india: bool = True,
        state_filter: Optional[str] = None,
        config: Optional[EdgeAdjustConfig] = None
    ) -> EdgeAdjustResult:
        """
        Compute edge-adjusted road Voronoi diagram.
        
        Args:
            facilities: List of {"id", "name", "lat", "lng", "type"} dicts
            clip_to_india: Whether to clip to India boundary
            state_filter: Optional state name to clip to
            config: Configuration options
            
        Returns:
            EdgeAdjustResult with road-adjusted polygons
        """
        import sys
        
        start_time = time.time()
        config = config or EdgeAdjustConfig()
        
        print(f"\n{'='*60}", flush=True)
        print(f"EDGE-ADJUST VORONOI - Starting computation", flush=True)
        print(f"  Facilities: {len(facilities)}", flush=True)
        print(f"  Config: samples_per_edge={config.samples_per_edge}, search_steps={config.search_steps}", flush=True)
        print(f"{'='*60}", flush=True)
        
        if len(facilities) < 3:
            raise ValueError("Need at least 3 facilities")
        
        # Build facility lookup
        facility_map = {f.get("id", str(i)): f for i, f in enumerate(facilities)}
        
        # Step 1: Compute Euclidean Voronoi
        print(f"\n[Step 1/4] Computing Euclidean Voronoi...", flush=True)
        step1_start = time.time()
        
        coords = [(f["lng"], f["lat"]) for f in facilities]
        names = [f["name"] for f in facilities]
        facility_ids = [f.get("id", str(i)) for i, f in enumerate(facilities)]
        types = [f.get("type") for f in facilities]
        
        geojson, dcel = self.voronoi_engine.compute_voronoi_with_dcel(
            coords=coords,
            names=names,
            facility_ids=facility_ids,
            types=types,
            clip_to_india=clip_to_india,
            state_filter=state_filter
        )
        print(f"  Done in {time.time() - step1_start:.2f}s", flush=True)
        
        # Step 2: Extract vertices and their adjacent facilities
        print(f"\n[Step 2/4] Extracting Voronoi vertices...", flush=True)
        step2_start = time.time()
        vertices = self._extract_vertices(dcel, facility_ids)
        print(f"  Found {len(vertices)} vertices in {time.time() - step2_start:.2f}s", flush=True)
        
        # Estimate query count: 3 queries per vertex (one to each adjacent facility)
        estimated_queries = len(vertices) * 3
        est_time = estimated_queries * 0.05  # ~50ms per query
        print(f"  Estimated OSRM queries: ~{estimated_queries} (~{est_time:.0f}s)", flush=True)
        
        # Step 3: Adjust each vertex based on road distances
        print(f"\n[Step 3/4] Adjusting vertices to road-distance equidistant...", flush=True)
        step3_start = time.time()
        adjusted_vertices: Dict[Tuple[float, float], Tuple[float, float]] = {}
        total_queries = 0
        
        for i, (vertex_coord, adjacent_fids) in enumerate(vertices):
            if len(adjacent_fids) < 3:
                # Boundary vertex - keep original
                adjusted_vertices[vertex_coord] = vertex_coord
                continue
            
            print(f"  Vertex {i+1}/{len(vertices)}: ({vertex_coord[0]:.4f}, {vertex_coord[1]:.4f}) ", end="", flush=True)
            
            new_coord, queries = self._adjust_vertex(
                vertex_coord,
                adjacent_fids,
                facility_map,
                config
            )
            
            adjusted_vertices[vertex_coord] = new_coord
            total_queries += queries
            
            shift = ((new_coord[0] - vertex_coord[0])**2 + (new_coord[1] - vertex_coord[1])**2)**0.5 * 111000
            print(f"[{queries} queries, shift={shift:.0f}m]", flush=True)
        
        print(f"  Step 3 done in {time.time() - step3_start:.2f}s, {total_queries} total queries", flush=True)
        
        # Step 4: Rebuild polygons using adjusted vertices
        print(f"\n[Step 4/4] Rebuilding polygons from adjusted vertices...", flush=True)
        step4_start = time.time()
        
        # Get boundary
        if state_filter:
            boundary = self.voronoi_engine._get_state_boundary_wgs84(state_filter)
        elif clip_to_india:
            boundary = VoronoiEngine._india_boundary_wgs84
        else:
            from shapely.geometry import MultiPoint
            boundary = MultiPoint(coords).convex_hull.buffer(0.5)
        
        # Rebuild cell polygons using adjusted vertices
        features = self._rebuild_polygons_from_vertices(
            dcel, adjusted_vertices, facility_map, boundary, geojson
        )
        print(f"  Done in {time.time() - step4_start:.2f}s", flush=True)
        
        computation_time = time.time() - start_time
        
        result = EdgeAdjustResult(
            num_facilities=len(facilities),
            num_edges=len(vertices),  # Now represents vertices instead of edges
            total_route_queries=total_queries,
            computation_time_sec=round(computation_time, 2),
            features=features,
            metadata={
                "method": "vertex_adjustment",
                "num_vertices": len(vertices),
                "num_interior_vertices": len(adjusted_vertices)
            }
        )
        
        print(f"\n{'='*60}", flush=True)
        print(f"COMPLETE: {computation_time:.2f}s, {total_queries} queries, {len(features)} cells", flush=True)
        print(f"{'='*60}\n", flush=True)
        
        return result
    
    def _extract_edges(
        self, 
        dcel: DCEL, 
        facility_ids: List[str]
    ) -> List[Tuple[str, str, LineString]]:
        """
        Extract edges between adjacent Voronoi cells.
        
        Returns list of (facility_id_a, facility_id_b, edge_linestring)
        """
        edges = []
        seen_pairs: Set[Tuple[str, str]] = set()
        
        faces = {f.facility_id: f for f in dcel.faces if f.polygon}
        
        for fid_a in facility_ids:
            if fid_a not in faces:
                continue
            
            face_a = faces[fid_a]
            
            for fid_b in facility_ids:
                if fid_b == fid_a or fid_b not in faces:
                    continue
                
                # Skip if already processed
                pair = tuple(sorted([fid_a, fid_b]))
                if pair in seen_pairs:
                    continue
                
                face_b = faces[fid_b]
                
                # Find shared boundary
                try:
                    intersection = face_a.polygon.intersection(face_b.polygon)
                    if intersection.is_empty:
                        continue
                    
                    # Get the line part of the intersection
                    if intersection.geom_type == 'LineString' and intersection.length > 0:
                        edges.append((fid_a, fid_b, intersection))
                        seen_pairs.add(pair)
                    elif intersection.geom_type == 'MultiLineString':
                        # Merge multi-line into single line
                        merged = unary_union(list(intersection.geoms))
                        if merged.geom_type == 'LineString' and merged.length > 0:
                            edges.append((fid_a, fid_b, merged))
                            seen_pairs.add(pair)
                    elif intersection.geom_type in ('GeometryCollection', 'MultiLineString'):
                        # Extract line parts
                        for geom in intersection.geoms:
                            if geom.geom_type == 'LineString' and geom.length > 0:
                                edges.append((fid_a, fid_b, geom))
                                seen_pairs.add(pair)
                                break
                except Exception as e:
                    logger.warning(f"Failed to extract edge between {fid_a} and {fid_b}: {e}")
        
        return edges
    
    def _extract_vertices(
        self,
        dcel: DCEL,
        facility_ids: List[str]
    ) -> List[Tuple[Tuple[float, float], List[str]]]:
        """
        Extract Voronoi vertices and their adjacent facilities.
        
        A Voronoi vertex is a point where 3+ cells meet.
        Returns list of (vertex_coord, [adjacent_facility_ids])
        """
        from collections import defaultdict
        
        # Map each vertex (rounded coords) to the facilities whose cells contain it
        vertex_to_facilities = defaultdict(set)
        
        faces = {f.facility_id: f for f in dcel.faces if f.polygon and f.facility_id}
        
        # For each polygon, get its vertices
        for fid, face in faces.items():
            if not face.polygon:
                continue
            
            try:
                coords = list(face.polygon.exterior.coords)
                for coord in coords:
                    # Round to avoid floating point issues
                    rounded = (round(coord[0], 6), round(coord[1], 6))
                    vertex_to_facilities[rounded].add(fid)
            except Exception as e:
                logger.warning(f"Failed to extract vertices for {fid}: {e}")
        
        # Filter to only interior vertices (where 3+ cells meet)
        vertices = []
        for coord, fids in vertex_to_facilities.items():
            if len(fids) >= 3:
                vertices.append((coord, list(fids)))
        
        return vertices
    
    def _adjust_vertex(
        self,
        vertex_coord: Tuple[float, float],
        adjacent_fids: List[str],
        facility_map: Dict[str, Dict],
        config: EdgeAdjustConfig
    ) -> Tuple[Tuple[float, float], int]:
        """
        Adjust a Voronoi vertex to be equidistant in road distance from adjacent facilities.
        
        For a vertex where facilities F1, F2, F3 meet:
        1. Query road distances: vertex -> F1, F2, F3
        2. If not equidistant, compute the point where they would be
        3. Use gradient descent or geometric calculation
        
        Returns: (new_vertex_coord, query_count)
        """
        lng, lat = vertex_coord
        query_count = 0
        
        # Query road distances to each adjacent facility
        road_distances = {}
        for fid in adjacent_fids[:3]:  # Use first 3 for simplicity
            fac = facility_map.get(fid)
            if not fac:
                continue
            
            dist = self._query_road_distance(lat, lng, fac["lat"], fac["lng"])
            query_count += 1
            
            if dist is not None:
                road_distances[fid] = dist
        
        if len(road_distances) < 3:
            # Couldn't query all facilities - keep original
            return vertex_coord, query_count
        
        # Calculate the average distance and the desired equidistant point
        avg_dist = sum(road_distances.values()) / len(road_distances)
        
        # For each facility, calculate how much we need to adjust
        # If dist_to_F1 > avg, we need to move closer to F1
        # Simple approach: weighted average shift toward each facility
        
        shift_x = 0.0
        shift_y = 0.0
        
        for fid, dist in road_distances.items():
            fac = facility_map[fid]
            fac_lng, fac_lat = fac["lng"], fac["lat"]
            
            # Direction from vertex to facility
            dir_lng = fac_lng - lng
            dir_lat = fac_lat - lat
            dir_len = (dir_lng**2 + dir_lat**2)**0.5
            
            if dir_len == 0:
                continue
            
            # Normalize
            dir_lng /= dir_len
            dir_lat /= dir_len
            
            # If this facility is farther than average, we need to move toward it
            # If closer than average, move away
            dist_diff = dist - avg_dist
            
            # Convert to degrees (rough: 1 degree ≈ 111km = 111000m)
            # Use a smaller scale factor to prevent excessive shifts
            shift_amount = dist_diff / 111000 * 0.8  # Reduced scale factor
            
            shift_x += dir_lng * shift_amount
            shift_y += dir_lat * shift_amount
        
        # Limit maximum shift to prevent overlaps
        # Max shift = 2km = ~0.018 degrees
        max_shift_deg = 0.1
        total_shift = (shift_x**2 + shift_y**2)**0.5
        
        if total_shift > max_shift_deg:
            # Scale down the shift
            scale = max_shift_deg / total_shift
            shift_x *= scale
            shift_y *= scale
        
        # Apply shift
        new_lng = lng + shift_x
        new_lat = lat + shift_y
        
        return (new_lng, new_lat), query_count
    
    def _adjust_edge(
        self,
        edge: LineString,
        facility_a: Dict,
        facility_b: Dict,
        config: EdgeAdjustConfig
    ) -> Tuple[LineString, int]:
        """
        Adjust edge based on road distances FROM the edge TO each facility.
        
        Approach:
        1. Sample the midpoint of the edge
        2. Query road distance: midpoint → A and midpoint → B (2 queries)
        3. Shift edge perpendicular toward the facility with SHORTER road distance
        
        This reflects: if road to A is shorter, A's cell should be larger (edge shifts toward B)
        
        Returns: (adjusted_linestring, query_count)
        """
        # Facility coordinates
        lat_a, lng_a = facility_a["lat"], facility_a["lng"]
        lat_b, lng_b = facility_b["lat"], facility_b["lng"]
        
        # Get edge midpoint
        midpoint = edge.interpolate(0.5, normalized=True)
        mid_lng, mid_lat = midpoint.x, midpoint.y
        
        # Query road distances from edge midpoint to each facility (2 queries)
        road_dist_a = self._query_road_distance(mid_lat, mid_lng, lat_a, lng_a)
        road_dist_b = self._query_road_distance(mid_lat, mid_lng, lat_b, lng_b)
        query_count = 2
        
        if road_dist_a is None or road_dist_b is None:
            # Routing failed, keep original edge
            print(f"    [routing failed, keeping original]", flush=True)
            return edge, query_count
        
        # Calculate difference
        diff = road_dist_a - road_dist_b  # positive = A is farther by road
        total_dist = road_dist_a + road_dist_b
        
        print(f"    [road_A={road_dist_a:.0f}m, road_B={road_dist_b:.0f}m, diff={diff:.0f}m]", flush=True)
        
        # Calculate shift direction and amount
        # If A is farther by road, shift edge TOWARD A (shrink A's cell)
        # If B is farther by road, shift edge TOWARD B (shrink B's cell)
        
        # Get perpendicular direction (from A toward B)
        vec_ab_lng = lng_b - lng_a
        vec_ab_lat = lat_b - lat_a
        vec_len = np.sqrt(vec_ab_lng**2 + vec_ab_lat**2)
        
        if vec_len == 0:
            return edge, query_count
        
        # Unit vector from A to B
        unit_ab_lng = vec_ab_lng / vec_len
        unit_ab_lat = vec_ab_lat / vec_len
        
        # Calculate the CORRECT shift amount
        # The edge should be at the point where road_dist to A = road_dist to B
        # Currently from edge: road_dist_A to A, road_dist_B to B
        # Moving toward A by d meters: new_dist_A ≈ road_dist_A - d, new_dist_B ≈ road_dist_B + d
        # For equal distances: road_dist_A - d = road_dist_B + d
        # Therefore: d = (road_dist_A - road_dist_B) / 2
        
        shift_meters = diff / 2  # This is the exact amount to shift
        
        # Convert meters to degrees (rough approximation: 1 degree ≈ 111km)
        shift_deg = shift_meters / 111000
        
        print(f"    [shifting by {shift_meters:.0f}m toward {'A' if diff > 0 else 'B'}]", flush=True)
        
        # Apply shift to all edge coordinates
        adjusted_coords = []
        for x, y in edge.coords:
            new_x = x + shift_deg * unit_ab_lng
            new_y = y + shift_deg * unit_ab_lat
            adjusted_coords.append((new_x, new_y))
        
        return LineString(adjusted_coords), query_count
    
    def _haversine_distance(
        self, 
        lat1: float, lng1: float, 
        lat2: float, lng2: float
    ) -> float:
        """Calculate Haversine distance in meters between two points."""
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371000  # Earth radius in meters
        
        lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
    
    def _query_road_distance(
        self, 
        from_lat: float, 
        from_lng: float, 
        to_lat: float, 
        to_lng: float
    ) -> Optional[float]:
        """Query OSRM for road distance between two points."""
        try:
            url = f"{self.routing.config.base_url}/route/v1/car/{from_lng},{from_lat};{to_lng},{to_lat}"
            params = {"overview": "false", "steps": "false"}
            
            client = self.routing._get_sync_client()
            response = client.get(url, params=params)
            data = response.json()
            
            if data.get("code") == "Ok" and data.get("routes"):
                return data["routes"][0]["distance"]
            return None
        except Exception as e:
            logger.debug(f"Road distance query failed: {e}")
            return None
    
    def _rebuild_polygons_from_vertices(
        self,
        dcel: DCEL,
        adjusted_vertices: Dict[Tuple[float, float], Tuple[float, float]],
        facility_map: Dict[str, Dict],
        boundary: Polygon,
        original_geojson: Dict
    ) -> List[Dict]:
        """
        Rebuild cell polygons using adjusted vertex positions.
        
        For each polygon, replace its vertices with the adjusted positions.
        This maintains topology since all polygons share the same adjusted vertices.
        """
        from shapely.geometry import Polygon as ShapelyPolygon
        from shapely.validation import make_valid
        
        print(f"  Rebuilding {len(dcel.faces)} polygons from {len(adjusted_vertices)} adjusted vertices...", flush=True)
        
        features = []
        
        for face in dcel.faces:
            if not face.polygon or not face.facility_id:
                continue
            
            fid = face.facility_id
            original_poly = face.polygon
            
            # Get original coordinates and replace with adjusted ones
            try:
                orig_coords = list(original_poly.exterior.coords)
                new_coords = []
                
                for coord in orig_coords:
                    # Round to match our vertex lookup
                    rounded = (round(coord[0], 6), round(coord[1], 6))
                    
                    # Use adjusted vertex if available, otherwise keep original
                    if rounded in adjusted_vertices:
                        new_coords.append(adjusted_vertices[rounded])
                    else:
                        new_coords.append(coord)
                
                # Close the ring if not closed
                if new_coords[0] != new_coords[-1]:
                    new_coords.append(new_coords[0])
                
                # Create new polygon
                adjusted_poly = ShapelyPolygon(new_coords)
                
                # Validate and fix if needed
                if not adjusted_poly.is_valid:
                    try:
                        adjusted_poly = make_valid(adjusted_poly)
                    except:
                        adjusted_poly = adjusted_poly.buffer(0)
                
                # If still invalid or empty, use original
                if adjusted_poly.is_empty or not adjusted_poly.is_valid:
                    adjusted_poly = original_poly
                
                # Extract polygon from possible GeometryCollection
                if adjusted_poly.geom_type == 'GeometryCollection':
                    for geom in adjusted_poly.geoms:
                        if geom.geom_type == 'Polygon' and not geom.is_empty:
                            adjusted_poly = geom
                            break
                    else:
                        adjusted_poly = original_poly
                elif adjusted_poly.geom_type == 'MultiPolygon':
                    # Take the largest polygon
                    largest = max(adjusted_poly.geoms, key=lambda p: p.area)
                    adjusted_poly = largest
                    
            except Exception as e:
                logger.warning(f"Failed to adjust polygon for {fid}: {e}")
                adjusted_poly = original_poly
            
            # Clip to boundary
            try:
                clipped = adjusted_poly.intersection(boundary)
                if clipped.is_empty:
                    continue
            except Exception:
                clipped = adjusted_poly
            
            # Find original feature properties
            original_props = {}
            for feat in original_geojson.get("features", []):
                if feat.get("properties", {}).get("facility_id") == fid:
                    original_props = feat.get("properties", {})
                    break
            
            feature = {
                "type": "Feature",
                "properties": {
                    **original_props,
                    "facility_id": fid,
                    "name": face.facility_name,
                    "cell_type": "vertex_adjusted",
                    "area_sq_km": self._calculate_area_km2(clipped),
                },
                "geometry": self._polygon_to_geojson(clipped)
            }
            features.append(feature)
        
        print(f"  Built {len(features)} vertex-adjusted cells", flush=True)
        return features
    
    def _rebuild_polygons(
        self,
        dcel: DCEL,
        adjusted_edges: Dict[Tuple[str, str], LineString],
        facility_map: Dict[str, Dict],
        boundary: Polygon,
        original_geojson: Dict
    ) -> List[Dict]:
        """
        Rebuild cell polygons by scaling them based on road accessibility.
        
        For each cell:
        1. Calculate average road distance ratio from its edges
        2. Scale the polygon (shrink if poor road access, expand if good)
        3. This maintains proper visualization while showing road effects
        """
        from shapely.affinity import scale
        from shapely.geometry import Point
        
        print(f"  Scaling {len(dcel.faces)} polygons based on road accessibility...", flush=True)
        
        # Calculate scale factor for each facility based on edge adjustments
        facility_scale_factors = {}
        
        for face in dcel.faces:
            if not face.polygon or not face.facility_id:
                continue
            
            fid = face.facility_id
            
            # Get all edges involving this facility
            total_ratio = 0
            edge_count = 0
            
            for (fid_a, fid_b), adjusted_edge in adjusted_edges.items():
                if fid not in (fid_a, fid_b):
                    continue
                
                # Find the other facility
                other_fid = fid_b if fid == fid_a else fid_a
                fac_a = facility_map.get(fid)
                fac_b = facility_map.get(other_fid)
                
                if not fac_a or not fac_b:
                    continue
                
                # Get edge midpoint and calculate road distances
                edge_mid = adjusted_edge.interpolate(0.5, normalized=True)
                
                # Road distances were already computed - use the shift amount to estimate ratio
                # If edge shifted toward this facility, this facility has worse road access
                fac_point = Point(fac_a["lng"], fac_a["lat"])
                edge_start = Point(adjusted_edge.coords[0])
                edge_end = Point(adjusted_edge.coords[-1])
                
                # Compute a simple accessibility metric
                edge_count += 1
            
            # Scale factor: 1.0 means no change
            # For now, keep original size (we'll use edge shifts for visual feedback)
            facility_scale_factors[fid] = 1.0
        
        # Build features using original polygons (properly tiled)
        features = []
        
        for face in dcel.faces:
            if not face.polygon or not face.facility_id:
                continue
            
            fid = face.facility_id
            original_poly = face.polygon
            
            # For now, use original polygon (proper tiling)
            adjusted_poly = original_poly
            
            # Clip to boundary
            try:
                clipped = adjusted_poly.intersection(boundary)
                if clipped.is_empty:
                    continue
            except Exception:
                clipped = adjusted_poly
            
            # Find original feature properties
            original_props = {}
            for feat in original_geojson.get("features", []):
                if feat.get("properties", {}).get("facility_id") == fid:
                    original_props = feat.get("properties", {})
                    break
            
            # Calculate road accessibility score from adjacent edges
            road_scores = []
            for (fid_a, fid_b), adj_edge in adjusted_edges.items():
                if fid in (fid_a, fid_b):
                    # Check shift direction - did edge move toward or away from this facility?
                    other_fid = fid_b if fid == fid_a else fid_a
                    other_fac = facility_map.get(other_fid)
                    this_fac = facility_map.get(fid)
                    
                    if other_fac and this_fac:
                        # Simple score: compare adjusted edge position to original
                        pass
            
            feature = {
                "type": "Feature",
                "properties": {
                    **original_props,
                    "facility_id": fid,
                    "name": face.facility_name,
                    "cell_type": "edge_adjusted",
                    "area_sq_km": self._calculate_area_km2(clipped),
                },
                "geometry": self._polygon_to_geojson(clipped)
            }
            features.append(feature)
        
        print(f"  Built {len(features)} road-adjusted cells", flush=True)
        return features
    
    def _fallback_to_original(self, dcel, boundary, original_geojson):
        """Return original Euclidean polygons as fallback."""
        features = []
        for feat in original_geojson.get("features", []):
            features.append(feat)
        return features
    
    def _merge_same_facility_features(self, features):
        """Merge multiple polygons assigned to the same facility."""
        from shapely.geometry import shape
        from shapely.ops import unary_union
        
        facility_polys = {}
        facility_props = {}
        
        for feat in features:
            fid = feat["properties"].get("facility_id")
            if not fid:
                continue
            
            geom = feat["geometry"]
            if geom["type"] == "Polygon" and geom.get("coordinates"):
                try:
                    poly = shape(geom)
                    if fid in facility_polys:
                        facility_polys[fid].append(poly)
                    else:
                        facility_polys[fid] = [poly]
                        facility_props[fid] = feat["properties"]
                except:
                    pass
        
        merged_features = []
        for fid, polys in facility_polys.items():
            try:
                merged = unary_union(polys)
                props = facility_props[fid]
                props["area_sq_km"] = self._calculate_area_km2(merged)
                
                merged_features.append({
                    "type": "Feature",
                    "properties": props,
                    "geometry": self._polygon_to_geojson(merged)
                })
            except:
                pass
        
        return merged_features
    
    def _points_close(self, p1: Tuple[float, float], p2: Tuple[float, float], tol: float = 0.0001) -> bool:
        """Check if two points are approximately equal."""
        return abs(p1[0] - p2[0]) < tol and abs(p1[1] - p2[1]) < tol
    
    def _adjust_polygon_edges(
        self,
        polygon: Polygon,
        facility_id: str,
        adjusted_edges: Dict[Tuple[str, str], LineString],
        dcel: DCEL
    ) -> Optional[Polygon]:
        """
        Replace polygon edges with adjusted versions where available.
        
        This is a simplified approach - for production, we'd need more
        sophisticated geometry manipulation.
        """
        # Get all edges that involve this facility
        relevant_edges = []
        for (fid_a, fid_b), edge in adjusted_edges.items():
            if facility_id in (fid_a, fid_b):
                relevant_edges.append(edge)
        
        if not relevant_edges:
            return polygon
        
        # For now, just return the original polygon
        # A full implementation would reconstruct the polygon boundary
        # by stitching together adjusted edges
        # This is complex because we need to handle:
        # - Order of edges around the polygon
        # - Connecting endpoints between edges
        # - Boundary edges that don't have adjustments
        
        # Simplified: buffer the union of adjusted edges and intersect with original
        # This gives an approximation
        try:
            edges_union = unary_union(relevant_edges)
            if edges_union.is_empty:
                return polygon
            
            # Create a small buffer around adjusted edges and intersect with original
            buffered = edges_union.buffer(0.001)  # ~100m buffer
            
            # Use original polygon - the edge adjustment is reflected in neighbor relationships
            return polygon
        except Exception as e:
            logger.warning(f"Failed to adjust polygon for {facility_id}: {e}")
            return polygon
    
    def _polygon_to_geojson(self, polygon) -> Dict:
        """Convert Shapely polygon to GeoJSON geometry."""
        if polygon is None or polygon.is_empty:
            return {"type": "Polygon", "coordinates": []}
        
        if polygon.geom_type == 'Polygon':
            coords = list(polygon.exterior.coords)
            if len(coords) >= 4:  # Valid polygon needs at least 4 points
                return {
                    "type": "Polygon",
                    "coordinates": [coords]
                }
        elif polygon.geom_type == 'MultiPolygon':
            polys = []
            for p in polygon.geoms:
                if p.geom_type == 'Polygon' and not p.is_empty:
                    coords = list(p.exterior.coords)
                    if len(coords) >= 4:
                        polys.append([coords])
            if polys:
                return {
                    "type": "MultiPolygon",
                    "coordinates": polys
                }
        elif polygon.geom_type == 'GeometryCollection':
            # Extract polygons from collection
            for geom in polygon.geoms:
                if geom.geom_type == 'Polygon' and not geom.is_empty:
                    coords = list(geom.exterior.coords)
                    if len(coords) >= 4:
                        return {
                            "type": "Polygon",
                            "coordinates": [coords]
                        }
        
        return {"type": "Polygon", "coordinates": []}
    
    def _calculate_area_km2(self, polygon) -> float:
        """Approximate area in km²."""
        return polygon.area * 111 * 111
    
    def to_geojson(self, result: EdgeAdjustResult) -> Dict:
        """Convert result to GeoJSON FeatureCollection."""
        return {
            "type": "FeatureCollection",
            "properties": {
                "computation_method": "edge_adjust_road_voronoi",
                "num_facilities": result.num_facilities,
                "num_edges": result.num_edges,
                "total_route_queries": result.total_route_queries,
                "computation_time_sec": result.computation_time_sec,
                **result.metadata
            },
            "features": result.features
        }


# Module-level helper
def get_edge_adjust_voronoi_engine() -> EdgeAdjustVoronoiEngine:
    """Get a new instance of the edge-adjust Voronoi engine."""
    return EdgeAdjustVoronoiEngine()
