"""
Additive Weighted Voronoi Engine

Implements road-adjusted Voronoi using additive weights:
- Each facility gets a "road penalty" based on its road accessibility
- effective_distance = euclidean_distance + road_penalty
- Facilities with poor road access → higher penalty → smaller cells

This produces mathematically valid Voronoi cells that reflect road network influence.
"""

import logging
import time
import numpy as np
import httpx
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from scipy.spatial import Voronoi, KDTree
from shapely.geometry import Polygon, Point, MultiPoint, LineString
from shapely.ops import unary_union

from .voronoi_engine import VoronoiEngine
from .routing_service import get_routing_service, RoutingService

logger = logging.getLogger(__name__)


@dataclass
class WeightedVoronoiConfig:
    """Configuration for weighted Voronoi computation."""
    num_neighbor_samples: int = 5  # How many neighbors to sample for penalty calculation
    penalty_scale: float = 1.0  # Scale factor for road penalty


@dataclass
class WeightedVoronoiResult:
    """Result of weighted Voronoi computation."""
    type: str = "weighted_road_voronoi"
    num_facilities: int = 0
    total_route_queries: int = 0
    computation_time_sec: float = 0.0
    features: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


class WeightedVoronoiEngine:
    """
    Computes additive weighted Voronoi diagrams.
    
    Algorithm:
    1. For each facility, compute road penalty by sampling distances to neighbors
    2. Road penalty = avg(road_distance - euclidean_distance) to neighbors
    3. Create virtual facility positions by shifting each facility outward by its penalty
    4. Compute standard Voronoi on virtual positions
    5. Map cells back to original facilities
    
    The "virtual position shift" is mathematically equivalent to additive weighting
    because increasing distance to a facility shrinks its Voronoi cell.
    """
    
    def __init__(self, voronoi_engine: Optional[VoronoiEngine] = None, routing_service: Optional[RoutingService] = None):
        self.voronoi_engine = voronoi_engine or VoronoiEngine()
        self.routing = routing_service or get_routing_service()
    
    def compute(
        self,
        facilities: List[Dict],
        clip_to_india: bool = True,
        state_filter: Optional[str] = None,
        config: Optional[WeightedVoronoiConfig] = None
    ) -> WeightedVoronoiResult:
        """
        Compute additive weighted Voronoi.
        
        Args:
            facilities: List of {"id", "name", "lat", "lng", "type"} dicts
            clip_to_india: Whether to clip to India boundary
            state_filter: Optional state name to clip to
            config: Configuration options
            
        Returns:
            WeightedVoronoiResult with road-weighted polygons
        """
        start_time = time.time()
        config = config or WeightedVoronoiConfig()
        
        if len(facilities) < 3:
            raise ValueError("Need at least 3 facilities")
        
        print(f"\n{'='*60}", flush=True)
        print(f"WEIGHTED VORONOI: {len(facilities)} facilities", flush=True)
        print(f"{'='*60}", flush=True)
        
        # Build facility map
        facility_map = {f.get("id", str(i)): f for i, f in enumerate(facilities)}
        
        # Step 1: Compute Euclidean Voronoi to get adjacency
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
        
        # Extract only facilities that have cells in the result (i.e., in the selected state)
        result_facility_ids = set()
        for feat in geojson.get("features", []):
            fid = feat.get("properties", {}).get("facility_id")
            if fid:
                result_facility_ids.add(fid)
        
        # Filter to only facilities in the result
        filtered_facilities = []
        filtered_facility_ids = []
        for i, f in enumerate(facilities):
            fid = f.get("id", str(i))
            if fid in result_facility_ids:
                filtered_facilities.append(f)
                filtered_facility_ids.append(fid)
        
        print(f"  Done in {time.time() - step1_start:.2f}s ({len(filtered_facility_ids)} cells in state)", flush=True)
        
        # Step 2: Compute road penalties only for facilities with cells
        print(f"\n[Step 2/4] Computing road penalties for {len(filtered_facility_ids)} facilities...", flush=True)
        step2_start = time.time()
        penalties, query_count = self._compute_road_penalties(
            filtered_facilities, filtered_facility_ids, dcel, config
        )
        print(f"  Done in {time.time() - step2_start:.2f}s, {query_count} queries", flush=True)
        
        # Step 3: Compute weighted Voronoi by shifting facility positions
        print(f"\n[Step 3/4] Computing weighted Voronoi...", flush=True)
        step3_start = time.time()
        
        # Get boundary
        if state_filter:
            boundary = self.voronoi_engine._get_state_boundary_wgs84(state_filter)
        elif clip_to_india:
            boundary = VoronoiEngine._india_boundary_wgs84
        else:
            boundary = MultiPoint(coords).convex_hull.buffer(0.5)
        
        weighted_geojson = self._compute_weighted_voronoi(
            facilities, facility_ids, penalties, boundary, config
        )
        print(f"  Done in {time.time() - step3_start:.2f}s", flush=True)
        
        # Step 4: Build features with original properties
        print(f"\n[Step 4/4] Building output features...", flush=True)
        step4_start = time.time()
        
        features = []
        for fid, poly in weighted_geojson.items():
            fac = facility_map.get(fid, {})
            penalty = penalties.get(fid, 0)
            
            # Find original properties from Euclidean result
            original_props = {}
            for feat in geojson.get("features", []):
                if feat.get("properties", {}).get("facility_id") == fid:
                    original_props = feat.get("properties", {})
                    break
            
            feature = {
                "type": "Feature",
                "properties": {
                    **original_props,
                    "facility_id": fid,
                    "name": fac.get("name", fid),
                    "cell_type": "weighted_road",
                    "road_penalty_km": round(penalty / 1000, 2),
                    "area_sq_km": self._calculate_area_km2(poly),
                },
                "geometry": self._polygon_to_geojson(poly)
            }
            features.append(feature)
        
        print(f"  Built {len(features)} weighted cells", flush=True)
        print(f"  Done in {time.time() - step4_start:.2f}s", flush=True)
        
        computation_time = time.time() - start_time
        
        result = WeightedVoronoiResult(
            num_facilities=len(facilities),
            total_route_queries=query_count,
            computation_time_sec=round(computation_time, 2),
            features=features,
            metadata={
                "method": "additive_weighted_voronoi",
                "penalty_scale": config.penalty_scale,
                "penalties": {fid: round(p / 1000, 2) for fid, p in penalties.items()}
            }
        )
        
        print(f"\n{'='*60}", flush=True)
        print(f"COMPLETE: {computation_time:.2f}s, {query_count} queries, {len(features)} cells", flush=True)
        print(f"{'='*60}\n", flush=True)
        
        return result
    
    def _compute_road_penalties(
        self,
        facilities: List[Dict],
        facility_ids: List[str],
        dcel,
        config: WeightedVoronoiConfig
    ) -> Tuple[Dict[str, float], int]:
        """
        Compute road penalty for each facility.
        
        Penalty = average(road_distance - euclidean_distance) to nearest neighbors.
        Positive penalty = poor road access = smaller cell.
        """
        penalties = {}
        total_queries = 0
        
        # Build facility coordinate lookup
        fac_coords = {
            f.get("id", str(i)): (f["lat"], f["lng"]) 
            for i, f in enumerate(facilities)
        }
        
        for i, fid in enumerate(facility_ids):
            lat, lng = fac_coords[fid]
            
            print(f"  Facility {i+1}/{len(facility_ids)}: {fid[:12]}... ", end="", flush=True)
            
            # Find nearest neighbors by Euclidean distance
            distances = []
            for other_fid in facility_ids:
                if other_fid == fid:
                    continue
                other_lat, other_lng = fac_coords[other_fid]
                euc_dist = self._euclidean_distance_meters(lat, lng, other_lat, other_lng)
                distances.append((other_fid, euc_dist))
            
            # Sort by Euclidean distance and take nearest N
            distances.sort(key=lambda x: x[1])
            neighbors = distances[:config.num_neighbor_samples]
            
            # Query road distances to all neighbors in one batch
            neighbor_locs = []
            neighbor_euc_dists = []
            for other_fid, euc_dist in neighbors:
                other_lat, other_lng = fac_coords[other_fid]
                neighbor_locs.append((other_lat, other_lng))
                neighbor_euc_dists.append(euc_dist)
            
            penalty_samples = []
            if neighbor_locs:
                try:
                    results = self.routing.batch_distance_sync(lat, lng, neighbor_locs)
                    total_queries += 1
                    
                    for res, euc_dist in zip(results, neighbor_euc_dists):
                        if res.connected:
                            # Penalty = how much longer road is than Euclidean
                            road_dist_m = res.distance_km * 1000
                            penalty = road_dist_m - euc_dist
                            penalty_samples.append(penalty)
                except Exception as e:
                    logger.debug(f"Batch penalty query failed for {fid}: {e}")
            
            # Average penalty
            if penalty_samples:
                avg_penalty = sum(penalty_samples) / len(penalty_samples)
                penalties[fid] = avg_penalty * config.penalty_scale
                print(f"penalty={avg_penalty/1000:.1f}km", flush=True)
            else:
                penalties[fid] = 0
                print(f"penalty=0 (no road data)", flush=True)
        
        return penalties, total_queries
    
    def _compute_weighted_voronoi(
        self,
        facilities: List[Dict],
        facility_ids: List[str],
        penalties: Dict[str, float],
        boundary: Polygon,
        config: WeightedVoronoiConfig
    ) -> Dict[str, Polygon]:
        """
        Compute weighted Voronoi by shifting facility positions.
        
        For additive weighted Voronoi, we simulate it by:
        1. Shifting each facility away from the centroid by its penalty amount
        2. Computing standard Voronoi on shifted positions
        3. Mapping results back to original facilities
        
        Alternatively, we sample a dense grid and assign each point to the 
        facility with minimum (euclidean_distance + penalty).
        """
        # Method: Dense grid sampling with weighted distance
        # This is more reliable than trying to compute analytic weighted Voronoi
        
        minx, miny, maxx, maxy = boundary.bounds
        
        # Create dense grid
        grid_size = 100  # 100x100 grid
        x_coords = np.linspace(minx, maxx, grid_size)
        y_coords = np.linspace(miny, maxy, grid_size)
        
        # Build lookup and KDTree for Euclidean distance optimization
        fac_coords = {
            f.get("id", str(i)): (f["lat"], f["lng"]) 
            for i, f in enumerate(facilities)
        }
        
        fac_coords_list = []
        for fid in facility_ids:
            fac_lat, fac_lng = fac_coords[fid]
            fac_coords_list.append([fac_lng, fac_lat])
            
        tree = KDTree(fac_coords_list)
        
        # Assign each grid point to facility with min weighted distance
        assignments = {}  # fid -> list of (x, y) points
        
        for x in x_coords:
            for y in y_coords:
                point = Point(x, y)
                if not boundary.contains(point):
                    continue
                
                # OPTIMIZATION: Only check top 20 nearest neighbors by Euclidean distance
                # The weighted neighbor is extremely likely to be among them
                dists, indices = tree.query([x, y], k=min(20, len(facility_ids)))
                
                min_dist = float('inf')
                best_fid = None
                
                for idx in indices:
                    fid = facility_ids[idx]
                    fac_lat, fac_lng = fac_coords[fid]
                    
                    # Use accurate Euclidean distance in meters
                    euc_dist_m = self._euclidean_distance_meters(y, x, fac_lat, fac_lng)
                    
                    # Add penalty (defaults to 0 for facilities outside the state)
                    penalty = penalties.get(fid, 0)
                    weighted_dist = euc_dist_m + penalty
                    
                    if weighted_dist < min_dist:
                        min_dist = weighted_dist
                        best_fid = fid
                
                if best_fid:
                    if best_fid not in assignments:
                        assignments[best_fid] = []
                    assignments[best_fid].append((x, y))
        
        # Convert point assignments to polygons using alpha shapes / convex hull
        result = {}
        for fid, points in assignments.items():
            if len(points) < 3:
                continue
            
            try:
                # Use convex hull for simplicity (alpha shapes would be better)
                mp = MultiPoint(points)
                hull = mp.convex_hull
                
                # Clip to boundary
                clipped = hull.intersection(boundary)
                
                if not clipped.is_empty:
                    result[fid] = clipped
            except Exception as e:
                logger.warning(f"Failed to create polygon for {fid}: {e}")
        
        return result
    
    def _query_road_distance(
        self, 
        lat1: float, lng1: float, 
        lat2: float, lng2: float,
        config: WeightedVoronoiConfig
    ) -> Optional[float]:
        """Query OSRM for road distance between two points using routing service."""
        try:
            result = self.routing.get_route_distance_sync(lat1, lng1, lat2, lng2)
            if result.connected:
                return result.distance_km * 1000  # Convert km to meters
            return None
        except Exception as e:
            logger.debug(f"Road distance query failed: {e}")
            return None
    
    def _euclidean_distance_meters(
        self, lat1: float, lng1: float, lat2: float, lng2: float
    ) -> float:
        """Calculate approximate Euclidean distance in meters."""
        # Simple approximation for India latitudes
        lat_m = (lat2 - lat1) * 111000
        lng_m = (lng2 - lng1) * 111000 * np.cos(np.radians((lat1 + lat2) / 2))
        return np.sqrt(lat_m**2 + lng_m**2)
    
    def _calculate_area_km2(self, polygon) -> float:
        """Calculate area in km² (rough approximation)."""
        if polygon is None or polygon.is_empty:
            return 0.0
        try:
            # At ~22°N (Gujarat), 1 degree ≈ 111km lat, 103km lng
            return polygon.area * 111 * 103
        except:
            return 0.0
    
    def _polygon_to_geojson(self, polygon) -> Dict:
        """Convert Shapely polygon to GeoJSON geometry."""
        if polygon is None or polygon.is_empty:
            return {"type": "Polygon", "coordinates": []}
        
        if polygon.geom_type == 'Polygon':
            return {
                "type": "Polygon",
                "coordinates": [list(polygon.exterior.coords)]
            }
        elif polygon.geom_type == 'MultiPolygon':
            # Take largest polygon
            largest = max(polygon.geoms, key=lambda p: p.area)
            return {
                "type": "Polygon", 
                "coordinates": [list(largest.exterior.coords)]
            }
        elif polygon.geom_type == 'GeometryCollection':
            for geom in polygon.geoms:
                if geom.geom_type == 'Polygon' and not geom.is_empty:
                    return {
                        "type": "Polygon",
                        "coordinates": [list(geom.exterior.coords)]
                    }
        
        return {"type": "Polygon", "coordinates": []}


def get_weighted_voronoi_engine() -> WeightedVoronoiEngine:
    """Get a new instance of the weighted Voronoi engine."""
    return WeightedVoronoiEngine()
