# Route Voronoi Debugging Implementation Plan

Date: 2026-02-07

## Goals
- Fix coverage gaps across state boundary and MultiPolygon components.
- Ensure facility polygons contain their own facility points.
- Keep behavior aligned with route-distance intent while staying performant enough for debugging.

## Plan (execute in order)
1. **Use real facility coordinates for k-NN and routing**
   - Persist facility lat/lng in Voronoi GeoJSON properties.
   - Store facility points in DCEL and use them for `k_nearest_neighbors`, `adaptive_k`, and routing destinations.

2. **Improve grid coverage and boundary inclusion**
   - Include boundary points via `covers` (not `contains`).
   - Generate grids per MultiPolygon component to avoid sparse sampling on small islands.

3. **Constrain triangulation by component + better boundary sampling**
   - Triangulate per polygon component to prevent cross-component triangles.
   - Densify boundary sampling based on edge length and grid spacing.
   - Assign boundary points to nearest facility point (not nearest grid point).

4. **Post-validate / enforce facility containment**
   - Seed triangulation with facility points explicitly.
   - Validate that facility points are within their polygons; if not, log and patch with small clipped buffers.

## Status
- [x] Plan created
- [x] Item 1 complete
- [x] Item 2 complete
- [x] Item 3 complete
- [x] Item 4 complete
