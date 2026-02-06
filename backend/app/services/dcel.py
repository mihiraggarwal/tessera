"""
DCEL (Doubly-Connected Edge List) data structure for spatial indexing of Voronoi diagrams.
Enables fast point-in-polygon queries and spatial relationships.
"""
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from shapely.geometry import Point, Polygon, MultiPolygon, box
from shapely.strtree import STRtree


@dataclass
class DCELVertex:
    """A vertex in the DCEL structure."""
    id: int
    x: float
    y: float
    incident_edge: Optional['DCELHalfEdge'] = None


@dataclass
class DCELFace:
    """A face (Voronoi cell) in the DCEL structure."""
    id: int
    facility_id: str
    facility_name: str
    outer_edge: Optional['DCELHalfEdge'] = None
    polygon: Optional[Polygon] = None
    properties: Dict = field(default_factory=dict)


@dataclass
class DCELHalfEdge:
    """A half-edge in the DCEL structure."""
    id: int
    origin: DCELVertex
    twin: Optional['DCELHalfEdge'] = None
    next: Optional['DCELHalfEdge'] = None
    prev: Optional['DCELHalfEdge'] = None
    face: Optional[DCELFace] = None


class DCEL:
    """
    Doubly-Connected Edge List for Voronoi diagram spatial indexing.
    
    Supports:
    - Fast point-in-polygon queries (which facility serves a location)
    - Spatial range queries
    - Adjacency relationships between facilities
    """
    
    def __init__(self):
        self.vertices: List[DCELVertex] = []
        self.edges: List[DCELHalfEdge] = []
        self.faces: List[DCELFace] = []
        self.spatial_index: Optional[STRtree] = None
        self._face_lookup: Dict[str, DCELFace] = {}
        self._geometry_to_face: Dict[int, DCELFace] = {}
    
    def build_from_voronoi(self, voronoi_geojson: Dict) -> None:
        """
        Build DCEL from Voronoi diagram GeoJSON.
        
        Args:
            voronoi_geojson: GeoJSON FeatureCollection from VoronoiEngine
        """
        features = voronoi_geojson.get('features', [])
        
        for idx, feature in enumerate(features):
            geometry = feature['geometry']
            properties = feature['properties']
            
            polygon = self._geojson_to_polygon(geometry)
            
            face = DCELFace(
                id=idx,
                facility_id=properties.get('facility_id', str(idx)),
                facility_name=properties.get('name', f'Facility {idx}'),
                polygon=polygon,
                properties=properties
            )
            
            self.faces.append(face)
            self._face_lookup[face.facility_id] = face
            if polygon:
                self._geometry_to_face[id(polygon)] = face
        
        self._build_spatial_index()
    
    def _geojson_to_polygon(self, geometry: Dict) -> Optional[Polygon]:
        """Convert GeoJSON geometry to Shapely Polygon."""
        if not geometry:
            return None
            
        geom_type = geometry.get('type')
        coords = geometry.get('coordinates', [])
        
        if not coords:
            return None
        
        try:
            if geom_type == 'Polygon':
                return Polygon(coords[0])
            elif geom_type == 'MultiPolygon':
                polygons = [Polygon(poly[0]) for poly in coords]
                return max(polygons, key=lambda p: p.area)
            else:
                return None
        except Exception:
            return None
    
    def _build_spatial_index(self) -> None:
        """Build R-tree spatial index for fast point queries."""
        geometries = [face.polygon for face in self.faces if face.polygon]
        if geometries:
            self.spatial_index = STRtree(geometries)
    
    def point_query(self, lat: float, lng: float) -> Optional[DCELFace]:
        """
        Find which Voronoi cell contains the given point.
        
        Args:
            lat: Latitude
            lng: Longitude
            
        Returns:
            The DCELFace containing the point, or None if not found
        """
        if not self.spatial_index:
            return None
        
        point = Point(lng, lat)
        
        candidates = self.spatial_index.query(point)
        
        for geom in candidates:
            face = self._geometry_to_face.get(id(geom))
            if face and face.polygon and face.polygon.contains(point):
                return face
        
        return None
    
    def range_query(self, min_lat: float, min_lng: float, 
                   max_lat: float, max_lng: float) -> List[DCELFace]:
        """
        Find all Voronoi cells intersecting the bounding box.
        
        Args:
            min_lat, min_lng: Southwest corner
            max_lat, max_lng: Northeast corner
            
        Returns:
            List of DCELFaces intersecting the bbox
        """
        if not self.spatial_index:
            return []
        
        bbox = box(min_lng, min_lat, max_lng, max_lat)
        candidates = self.spatial_index.query(bbox)
        
        result = []
        for geom in candidates:
            face = self._geometry_to_face.get(id(geom))
            if face and face.polygon and face.polygon.intersects(bbox):
                result.append(face)
        
        return result
    
    def get_face_by_facility_id(self, facility_id: str) -> Optional[DCELFace]:
        """Get Voronoi cell for a specific facility."""
        return self._face_lookup.get(facility_id)
    
    def get_adjacent_facilities(self, facility_id: str) -> List[str]:
        """Find facilities adjacent to the given facility (sharing a border)."""
        face = self.get_face_by_facility_id(facility_id)
        if not face or not face.polygon:
            return []
        
        adjacent = []
        for other_face in self.faces:
            if other_face.facility_id == facility_id:
                continue
            if other_face.polygon and face.polygon.touches(other_face.polygon):
                adjacent.append(other_face.facility_id)
        
        return adjacent
    
    def get_facilities_by_population(self, top_n: int = 10, 
                                     state: Optional[str] = None) -> List[Dict]:
        """
        Get facilities ranked by population served.
        
        Args:
            top_n: Number of top facilities to return
            state: Optional state filter
            
        Returns:
            List of facility info dicts sorted by population
        """
        facilities = []
        
        for face in self.faces:
            props = face.properties or {}
            population = props.get('population', 0)
            
            if state:
                facility_state = props.get('state', '')
                if facility_state.lower() != state.lower():
                    continue
            
            facilities.append({
                'facility_id': face.facility_id,
                'name': face.facility_name,
                'population': population,
                'area_km2': face.polygon.area * 111 * 111 if face.polygon else 0,
                'properties': props
            })
        
        facilities.sort(key=lambda x: x['population'], reverse=True)
        return facilities[:top_n]
    
    def to_dict(self) -> Dict:
        """Export DCEL structure as dictionary for serialization."""
        return {
            'num_faces': len(self.faces),
            'faces': [
                {
                    'id': face.id,
                    'facility_id': face.facility_id,
                    'facility_name': face.facility_name,
                    'population': face.properties.get('population', 0) if face.properties else 0,
                    'area_km2': face.polygon.area * 111 * 111 if face.polygon else 0
                }
                for face in self.faces
            ]
        }


# Global DCEL instance for caching
_current_dcel: Optional[DCEL] = None


def get_current_dcel() -> Optional[DCEL]:
    """Get the current DCEL instance."""
    return _current_dcel


def set_current_dcel(dcel: DCEL) -> None:
    """Set the current DCEL instance."""
    global _current_dcel
    _current_dcel = dcel
