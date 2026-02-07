"""
Road Network Service - Downloads and caches OSM road networks, computes road-based Voronoi.
"""
import os
import pickle
from typing import List, Dict, Any, Optional, Tuple
import osmnx as ox
import networkx as nx
import numpy as np
from shapely.geometry import Polygon, MultiPolygon, Point, mapping
from shapely.ops import unary_union
import geopandas as gpd

# Configure osmnx
ox.settings.use_cache = True
ox.settings.log_console = False


class RoadNetworkService:
    """Service for road network-based Voronoi computation."""
    
    CACHE_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
        "cache", 
        "road_graphs"
    )
    
    # Available districts with pre-computed road networks
    # Using bounding box for reliable download
    # Delhi bbox coordinates
    AVAILABLE_DISTRICTS = {
        "Delhi": {
            "display_name": "Delhi",
            # bbox format: (left, bottom, right, top) = (west, south, east, north)
            "bbox": (76.8372, 28.4041, 77.3480, 28.8846),
            "network_type": "drive"
        }
    }
    
    def __init__(self):
        os.makedirs(self.CACHE_DIR, exist_ok=True)
        self._graph_cache: Dict[str, nx.MultiDiGraph] = {}
        self._boundary_cache: Dict[str, Polygon] = {}
    
    def get_available_districts(self) -> List[Dict[str, str]]:
        """Return list of districts with available road networks."""
        return [
            {"id": k, "name": v["display_name"]} 
            for k, v in self.AVAILABLE_DISTRICTS.items()
        ]
    
    def _get_cache_path(self, district_id: str) -> str:
        """Get cache file path for a district's road graph."""
        safe_name = district_id.replace(" ", "_").lower()
        return os.path.join(self.CACHE_DIR, f"{safe_name}_road_graph.pkl")
    
    def _get_boundary_cache_path(self, district_id: str) -> str:
        """Get cache file path for a district's boundary."""
        safe_name = district_id.replace(" ", "_").lower()
        return os.path.join(self.CACHE_DIR, f"{safe_name}_boundary.pkl")
    
    def load_or_download_graph(self, district_id: str) -> nx.MultiDiGraph:
        """Load road network graph from cache or download from OSM."""
        if district_id not in self.AVAILABLE_DISTRICTS:
            raise ValueError(f"District '{district_id}' not available for road network analysis")
        
        # Check in-memory cache first
        if district_id in self._graph_cache:
            return self._graph_cache[district_id]
        
        cache_path = self._get_cache_path(district_id)
        
        # Try to load from disk cache
        if os.path.exists(cache_path):
            print(f"Loading cached road network for {district_id}...")
            with open(cache_path, 'rb') as f:
                G = pickle.load(f)
            self._graph_cache[district_id] = G
            return G
        
        # Download from OSM
        print(f"Downloading road network for {district_id}... (this may take a few minutes)")
        config = self.AVAILABLE_DISTRICTS[district_id]
        
        try:
            # Use bounding box approach for reliable download
            bbox = config["bbox"]  # (west, south, east, north)
            G = ox.graph_from_bbox(
                bbox=bbox,  # (left, bottom, right, top)
                network_type=config["network_type"],
                simplify=True
            )
            
            # Add edge lengths if not present
            G = ox.distance.add_edge_lengths(G)
            
            # Cache to disk
            with open(cache_path, 'wb') as f:
                pickle.dump(G, f)
            
            # Create boundary from bbox
            west, south, east, north = bbox
            boundary = Polygon([
                (west, south), (east, south), (east, north), (west, north), (west, south)
            ])
            boundary_cache_path = self._get_boundary_cache_path(district_id)
            with open(boundary_cache_path, 'wb') as f:
                pickle.dump(boundary, f)
            self._boundary_cache[district_id] = boundary
            
            self._graph_cache[district_id] = G
            print(f"Road network cached: {len(G.nodes)} nodes, {len(G.edges)} edges")
            return G
            
        except Exception as e:
            raise RuntimeError(f"Failed to download road network for {district_id}: {str(e)}")
    
    def get_district_boundary(self, district_id: str) -> Optional[Dict[str, Any]]:
        """Get the boundary GeoJSON for a district."""
        if district_id not in self.AVAILABLE_DISTRICTS:
            return None
        
        # Check cache
        if district_id in self._boundary_cache:
            boundary = self._boundary_cache[district_id]
        else:
            boundary_cache_path = self._get_boundary_cache_path(district_id)
            if os.path.exists(boundary_cache_path):
                with open(boundary_cache_path, 'rb') as f:
                    boundary = pickle.load(f)
                self._boundary_cache[district_id] = boundary
            else:
                # Create boundary from bbox
                config = self.AVAILABLE_DISTRICTS[district_id]
                bbox = config["bbox"]
                west, south, east, north = bbox
                boundary = Polygon([
                    (west, south), (east, south), (east, north), (west, north), (west, south)
                ])
                with open(boundary_cache_path, 'wb') as f:
                    pickle.dump(boundary, f)
                self._boundary_cache[district_id] = boundary
        
        return {
            "type": "Feature",
            "properties": {"name": district_id},
            "geometry": mapping(boundary)
        }
    
    def filter_facilities_in_district(
        self, 
        facilities: List[Dict[str, Any]], 
        district_id: str
    ) -> List[Dict[str, Any]]:
        """Filter facilities to only those within the district boundary."""
        boundary_geojson = self.get_district_boundary(district_id)
        if not boundary_geojson:
            return facilities
        
        boundary = self._boundary_cache.get(district_id)
        if not boundary:
            return facilities
        
        filtered = []
        for f in facilities:
            point = Point(f["lng"], f["lat"])
            if boundary.contains(point):
                filtered.append(f)
        
        return filtered
    
    def compute_road_voronoi(
        self,
        facilities: List[Dict[str, Any]],
        district_id: str
    ) -> Dict[str, Any]:
        """
        Compute Voronoi diagram based on road network distances.
        
        Args:
            facilities: List of facility dicts with lat, lng, name, id
            district_id: ID of the district to compute for
            
        Returns:
            GeoJSON FeatureCollection of Voronoi polygons
        """
        if len(facilities) < 2:
            raise ValueError("At least 2 facilities are required for road Voronoi")
        
        # Load road network
        G = self.load_or_download_graph(district_id)
        
        # Get largest strongly connected component for reliable routing
        if G.is_directed():
            largest_cc = max(nx.strongly_connected_components(G), key=len)
            G_connected = G.subgraph(largest_cc).copy()
        else:
            largest_cc = max(nx.connected_components(G), key=len)
            G_connected = G.subgraph(largest_cc).copy()
        
        # Snap facilities to nearest network nodes
        facility_nodes = []
        valid_facilities = []
        
        for f in facilities:
            try:
                nearest_node = ox.nearest_nodes(G_connected, f["lng"], f["lat"])
                facility_nodes.append(nearest_node)
                valid_facilities.append(f)
            except Exception as e:
                print(f"Warning: Could not snap facility {f.get('name', 'Unknown')} to network: {e}")
                continue
        
        if len(facility_nodes) < 2:
            raise ValueError("Not enough facilities could be snapped to the road network")
        
        # Remove duplicate nodes (multiple facilities at same network node)
        unique_nodes = list(set(facility_nodes))
        node_to_facility = {}
        for node, facility in zip(facility_nodes, valid_facilities):
            if node not in node_to_facility:
                node_to_facility[node] = facility
        
        print(f"Computing road Voronoi for {len(unique_nodes)} unique network nodes...")
        
        # Compute Voronoi cells using NetworkX
        # This assigns each node in the graph to its nearest center (facility node)
        try:
            voronoi_dict = nx.voronoi_cells(G_connected, unique_nodes, weight='length')
        except Exception as e:
            raise RuntimeError(f"Failed to compute Voronoi cells: {str(e)}")
        
        # Convert node cells to polygons
        features = []
        node_positions = {node: (G_connected.nodes[node]['x'], G_connected.nodes[node]['y']) 
                         for node in G_connected.nodes}
        
        for center_node, cell_nodes in voronoi_dict.items():
            if center_node not in node_to_facility:
                continue
                
            facility = node_to_facility[center_node]
            
            # Get positions of all nodes in this cell
            cell_points = [node_positions[n] for n in cell_nodes if n in node_positions]
            
            if len(cell_points) < 3:
                continue
            
            # Create convex hull of the cell nodes to form a polygon
            try:
                from scipy.spatial import ConvexHull
                points_array = np.array(cell_points)
                hull = ConvexHull(points_array)
                hull_points = points_array[hull.vertices]
                polygon = Polygon(hull_points)
                
                if not polygon.is_valid:
                    polygon = polygon.buffer(0)
                
                if polygon.is_empty or polygon.area == 0:
                    continue
                
                # Calculate area in sq km (approximate)
                # Using a simple lat/lng to km conversion
                centroid = polygon.centroid
                lat_factor = 111.32  # km per degree latitude
                lng_factor = 111.32 * np.cos(np.radians(centroid.y))
                area_sq_km = polygon.area * lat_factor * lng_factor
                
                feature = {
                    "type": "Feature",
                    "properties": {
                        "name": facility.get("name", "Unknown"),
                        "facility_id": facility.get("id", str(center_node)),
                        "type": facility.get("type"),
                        "area_sq_km": round(area_sq_km, 2),
                        "centroid_lat": centroid.y,
                        "centroid_lng": centroid.x,
                        "network_nodes": len(cell_nodes),
                        "distance_type": "road"
                    },
                    "geometry": mapping(polygon)
                }
                features.append(feature)
                
            except Exception as e:
                print(f"Warning: Could not create polygon for facility {facility.get('name')}: {e}")
                continue
        
        print(f"Created {len(features)} road Voronoi polygons")
        
        return {
            "type": "FeatureCollection",
            "features": features
        }
    
    def get_road_distance(
        self,
        from_lat: float,
        from_lng: float,
        to_lat: float,
        to_lng: float,
        district_id: str
    ) -> Optional[float]:
        """
        Calculate road distance between two points in km.
        
        Returns None if no path exists.
        """
        try:
            G = self.load_or_download_graph(district_id)
            
            from_node = ox.nearest_nodes(G, from_lng, from_lat)
            to_node = ox.nearest_nodes(G, to_lng, to_lat)
            
            # Calculate shortest path length
            path_length = nx.shortest_path_length(G, from_node, to_node, weight='length')
            
            # Convert meters to km
            return path_length / 1000.0
            
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
        except Exception as e:
            print(f"Error calculating road distance: {e}")
            return None
    
    def get_road_edges_geojson(self, district_id: str, simplify: bool = True) -> Dict[str, Any]:
        """
        Get road network edges as GeoJSON for visualization.
        
        Args:
            district_id: ID of the district
            simplify: If True, only return major roads to reduce data size
            
        Returns:
            GeoJSON FeatureCollection of road edges as LineStrings
        """
        G = self.load_or_download_graph(district_id)
        
        # Convert graph to GeoDataFrame of edges
        try:
            edges_gdf = ox.graph_to_gdfs(G, nodes=False, edges=True)
        except Exception as e:
            raise RuntimeError(f"Failed to convert graph to edges: {str(e)}")
        
        # Optionally filter to major roads only
        if simplify and 'highway' in edges_gdf.columns:
            # Keep major road types only
            major_types = ['motorway', 'trunk', 'primary', 'secondary', 'tertiary',
                          'motorway_link', 'trunk_link', 'primary_link', 'secondary_link']
            
            # Handle list values in highway column
            def is_major_road(highway_val):
                if isinstance(highway_val, list):
                    return any(h in major_types for h in highway_val)
                return highway_val in major_types
            
            mask = edges_gdf['highway'].apply(is_major_road)
            edges_gdf = edges_gdf[mask]
        
        # Convert to GeoJSON
        features = []
        for idx, row in edges_gdf.iterrows():
            geometry = row.geometry
            if geometry is not None and not geometry.is_empty and geometry.is_valid:
                # Skip any geometry with NaN or Inf coordinates
                try:
                    coords = list(geometry.coords) if hasattr(geometry, 'coords') else []
                    has_invalid = False
                    for coord in coords:
                        for val in coord:
                            if not np.isfinite(val):
                                has_invalid = True
                                break
                        if has_invalid:
                            break
                    if has_invalid:
                        continue
                except:
                    pass  # If we can't check, continue anyway
                
                # Get road type for styling
                highway = row.get('highway', 'road')
                if isinstance(highway, list):
                    highway = highway[0] if highway else 'road'
                
                name = row.get('name', '')
                if isinstance(name, list):
                    name = name[0] if name else ''
                
                # Handle NaN/Inf in length
                length_m = row.get('length', 0)
                if not np.isfinite(length_m):
                    length_m = 0
                
                feature = {
                    "type": "Feature",
                    "properties": {
                        "highway": highway,
                        "name": name or '',
                        "length_m": float(length_m)
                    },
                    "geometry": mapping(geometry)
                }
                features.append(feature)
        
        print(f"Returning {len(features)} road segments for visualization")
        
        return {
            "type": "FeatureCollection",
            "features": features
        }

