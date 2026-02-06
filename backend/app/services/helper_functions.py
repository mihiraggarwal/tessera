"""
Helper functions for Python REPL execution environment.
These are injected into the sandbox for safe data access.
"""
from difflib import get_close_matches
from typing import List, Dict, Any, Optional


def create_helper_functions(dcel):
    """
    Create helper functions bound to a specific DCEL instance.
    Returns a dict of functions to inject into execution environment.
    """
    
    def get_primary_location(facility):
        """Extract primary state/district from population_breakdown."""
        props = getattr(facility, 'properties', None) or {}
        
        # First try direct properties
        state = props.get('state')
        district = props.get('district')
        if state and district:
            return state, district
        
        # Fall back to population_breakdown (pick region with highest overlap)
        breakdown = props.get('population_breakdown', [])
        if breakdown:
            primary = max(breakdown, key=lambda x: x.get('overlap_percentage', 0))
            return primary.get('state', ''), primary.get('district', '')
        
        return '', ''
    
    # Pre-compute unique values for fast lookups by extracting from population_breakdown
    all_states = set()
    all_districts = set()
    for f in dcel.faces:
        state, district = get_primary_location(f)
        if state:
            all_states.add(state)
        if district:
            all_districts.add(district)
    
    unique_states = sorted(all_states)
    unique_districts = sorted(all_districts)
    
    def normalize_state(name: str) -> Optional[str]:
        """Normalize state name to canonical form."""
        if not name:
            return None
        name_lower = name.lower().strip()
        
        # Direct match
        for state in unique_states:
            if state.lower() == name_lower:
                return state
        
        # Fuzzy match
        matches = get_close_matches(name, unique_states, n=1, cutoff=0.6)
        return matches[0] if matches else None
    
    def normalize_district(name: str) -> Optional[str]:
        """Normalize district name to canonical form."""
        if not name:
            return None
        name_lower = name.lower().strip()
        
        for district in unique_districts:
            if district.lower() == name_lower:
                return district
        
        matches = get_close_matches(name, unique_districts, n=1, cutoff=0.6)
        return matches[0] if matches else None
    
    def safe_filter_by_state(query: str) -> List[Any]:
        """
        Filter facilities by state with fuzzy matching.
        Raises ValueError if state not found.
        """
        normalized = normalize_state(query)
        if not normalized:
            raise ValueError(
                f"State '{query}' not found. Available: {', '.join(unique_states[:10])}..."
            )
        
        return [
            f for f in dcel.faces 
            if get_primary_location(f)[0] == normalized
        ]
    
    def safe_filter_by_district(query: str, state: str = None) -> List[Any]:
        """
        Filter facilities by district with fuzzy matching.
        Optionally filter by state first.
        """
        facilities = dcel.faces
        
        if state:
            facilities = safe_filter_by_state(state)
        
        normalized = normalize_district(query)
        if not normalized:
            available = sorted(set(
                get_primary_location(f)[1]
                for f in facilities 
                if get_primary_location(f)[1]
            ))
            raise ValueError(
                f"District '{query}' not found. Available: {', '.join(available[:10])}..."
            )
        
        return [
            f for f in facilities 
            if get_primary_location(f)[1] == normalized
        ]
    
    def safe_get_property(facility, prop: str, default=None):
        """Safely get a property from a facility with fallback."""
        if not facility:
            return default
        props = getattr(facility, 'properties', None) or {}
        value = props.get(prop, None)
        
        # For state/district, try population_breakdown if not found directly
        if value is None and prop in ['state', 'district']:
            state, district = get_primary_location(facility)
            value = state if prop == 'state' else district
        
        # Treat 0, None, empty string as missing for certain fields
        if prop in ['population', 'area_sq_km'] and not value:
            return default
        return value if value is not None else default
    
    def get_stats(facilities: List[Any]) -> Dict[str, Any]:
        """Compute aggregate statistics for a list of facilities."""
        if not facilities:
            return {
                'count': 0,
                'total_population': 0,
                'avg_population': 0,
                'total_area_sq_km': 0,
                'avg_area_sq_km': 0
            }
        
        pops = [safe_get_property(f, 'population', 0) for f in facilities]
        areas = [safe_get_property(f, 'area_sq_km', 0) for f in facilities]
        
        total_pop = sum(p for p in pops if p)
        total_area = sum(a for a in areas if a)
        count = len(facilities)
        
        return {
            'count': count,
            'total_population': int(total_pop),
            'avg_population': int(total_pop / count) if count else 0,
            'total_area_sq_km': round(total_area, 2),
            'avg_area_sq_km': round(total_area / count, 2) if count else 0
        }
    
    def get_top_n(facilities: List[Any], by: str = 'population', n: int = 10) -> List[Any]:
        """Get top N facilities sorted by a property."""
        return sorted(
            facilities,
            key=lambda f: safe_get_property(f, by, 0),
            reverse=True
        )[:n]
    
    # Return all helpers as a dict
    return {
        'normalize_state': normalize_state,
        'normalize_district': normalize_district,
        'safe_filter_by_state': safe_filter_by_state,
        'safe_filter_by_district': safe_filter_by_district,
        'safe_get_property': safe_get_property,
        'get_stats': get_stats,
        'get_top_n': get_top_n,
        'unique_states': unique_states,
        'unique_districts': unique_districts,
        'total_facilities': len(dcel.faces),
    }
