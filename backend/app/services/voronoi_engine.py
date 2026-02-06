"""
Voronoi computation engine - core geospatial processing
Uses a robust algorithm to handle infinite Voronoi regions.
"""
from typing import List, Tuple, Optional, Dict, Any
import numpy as np
import os
from scipy.spatial import Voronoi
from shapely.geometry import Polygon, MultiPolygon, box, Point
from shapely.ops import unary_union
import geopandas as gpd
import pyproj


class VoronoiEngine:
    """
    Computes Voronoi diagrams with proper projection handling.
    """
    
    # India approximate bounding box
    INDIA_BOUNDS = {
        "min_lng": 68.0,
        "max_lng": 97.5,
        "min_lat": 6.5,
        "max_lat": 37.5,
    }
    
    # UTM zone 44N (covers central India) - good for most calculations
    CRS_WGS84 = "EPSG:4326"
    CRS_PROJECTED = "EPSG:32644"  # UTM zone 44N
    
    # Cached India boundary geometry (loaded from shapefile)
    _india_boundary_wgs84 = None
    _india_boundary_projected = None
    
    def __init__(self):
        # Set up coordinate transformers
        self.wgs84 = pyproj.CRS(self.CRS_WGS84)
        self.projected = pyproj.CRS(self.CRS_PROJECTED)
        
        self.to_projected = pyproj.Transformer.from_crs(
            self.wgs84, self.projected, always_xy=True
        )
        self.to_wgs84 = pyproj.Transformer.from_crs(
            self.projected, self.wgs84, always_xy=True
        )
        
        # Load India boundary from shapefile on first instantiation
        self._load_india_boundary()
    
    def _load_india_boundary(self):
        """Load India boundary from shapefile and cache it."""
        if VoronoiEngine._india_boundary_wgs84 is not None:
            return  # Already loaded
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        shapefile_path = os.path.join(base_dir, "data", "boundaries", "india_st.shp")
        
        if not os.path.exists(shapefile_path):
            print(f"Warning: India shapefile not found at {shapefile_path}")
            print("Falling back to bounding box for clipping.")
            return
        
        try:
            # Load the shapefile
            gdf = gpd.read_file(shapefile_path)
            
            # Ensure CRS is WGS84
            if gdf.crs is None:
                gdf = gdf.set_crs("EPSG:4326")
            elif gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs("EPSG:4326")
            
            # Dissolve all state geometries into a single unified boundary
            unified_boundary = unary_union(gdf.geometry)
            
            # Handle invalid geometries
            if not unified_boundary.is_valid:
                unified_boundary = unified_boundary.buffer(0)
            
            VoronoiEngine._india_boundary_wgs84 = unified_boundary
            
            # Also create projected version for Voronoi clipping
            gdf_projected = gdf.to_crs(self.CRS_PROJECTED)
            projected_boundary = unary_union(gdf_projected.geometry)
            if not projected_boundary.is_valid:
                projected_boundary = projected_boundary.buffer(0)
            VoronoiEngine._india_boundary_projected = projected_boundary
            
            print(f"Loaded India boundary from shapefile ({len(gdf)} states)")
            
        except Exception as e:
            print(f"Error loading India shapefile: {e}")
            print("Falling back to bounding box for clipping.")
    
    def _get_state_boundary_wgs84(self, state_name: str) -> Optional[Polygon]:
        """Load boundary for a specific state from states.geojson in WGS84."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        geojson_path = os.path.join(base_dir, "data", "states.geojson")
        
        if not os.path.exists(geojson_path):
            return None
        
        try:
            gdf = gpd.read_file(geojson_path)
            
            # Ensure CRS is WGS84
            if gdf.crs is None:
                gdf = gdf.set_crs("EPSG:4326")
            elif gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs("EPSG:4326")
            
            # Find the state (case-insensitive)
            state_gdf = gdf[gdf['state'].str.lower() == state_name.lower()]
            
            if len(state_gdf) == 0:
                return None
            
            # Get the geometry
            state_geom = state_gdf.iloc[0].geometry
            if not state_geom.is_valid:
                state_geom = state_geom.buffer(0)
            
            return state_geom
            
        except Exception as e:
            print(f"Error loading state boundary WGS84: {e}")
            return None

    def _get_state_boundary(self, state_name: str) -> Optional[Polygon]:
        """Load boundary for a specific state from states.geojson in Projected CRS."""
        state_geom = self._get_state_boundary_wgs84(state_name)
        if state_geom is None:
            return None
        
        try:
            # Project to UTM for Voronoi clipping
            gs = gpd.GeoSeries([state_geom], crs="EPSG:4326")
            gs_proj = gs.to_crs(self.CRS_PROJECTED)
            projected_geom = gs_proj.iloc[0]
            
            if not projected_geom.is_valid:
                projected_geom = projected_geom.buffer(0)
            
            return projected_geom
            
        except Exception as e:
            print(f"Error projecting state boundary: {e}")
            return None
    
    def _project_coords(self, coords: List[Tuple[float, float]]) -> np.ndarray:
        """Project WGS84 coordinates to UTM"""
        projected = []
        for lng, lat in coords:
            x, y = self.to_projected.transform(lng, lat)
            projected.append([x, y])
        return np.array(projected)
    
    def _unproject_coords(self, coords: np.ndarray) -> List[Tuple[float, float]]:
        """Unproject UTM coordinates back to WGS84"""
        unprojected = []
        for x, y in coords:
            lng, lat = self.to_wgs84.transform(x, y)
            unprojected.append((lng, lat))
        return unprojected
    
    def _get_bounding_box(self, coords: np.ndarray, buffer: float = 0.5) -> Polygon:
        """
        Create bounding box around coordinates with buffer.
        Buffer is fraction of extent.
        """
        min_x, min_y = coords.min(axis=0)
        max_x, max_y = coords.max(axis=0)
        
        width = max_x - min_x
        height = max_y - min_y
        
        # Ensure minimum size
        width = max(width, 100000)  # At least 100km
        height = max(height, 100000)
        
        # Add buffer
        buf_x = width * buffer
        buf_y = height * buffer
        
        return box(
            min_x - buf_x,
            min_y - buf_y,
            max_x + buf_x,
            max_y + buf_y
        )
    
    def _voronoi_regions(
        self,
        vor: Voronoi,
        bounding_box: Polygon
    ) -> List[Tuple[int, Polygon]]:
        """
        Reconstruct all Voronoi regions including infinite ones.
        Extends infinite ridges to bounding box for proper clipping.
        
        This implementation handles all points including closely-spaced ones.
        """
        from scipy.spatial import ConvexHull
        
        center = vor.points.mean(axis=0)
        
        # Compute a radius large enough to contain all points
        ptp_bound = np.ptp(vor.points, axis=0)
        radius = max(ptp_bound.max() * 10, 5000000)  # At least 5000km for full India coverage
        
        polygons = []
        
        for point_idx, region_idx in enumerate(vor.point_region):
            region = vor.regions[region_idx]
            
            # Skip empty regions
            if not region:
                continue
            
            try:
                if -1 not in region:
                    # Finite region - use vertices directly
                    vertices = vor.vertices[region]
                    poly = self._make_valid_polygon(vertices)
                    if poly is not None:
                        clipped = self._clip_polygon(poly, bounding_box)
                        if clipped is not None:
                            polygons.append((point_idx, clipped))
                    continue
                
                # Infinite region - need to extend ridges to far points
                # Collect all vertices for this region (both finite and extended)
                all_vertices = []
                
                for ridge_idx, (p1, p2) in enumerate(vor.ridge_points):
                    if p1 != point_idx and p2 != point_idx:
                        continue
                    
                    v1, v2 = vor.ridge_vertices[ridge_idx]
                    other_point = p2 if p1 == point_idx else p1
                    
                    # Add finite vertices
                    if v1 >= 0:
                        all_vertices.append(tuple(vor.vertices[v1]))
                    if v2 >= 0:
                        all_vertices.append(tuple(vor.vertices[v2]))
                    
                    # Extend infinite vertices
                    if v1 == -1 or v2 == -1:
                        finite_v = v2 if v1 == -1 else v1
                        if finite_v >= 0:
                            # Compute direction perpendicular to the ridge
                            t = vor.points[other_point] - vor.points[point_idx]
                            norm = np.linalg.norm(t)
                            if norm > 0:
                                t = t / norm
                                n = np.array([-t[1], t[0]])
                                
                                midpoint = (vor.points[point_idx] + vor.points[other_point]) / 2
                                direction = np.sign(np.dot(midpoint - center, n)) * n
                                
                                far_point = vor.vertices[finite_v] + direction * radius
                                all_vertices.append(tuple(far_point))
                
                # De-duplicate vertices (close points can create duplicate vertices)
                unique_vertices = list(set(all_vertices))
                
                if len(unique_vertices) >= 3:
                    # Use ConvexHull to properly order vertices
                    vertices_array = np.array(unique_vertices)
                    try:
                        hull = ConvexHull(vertices_array)
                        ordered_vertices = vertices_array[hull.vertices]
                        poly = self._make_valid_polygon(ordered_vertices)
                    except Exception:
                        # Fallback: try angle-based sorting if ConvexHull fails
                        point_center = vor.points[point_idx]
                        angles = [np.arctan2(v[1] - point_center[1], v[0] - point_center[0]) 
                                  for v in unique_vertices]
                        sorted_vertices = [v for _, v in sorted(zip(angles, unique_vertices))]
                        poly = self._make_valid_polygon(np.array(sorted_vertices))
                    
                    if poly is not None:
                        clipped = self._clip_polygon(poly, bounding_box)
                        if clipped is not None:
                            polygons.append((point_idx, clipped))
                            
            except Exception as e:
                # Log but don't fail - continue processing other points
                print(f"Warning: Could not process Voronoi region for point {point_idx}: {e}")
                continue
        
        return polygons
    
    def _make_valid_polygon(self, vertices: np.ndarray) -> Optional[Polygon]:
        """Create a valid polygon from vertices, handling edge cases."""
        if len(vertices) < 3:
            return None
        try:
            poly = Polygon(vertices)
            if not poly.is_valid:
                # Try to fix with buffer(0)
                poly = poly.buffer(0)
            if poly.is_valid and not poly.is_empty and poly.area > 0:
                return poly
        except Exception:
            pass
        return None
    
    def _clip_polygon(self, poly: Polygon, bounding_box: Polygon) -> Optional[Polygon]:
        """Clip a polygon to the bounding box, returning the largest piece."""
        try:
            clipped = poly.intersection(bounding_box)
            if clipped.is_empty or clipped.area <= 0:
                return None
            if isinstance(clipped, MultiPolygon):
                clipped = max(clipped.geoms, key=lambda p: p.area)
            if isinstance(clipped, Polygon) and clipped.area > 0:
                return clipped
        except Exception:
            pass
        return None
    
    def compute_voronoi(
        self,
        coords: List[Tuple[float, float]],
        names: List[str],
        facility_ids: List[str],
        types: Optional[List[str]] = None,
        clip_to_india: bool = True,
        state_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compute Voronoi diagram and return as GeoJSON.
        
        Args:
            coords: List of (longitude, latitude) tuples
            names: Facility names
            facility_ids: Facility IDs
            types: Optional facility types
            clip_to_india: Whether to clip to India bounds
            state_filter: Optional state name to clip to (overrides clip_to_india)
            
        Returns:
            GeoJSON FeatureCollection
        """
        if len(coords) < 3:
            raise ValueError("Need at least 3 points for Voronoi")
        
        # Project coordinates to UTM for accurate computation
        projected_coords = self._project_coords(coords)
        
        # Compute Voronoi diagram
        vor = Voronoi(projected_coords)
        
        # Get bounding polygon for clipping
        if state_filter:
            # Use state boundary for clipping
            state_boundary = self._get_state_boundary(state_filter)
            if state_boundary is not None:
                bounding_box = state_boundary
            else:
                print(f"Warning: State '{state_filter}' not found, falling back to India boundary")
                if clip_to_india and VoronoiEngine._india_boundary_projected is not None:
                    bounding_box = VoronoiEngine._india_boundary_projected
                else:
                    bounding_box = self._get_bounding_box(projected_coords, buffer=0.5)
        elif clip_to_india and VoronoiEngine._india_boundary_projected is not None:
            # Use the cached India boundary from shapefile
            bounding_box = VoronoiEngine._india_boundary_projected
        else:
            bounding_box = self._get_bounding_box(projected_coords, buffer=0.5)
        
        # Convert to polygons clipped to bounding box
        polygons = self._voronoi_regions(vor, bounding_box)
        
        # Build GeoJSON features
        features = []
        for point_idx, polygon in polygons:
            # Unproject polygon coordinates back to WGS84
            exterior_coords = list(polygon.exterior.coords)
            unprojected_exterior = self._unproject_coords(np.array(exterior_coords))
            
            feature = {
                "type": "Feature",
                "id": facility_ids[point_idx] if point_idx < len(facility_ids) else str(point_idx),
                "properties": {
                    "name": names[point_idx] if point_idx < len(names) else f"Facility_{point_idx}",
                    "facility_id": facility_ids[point_idx] if point_idx < len(facility_ids) else str(point_idx),
                    "type": types[point_idx] if types and point_idx < len(types) else None,
                    "area_sq_km": polygon.area / 1_000_000,  # Convert from sq meters
                    "centroid_lng": coords[point_idx][0],
                    "centroid_lat": coords[point_idx][1],
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [unprojected_exterior]
                }
            }
            features.append(feature)
        
        return {
            "type": "FeatureCollection",
            "features": features
        }
    
    def compute_voronoi_with_dcel(
        self,
        coords: List[Tuple[float, float]],
        names: List[str],
        facility_ids: List[str],
        types: Optional[List[str]] = None,
        clip_to_india: bool = True,
        state_filter: Optional[str] = None
    ) -> Tuple[Dict[str, Any], 'DCEL']:
        """
        Compute Voronoi diagram and build DCEL index.
        
        Returns:
            Tuple of (GeoJSON FeatureCollection, DCEL instance)
        """
        from app.services.dcel import DCEL, set_current_dcel
        
        geojson = self.compute_voronoi(
            coords=coords,
            names=names,
            facility_ids=facility_ids,
            types=types,
            clip_to_india=clip_to_india,
            state_filter=state_filter
        )
        
        dcel = DCEL()
        dcel.build_from_voronoi(geojson)
        set_current_dcel(dcel)
        
        return geojson, dcel

