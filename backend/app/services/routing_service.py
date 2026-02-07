"""
Routing Service for OSRM integration.
Provides route distance queries for the route-based Voronoi computation.

Uses OSRM (Open Source Routing Machine) for fast, accurate road network routing.
"""

import httpx
import asyncio
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class RouteResult:
    """Result of a single route query."""
    origin: Tuple[float, float]  # (lat, lng)
    destination: Tuple[float, float]  # (lat, lng)
    distance_km: float
    duration_min: float
    connected: bool  # Whether a route exists
    error: Optional[str] = None


@dataclass
class RoutingConfig:
    """Configuration for the routing service."""
    base_url: str = "http://localhost:5000"
    profile: str = "car"  # car, bike, foot
    timeout_seconds: float = 10.0
    max_retries: int = 3
    batch_size: int = 100  # Max destinations per table query


class RoutingService:
    """
    OSRM-based routing service for computing road network distances.
    
    Supports:
    - Single route queries (point-to-point distance)
    - Batch distance queries (one-to-many matrix)
    - Connectivity checks (is route possible?)
    """
    
    def __init__(self, config: Optional[RoutingConfig] = None):
        self.config = config or RoutingConfig()
        self._client: Optional[httpx.AsyncClient] = None
        self._sync_client: Optional[httpx.Client] = None
    
    async def _get_async_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout_seconds,
                limits=httpx.Limits(max_connections=50, max_keepalive_connections=10)
            )
        return self._client
    
    def _get_sync_client(self) -> httpx.Client:
        """Get or create sync HTTP client."""
        if self._sync_client is None:
            self._sync_client = httpx.Client(
                timeout=self.config.timeout_seconds
            )
        return self._sync_client
    
    def _format_coords(self, lat: float, lng: float) -> str:
        """Format coordinates for OSRM (note: OSRM uses lng,lat order)."""
        return f"{lng},{lat}"
    
    async def get_route_distance(
        self, 
        origin_lat: float, 
        origin_lng: float,
        dest_lat: float,
        dest_lng: float
    ) -> RouteResult:
        """
        Get driving distance and duration between two points.
        
        Args:
            origin_lat, origin_lng: Origin coordinates
            dest_lat, dest_lng: Destination coordinates
            
        Returns:
            RouteResult with distance/duration or error
        """
        client = await self._get_async_client()
        
        coords = f"{self._format_coords(origin_lat, origin_lng)};{self._format_coords(dest_lat, dest_lng)}"
        url = f"{self.config.base_url}/route/v1/{self.config.profile}/{coords}"
        
        try:
            response = await client.get(url, params={"overview": "false"})
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") == "Ok" and data.get("routes"):
                route = data["routes"][0]
                return RouteResult(
                    origin=(origin_lat, origin_lng),
                    destination=(dest_lat, dest_lng),
                    distance_km=route["distance"] / 1000,  # meters to km
                    duration_min=route["duration"] / 60,   # seconds to minutes
                    connected=True
                )
            else:
                return RouteResult(
                    origin=(origin_lat, origin_lng),
                    destination=(dest_lat, dest_lng),
                    distance_km=float('inf'),
                    duration_min=float('inf'),
                    connected=False,
                    error=data.get("message", "No route found")
                )
                
        except httpx.HTTPError as e:
            logger.error(f"OSRM request failed: {e}")
            return RouteResult(
                origin=(origin_lat, origin_lng),
                destination=(dest_lat, dest_lng),
                distance_km=float('inf'),
                duration_min=float('inf'),
                connected=False,
                error=str(e)
            )
    
    def get_route_distance_sync(
        self, 
        origin_lat: float, 
        origin_lng: float,
        dest_lat: float,
        dest_lng: float
    ) -> RouteResult:
        """Synchronous version of get_route_distance."""
        client = self._get_sync_client()
        
        coords = f"{self._format_coords(origin_lat, origin_lng)};{self._format_coords(dest_lat, dest_lng)}"
        url = f"{self.config.base_url}/route/v1/{self.config.profile}/{coords}"
        
        try:
            response = client.get(url, params={"overview": "false"})
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") == "Ok" and data.get("routes"):
                route = data["routes"][0]
                return RouteResult(
                    origin=(origin_lat, origin_lng),
                    destination=(dest_lat, dest_lng),
                    distance_km=route["distance"] / 1000,
                    duration_min=route["duration"] / 60,
                    connected=True
                )
            else:
                return RouteResult(
                    origin=(origin_lat, origin_lng),
                    destination=(dest_lat, dest_lng),
                    distance_km=float('inf'),
                    duration_min=float('inf'),
                    connected=False,
                    error=data.get("message", "No route found")
                )
                
        except httpx.HTTPError as e:
            logger.error(f"OSRM request failed: {e}")
            return RouteResult(
                origin=(origin_lat, origin_lng),
                destination=(dest_lat, dest_lng),
                distance_km=float('inf'),
                duration_min=float('inf'),
                connected=False,
                error=str(e)
            )
    
    async def batch_distance(
        self,
        origin_lat: float,
        origin_lng: float,
        destinations: List[Tuple[float, float]]  # List of (lat, lng)
    ) -> List[RouteResult]:
        """
        Get distances from one origin to multiple destinations using OSRM table API.
        
        This is much more efficient than individual route queries.
        
        Args:
            origin_lat, origin_lng: Origin coordinates
            destinations: List of (lat, lng) tuples for destinations
            
        Returns:
            List of RouteResult for each destination
        """
        if not destinations:
            return []
        
        client = await self._get_async_client()
        
        # Build coordinate string: origin first, then all destinations
        all_coords = [self._format_coords(origin_lat, origin_lng)]
        all_coords.extend([self._format_coords(lat, lng) for lat, lng in destinations])
        coords_str = ";".join(all_coords)
        
        url = f"{self.config.base_url}/table/v1/{self.config.profile}/{coords_str}"
        
        try:
            response = await client.get(url, params={
                "sources": "0",  # Only origin as source
                "annotations": "distance,duration"
            })
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") != "Ok":
                logger.error(f"OSRM table query failed: {data.get('message')}")
                return [
                    RouteResult(
                        origin=(origin_lat, origin_lng),
                        destination=dest,
                        distance_km=float('inf'),
                        duration_min=float('inf'),
                        connected=False,
                        error=data.get('message', 'Table query failed')
                    )
                    for dest in destinations
                ]
            
            # Parse results
            distances = data.get("distances", [[]])[0]  # First row (from origin to all)
            durations = data.get("durations", [[]])[0]
            
            results = []
            for i, dest in enumerate(destinations):
                # Index i+1 because index 0 is origin-to-origin
                dist = distances[i + 1] if i + 1 < len(distances) else None
                dur = durations[i + 1] if i + 1 < len(durations) else None
                
                if dist is not None and dur is not None:
                    results.append(RouteResult(
                        origin=(origin_lat, origin_lng),
                        destination=dest,
                        distance_km=dist / 1000,
                        duration_min=dur / 60,
                        connected=True
                    ))
                else:
                    results.append(RouteResult(
                        origin=(origin_lat, origin_lng),
                        destination=dest,
                        distance_km=float('inf'),
                        duration_min=float('inf'),
                        connected=False,
                        error="No route found"
                    ))
            
            return results
            
        except httpx.HTTPError as e:
            logger.error(f"OSRM batch request failed: {e}")
            return [
                RouteResult(
                    origin=(origin_lat, origin_lng),
                    destination=dest,
                    distance_km=float('inf'),
                    duration_min=float('inf'),
                    connected=False,
                    error=str(e)
                )
                for dest in destinations
            ]
    
    def batch_distance_sync(
        self,
        origin_lat: float,
        origin_lng: float,
        destinations: List[Tuple[float, float]]
    ) -> List[RouteResult]:
        """Synchronous version of batch_distance."""
        if not destinations:
            return []
        
        client = self._get_sync_client()
        
        all_coords = [self._format_coords(origin_lat, origin_lng)]
        all_coords.extend([self._format_coords(lat, lng) for lat, lng in destinations])
        coords_str = ";".join(all_coords)
        
        url = f"{self.config.base_url}/table/v1/{self.config.profile}/{coords_str}"
        
        try:
            response = client.get(url, params={
                "sources": "0",
                "annotations": "distance,duration"
            })
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") != "Ok":
                return [
                    RouteResult(
                        origin=(origin_lat, origin_lng),
                        destination=dest,
                        distance_km=float('inf'),
                        duration_min=float('inf'),
                        connected=False,
                        error=data.get('message', 'Table query failed')
                    )
                    for dest in destinations
                ]
            
            distances = data.get("distances", [[]])[0]
            durations = data.get("durations", [[]])[0]
            
            results = []
            for i, dest in enumerate(destinations):
                dist = distances[i + 1] if i + 1 < len(distances) else None
                dur = durations[i + 1] if i + 1 < len(durations) else None
                
                if dist is not None and dur is not None:
                    results.append(RouteResult(
                        origin=(origin_lat, origin_lng),
                        destination=dest,
                        distance_km=dist / 1000,
                        duration_min=dur / 60,
                        connected=True
                    ))
                else:
                    results.append(RouteResult(
                        origin=(origin_lat, origin_lng),
                        destination=dest,
                        distance_km=float('inf'),
                        duration_min=float('inf'),
                        connected=False,
                        error="No route found"
                    ))
            
            return results
            
        except httpx.HTTPError as e:
            logger.error(f"OSRM batch request failed: {e}")
            return [
                RouteResult(
                    origin=(origin_lat, origin_lng),
                    destination=dest,
                    distance_km=float('inf'),
                    duration_min=float('inf'),
                    connected=False,
                    error=str(e)
                )
                for dest in destinations
            ]
    
    async def check_connectivity(
        self,
        point_a: Tuple[float, float],
        point_b: Tuple[float, float]
    ) -> bool:
        """
        Check if two points are connected in the road network.
        
        Args:
            point_a: (lat, lng) of first point
            point_b: (lat, lng) of second point
            
        Returns:
            True if a route exists, False otherwise
        """
        result = await self.get_route_distance(
            point_a[0], point_a[1],
            point_b[0], point_b[1]
        )
        return result.connected
    
    def check_connectivity_sync(
        self,
        point_a: Tuple[float, float],
        point_b: Tuple[float, float]
    ) -> bool:
        """Synchronous version of check_connectivity."""
        result = self.get_route_distance_sync(
            point_a[0], point_a[1],
            point_b[0], point_b[1]
        )
        return result.connected
    
    async def health_check(self) -> Dict:
        """
        Check if OSRM service is available and responding.
        
        Returns:
            Dict with status and version info
        """
        client = await self._get_async_client()
        
        try:
            # Test with a simple route in India (Delhi area)
            test_url = f"{self.config.base_url}/route/v1/{self.config.profile}/77.2090,28.6139;77.2310,28.6139"
            response = await client.get(test_url, params={"overview": "false"})
            data = response.json()
            
            return {
                "status": "healthy" if data.get("code") == "Ok" else "degraded",
                "osrm_code": data.get("code"),
                "message": data.get("message", "OK"),
                "base_url": self.config.base_url,
                "profile": self.config.profile
            }
            
        except httpx.HTTPError as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "base_url": self.config.base_url,
                "profile": self.config.profile
            }
    
    def health_check_sync(self) -> Dict:
        """Synchronous version of health_check."""
        client = self._get_sync_client()
        
        try:
            test_url = f"{self.config.base_url}/route/v1/{self.config.profile}/77.2090,28.6139;77.2310,28.6139"
            response = client.get(test_url, params={"overview": "false"})
            data = response.json()
            
            return {
                "status": "healthy" if data.get("code") == "Ok" else "degraded",
                "osrm_code": data.get("code"),
                "message": data.get("message", "OK"),
                "base_url": self.config.base_url,
                "profile": self.config.profile
            }
            
        except httpx.HTTPError as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "base_url": self.config.base_url,
                "profile": self.config.profile
            }
    
    async def close(self):
        """Close HTTP clients."""
        if self._client:
            await self._client.aclose()
            self._client = None
        if self._sync_client:
            self._sync_client.close()
            self._sync_client = None


# Global routing service instance
_routing_service: Optional[RoutingService] = None


def get_routing_service(config: Optional[RoutingConfig] = None) -> RoutingService:
    """Get or create the global routing service instance."""
    global _routing_service
    if _routing_service is None:
        _routing_service = RoutingService(config)
    return _routing_service


def set_routing_config(config: RoutingConfig):
    """Update the routing service configuration."""
    global _routing_service
    _routing_service = RoutingService(config)
