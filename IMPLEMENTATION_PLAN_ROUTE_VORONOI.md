# Route-Distance Voronoi Implementation Plan

## Overview

This plan implements a **candidate-filtered network Voronoi approximation** for Tessera, replacing the current Euclidean-only approach with road-network-aware facility service areas. This is a filter-refine algorithm that uses geometric proximity to prune candidates, then computes exact route distances for final assignment.

> [!IMPORTANT]
> This is **not** a mathematically exact graph Voronoi—it's an engineering-grade approximation that:
>
> - Computes true network distances (not approximated)
> - Uses Euclidean Voronoi only for candidate filtering
> - Provides empirical guarantees based on road network properties (spanners)
> - Explicitly encodes confidence and ambiguity metrics

---

## Problem Statement

Current implementation uses Euclidean distance, which doesn't reflect real-world accessibility:

- Facilities "close" in straight-line distance may be far by road
- Rivers, highways, railways create barriers not captured geometrically
- Service area boundaries don't match actual population access patterns
- CSV upload loads all points immediately without allowing subset selection
- Large datasets cause performance issues when full country data is loaded

**Goal:** Compute Voronoi cells using actual road network distance while maintaining computational feasibility.

---

## Proposed Algorithm

### Core Approach: Filter-Refine

```
For each grid point p in the region:
  1. [FILTER] Use DCEL R-tree to get k nearest facilities by Euclidean distance
  2. [REFINE] Query routing API for road distance to these k candidates
  3. [ASSIGN] Assign p to facility with minimum road distance
  4. [INTERPOLATE] Generate polygons from assigned grid points
```

**Complexity:** O(m × k) where m = grid points, k = constant candidates  
**Independence:** Linear in grid size, independent of facility count

### Key Insight

Road networks are **geometric spanners**: shortest path distance is usually within a small constant factor of Euclidean distance. Therefore, the true nearest-by-road facility is typically among the top-k nearest-by-Euclidean facilities.

**Assumption validity:** Holds in urban networks without extreme topological barriers  
**Failure mode:** Disconnected road components (rivers with few bridges, restricted zones)

---

## Proposed Changes

### Backend

#### **New Service: `routing_service.py`**

OSRM/OpenRouteService wrapper with connection awareness.

**Key methods:**

- `batch_distance(origin, destinations)` - Multi-destination distance query
- `check_connectivity(point_a, point_b)` - Test if points are in same road component
- `get_route(origin, destination)` - Full route with geometry (for visualization)

**Configuration:**

```python
ROUTING_CONFIG = {
    "provider": "osrm",  # or "openrouteservice"
    "url": "http://localhost:5000",
    "profile": "car",  # or "bike", "foot"
    "timeout_ms": 5000,
    "batch_size": 100
}
```

---

#### **Enhanced Service: `dcel.py`**

Add k-nearest neighbors with adaptive k.

**New methods:**

```python
def k_nearest_neighbors(self, point: Point, k: int = 5) -> List[DCELFace]:
    """Get k nearest facilities by Euclidean distance using R-tree"""

def adaptive_k(self, point: Point, base_k: int = 5) -> int:
    """
    Adjust k based on distortion detection
    If d_E(f_k) / d_E(f_1) > threshold (e.g., 3-4), expand k
    """
```

**Rationale:** In areas with barriers, Euclidean distances spread more—this signals need for more candidates.

---

#### **New Service: `route_voronoi_service.py`**

Core route Voronoi computation engine.

**Class structure:**

```python
class RouteVoronoiEngine:
    def __init__(self, dcel: DCEL, routing: RoutingService):
        self.dcel = dcel
        self.routing = routing
        self.cache = {}  # Route distance cache

    def compute(
        self,
        boundary: Polygon,
        grid_density: int = 50,
        grid_points: int = 2500,
        base_k: int = 5,
        adaptive: bool = True
    ) -> RouteVoronoiResult:
        """Main computation method"""

    def _sample_grid(self, boundary: Polygon, density: int) -> List[Point]:
        """Generate uniform grid within boundary"""

    def _assign_grid_point(
        self,
        point: Point,
        k: int,
        connectivity_check: bool = True
    ) -> Assignment:
        """Assign single grid point with confidence metrics"""

    def _interpolate_polygons(
        self,
        assignments: List[Assignment]
    ) -> MultiPolygon:
        """Delaunay triangulation + dissolve to create Voronoi-like cells"""
```

**Assignment data structure:**

```python
@dataclass
class Assignment:
    point: Point
    facility_id: int
    route_distance_km: float
    route_duration_min: float
    euclidean_distance_km: float
    distortion_ratio: float  # route / euclidean
    confidence: float  # 1.0 if isolated winner, <1.0 if ambiguous
    k_used: int
    connectivity_verified: bool
```

**Confidence calculation:**

```python
# If nearest and second-nearest are very close, confidence is low
confidence = 1 - (d2 - d1) / d1  # Lower when d1 ≈ d2
```

---

#### **Polygon Interpolation Strategy**

**Method:** Delaunay Triangulation + Dissolve

1. Compute Delaunay triangulation of all grid points
2. Assign each triangle to majority facility of its vertices
3. Dissolve adjacent triangles with same facility ID
4. Result: continuous polygonal regions

**Implementation:**

- Use `scipy.spatial.Delaunay` for triangulation
- Use `shapely.ops.unary_union` for dissolving
- Handle edge cases (grid points on boundary)

**Alternative:** Alpha shapes for smoother boundaries (future enhancement)

---

#### **New API Endpoints**

##### `POST /api/voronoi/compute-route`

Compute route-based Voronoi diagram.

**Request:**

```json
{
  "facilities": [...],
  "boundary_type": "district",
  "boundary_name": "Mumbai",
  "config": {
    "grid_density": 50,
    "base_k": 5,
    "adaptive_k": true,
    "connectivity_check": true,
    "routing_profile": "car"
  }
}
```

**Response:**

```json
{
  "type": "route_voronoi",
  "computation_method": "candidate_filtered_k5",
  "grid_size": 2500,
  "total_route_queries": 12450,
  "computation_time_sec": 45.3,
  "features": [...],  // GeoJSON features
  "metadata": {
    "avg_distortion_ratio": 1.42,
    "ambiguous_regions_count": 12,
    "disconnected_regions_count": 2
  }
}
```

---

##### `POST /api/voronoi/compare`

Compare Euclidean vs Route Voronoi side-by-side.

**Response includes:**

- Both Voronoi diagrams (Euclidean + Route)
- Difference metrics per facility (area change, centroid shift)
- Regions of high distortion
- Ambiguity zones

---

##### `POST /api/voronoi/validate`

Validation endpoint for accuracy testing.

**Purpose:** Compare against ground-truth graph Voronoi on small subgraph

**Request:**

```json
{
  "test_points": [...],  // Random sample points
  "k_values": [3, 5, 7, 10],
  "ground_truth_method": "multi_source_dijkstra"
}
```

**Response:**

```json
{
  "accuracy_by_k": {
    "k3": 0.92,
    "k5": 0.98,
    "k7": 0.995,
    "k10": 1.0
  },
  "failure_cases": [...],
  "recommended_k": 5
}
```

---

---

## CSV Upload Flow Enhancement

### Current Problem

CSV upload currently loads all facilities immediately, which:

- Causes performance issues with large datasets (1000+ facilities)
- Prevents users from working with specific regions
- Makes route Voronoi computation expensive for full country

### Proposed Two-Step Upload Flow

**Step 1: Upload & Preview**

User drags and drops CSV file:

1. File uploaded to backend
2. Backend parses CSV and extracts unique states/districts
3. Returns metadata without loading full dataset:
   ```json
   {
     "filename": "health_centers_india.csv",
     "total_rows": 5432,
     "states": ["Maharashtra", "Karnataka", "Delhi", ...],
     "districts_by_state": {
       "Maharashtra": ["Mumbai", "Pune", "Nagpur", ...],
       "Karnataka": ["Bangalore Urban", "Mysore", ...]
     },
     "preview_data": [...] // First 10 rows
   }
   ```

**Step 2: Subset Selection & Load**

User selects filtering options:

- **Option A:** Load entire country (if dataset is small)
- **Option B:** Select specific state(s)
- **Option C:** Select specific district(s) within a state

Frontend sends load request:

```json
{
  "filename": "health_centers_india.csv",
  "filter": {
    "type": "district",
    "state": "Maharashtra",
    "district": "Mumbai"
  }
}
```

Backend filters data and returns only relevant facilities.

### Implementation Details

**Backend changes:**

#### `POST /api/upload/csv` (modified)

Now returns metadata only, doesn't load facilities into memory:

```python
# Parse CSV
df = pd.read_csv(file)

# Extract unique values
states = df['state'].unique().tolist() if 'state' in df.columns else []
districts = df.groupby('state')['district'].unique().to_dict() if 'district' in df.columns else {}

# Store file temporarily
file_id = save_temp_file(file)

return {
    "file_id": file_id,
    "total_rows": len(df),
    "states": states,
    "districts_by_state": districts,
    "preview": df.head(10).to_dict('records')
}
```

#### `POST /api/upload/load-subset` (new)

Loads filtered subset of facilities:

```python
@router.post("/load-subset")
async def load_subset(request: LoadSubsetRequest):
    df = read_temp_file(request.file_id)

    # Apply filters
    if request.filter.type == "state":
        df = df[df['state'].isin(request.filter.states)]
    elif request.filter.type == "district":
        df = df[(df['state'] == request.filter.state) &
                (df['district'] == request.filter.district)]

    facilities = parse_facilities(df)
    return {"facilities": facilities, "count": len(facilities)}
```

**Frontend changes:**

#### Enhanced FileUpload Component

```tsx
// Step 1: Upload shows metadata
<FileUploadPreview>
  <FileInfo>
    Total Facilities: {metadata.total_rows}
    States: {metadata.states.length}
  </FileInfo>

  <DataPreview table={metadata.preview_data} />

  {/* Step 2: Subset selector */}
  <SubsetSelector>
    <Select label="Filter By">
      <option value="all">Load All</option>
      <option value="state">Select State(s)</option>
      <option value="district">Select District</option>
    </Select>

    {filterType === "state" && <MultiSelect options={metadata.states} />}

    {filterType === "district" && (
      <>
        <Select options={metadata.states} onChange={setSelectedState} />
        <Select options={metadata.districts_by_state[selectedState]} />
      </>
    )}

    <Button onClick={loadSubset}>Load Facilities</Button>
  </SubsetSelector>
</FileUploadPreview>
```

**Benefits:**

- Users can work with manageable subsets
- Route Voronoi computation scoped to relevant region
- Faster initial load and preview
- Better UX for large national datasets

---

### Frontend

#### **Enhanced Map Component**

**New layer toggles:**

- Euclidean Voronoi (existing)
- Route Voronoi (new)
- Overlay comparison mode
- Distortion heatmap
- Confidence zones (highlight low-confidence regions)

**Color schemes:**

- **Comparison overlay:** Blue outlines (Euclidean) + Red fill (Route)
- **Distortion heatmap:** Green (low distortion) → Yellow → Red (high distortion)
- **Confidence:** Solid colors (high confidence) → Hatched (low confidence)

---

#### **New Configuration Panel**

**Route Voronoi Settings:**

```tsx
<RouteVoronoiConfig>
  <Slider label="Grid Density" min={20} max={100} default={50} />
  <Slider label="Base k" min={3} max={10} default={5} />
  <Toggle label="Adaptive k" default={true} />
  <Toggle label="Connectivity Check" default={true} />
  <Select label="Routing Profile" options={["car", "bike", "foot"]} />
  <Button>Compute Route Voronoi</Button>
</RouteVoronoiConfig>
```

---

#### **Enhanced Analytics Panel**

**New metrics:**

| Metric                   | Description                                 |
| ------------------------ | ------------------------------------------- |
| **Avg Distortion Ratio** | Mean of route_distance / euclidean_distance |
| **Max Distortion**       | Worst-case distortion in dataset            |
| **Ambiguous Regions**    | Count of low-confidence assignments         |
| **Area Coverage Change** | % change in facility service areas          |
| **Disconnected Zones**   | Regions with connectivity failures          |

**Visualization:**

- Side-by-side bar charts: Euclidean vs Route coverage area per facility
- Scatter plot: Euclidean distance vs Route distance (shows spanner property)
- Table: Top 10 facilities with highest distortion

---

#### **API Client Updates** (`lib/api.ts`)

```typescript
export const routeVoronoiApi = {
  compute: (request: RouteVoronoiRequest) =>
    axios.post("/api/voronoi/compute-route", request),

  compare: (request: CompareRequest) =>
    axios.post("/api/voronoi/compare", request),

  validate: (request: ValidationRequest) =>
    axios.post("/api/voronoi/validate", request),
};
```

---

## Robustness Improvements

### 1. Adaptive k Based on Distortion Detection

**Rule:**

```python
k_candidates = self.dcel.k_nearest_neighbors(point, base_k)
euclidean_distances = [distance(point, c.centroid) for c in k_candidates]

# If spread is large, expand k
if euclidean_distances[-1] / euclidean_distances[0] > distortion_threshold:
    k_expanded = base_k * 2
    k_candidates = self.dcel.k_nearest_neighbors(point, k_expanded)
```

**Threshold:** τ = 3-4 (if 5th nearest is 3× farther than 1st, suspect barrier)

---

### 2. Connectivity-Aware Fallback

**Before routing query:**

```python
# Snap to nearest road nodes
point_node = routing.snap_to_road(grid_point)
facility_nodes = [routing.snap_to_road(f.location) for f in candidates]

# Check connectivity
reachable = [f for f in candidates if routing.check_connectivity(point_node, f)]

if not reachable:
    # Fallback: use Euclidean assignment, mark as "isolated"
    return Assignment(facility=nearest_euclidean, confidence=0.0, isolated=True)
```

**Purpose:** Avoid expensive routing calls that will fail

---

### 3. Confidence Metrics for Ambiguity

**Store metadata on each assignment:**

```python
# Compute second-best route distance
best_distance = min(route_distances)
second_best = sorted(route_distances)[1]

# Confidence inversely proportional to closeness
confidence = 1.0 - (second_best - best_distance) / best_distance

if confidence < 0.3:
    # This region is contested by multiple facilities
    assignment.ambiguous = True
```

**UI treatment:** Render low-confidence regions with hatched patterns or borders

---

## Validation Protocol

### Testing Framework

**Goal:** Measure accuracy as function of k and grid density

**Method:**

1. Select test district (e.g., small urban district with ~50 facilities)
2. Generate 500 random test points
3. For each point:
   - Compute **ground truth** using full multi-source Dijkstra on road graph
   - Compute **approximation** using candidate-filtered approach with varying k
4. Measure accuracy: `correct_assignments / total_points`
5. Repeat for k ∈ {3, 5, 7, 10, 15}

**Expected results:**

- k=3: ~90-95% accuracy (urban), ~80-85% (rural)
- k=5: ~97-99% accuracy (urban), ~92-95% (rural)
- k=7+: >99% accuracy (both)

**Deliverable:** Validation report with recommended k values for different contexts

---

### Failure Case Analysis

**Classification of errors:**

| Failure Type          | Cause                                      | Detection                |
| --------------------- | ------------------------------------------ | ------------------------ |
| **Barrier Miss**      | True nearest beyond k due to river/highway | High distortion ratio    |
| **Disconnection**     | Road network not connected                 | Connectivity check fails |
| **Metric Distortion** | Highly non-Euclidean local geometry        | Adaptive k triggers      |

**Mitigation:**

- Log all failures for manual inspection
- Build "known barrier" database for future improved candidate selection
- Provide override mode: manual facility assignment for specific regions

---

## Performance Considerations

### OSRM Setup

**India Road Network Data:**

1. **Download OSM data** from Geofabrik:
   - URL: https://download.geofabrik.de/asia/india-latest.osm.pbf
   - Size: ~2GB compressed, ~8GB extracted
   - Updated: Weekly (check for freshness)

2. **Process with OSRM:**

   ```bash
   # Extract roads
   docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-extract -p /opt/car.lua /data/india-latest.osm.pbf

   # Build routing graph
   docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-partition /data/india-latest.osrm
   docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-customize /data/india-latest.osrm

   # Run routing server
   docker run -t -i -p 5000:5000 -v "${PWD}:/data" osrm/osrm-backend osrm-routed --algorithm mld /data/india-latest.osrm
   ```

3. **State/District-specific extraction** (optional, for faster startup):
   - Use osmium-tool to extract specific regions
   - Reduces memory footprint for district-level analysis

**Infrastructure:**

- Docker container: `osrm/osrm-backend`
- RAM requirement: 4-6GB for all-India, 1-2GB for single state
- Query performance: 100-500 requests/sec

**Batch optimization:**

- Use OSRM "table" endpoint: one-to-many distance queries
- Single API call for point + 5 candidates
- Reduces network overhead significantly

---

### Caching Strategy

**Route distance cache:**

```python
cache_key = f"{point.lat:.4f},{point.lng:.4f}:{facility.id}"
if cache_key in self.cache:
    return self.cache[cache_key]

distance = routing.query(point, facility)
self.cache[cache_key] = distance
```

**Cache invalidation:**

- Invalidate on facility location changes
- No invalidation needed for static road network
- Persist cache to Redis for cross-session reuse

---

### Incremental Recomputation

**Scenario:** User adds/removes one facility

**Naive:** Recompute entire route Voronoi  
**Optimized:**

1. Identify grid points in Euclidean Voronoi cell of changed facility
2. Identify grid points in adjacent cells (potential boundary shifts)
3. Recompute only affected grid points (~10-20% of total)
4. Re-interpolate only affected regions

---

## Verification Plan

### Automated Tests

**Unit tests:**

- [ ] Grid sampling (uniform distribution, boundary clipping)
- [ ] k-NN queries (correct ordering, adaptive expansion)
- [ ] Delaunay triangulation (topology validity)
- [ ] Cache hit/miss logic

**Integration tests:**

- [ ] End-to-end route Voronoi computation on test dataset
- [ ] Euclidean vs Route comparison (metrics calculation)
- [ ] API endpoint responses (schema validation)

---

### Manual Verification

**Visual inspection:**

- [ ] Compare Euclidean vs Route Voronoi for known barrier cases (rivers)
- [ ] Verify distortion heatmap highlights expected regions
- [ ] Check ambiguity zones align with actual facility overlap

**User testing:**

- [ ] Planner feedback on realism improvement
- [ ] Performance acceptable on standard hardware
- [ ] UI controls intuitive for configuration

---

## Timeline Estimate

| Phase       | Tasks                                                          | Duration  |
| ----------- | -------------------------------------------------------------- | --------- |
| **Phase 1** | Infrastructure setup, OSRM configuration, validation framework | 1 week    |
| **Phase 2** | Core algorithm, DCEL enhancement, route Voronoi engine         | 2 weeks   |
| **Phase 3** | API endpoints, backend integration, caching                    | 1 week    |
| **Phase 4** | Frontend UI, visualization layers, analytics panel             | 1-2 weeks |
| **Phase 5** | Validation, testing, performance tuning, documentation         | 1 week    |

**Total:** ~6-7 weeks for full implementation

**Proof of concept (single district):** ~2-3 weeks (Phases 1-2 only)

---

## Success Criteria

### Functional Requirements

- ✅ Compute route-based Voronoi for any district in India
- ✅ K-NN candidate filtering operational
- ✅ Batch routing API integration working
- ✅ Polygon interpolation produces valid geometries
- ✅ Confidence metrics calculated and displayed

### Performance Requirements

- ✅ Computation time <2 minutes for 50 facilities, 50×50 grid
- ✅ OSRM queries <100ms average latency
- ✅ Cache hit rate >85% on repeat computations
- ✅ UI responsive during background computation

### Quality Requirements

- ✅ Validation accuracy >95% with k=5 in urban areas
- ✅ Failure cases detected and flagged (connectivity, ambiguity)
- ✅ Visual comparison clearly shows distortion regions

---

## Future Enhancements

### Multi-Modal Routing

- Toggle between car/bike/foot/public transit
- Show coverage differences by travel mode

### Temporal Variation

- Compute route Voronoi for different times of day (traffic)
- Identify facilities sensitive to congestion

### Isochrone Integration

- Overlay time-based isochrones (10/20/30 min drive polygons)
- Compare isochrone vs route Voronoi boundaries

### GPU Acceleration

- Parallelize grid point processing on GPU
- Handle 200×200+ grids for high-resolution analysis

---

## Open Questions

1. **Optimal grid density:** Trade-off between resolution and computation time
2. **k value tunability:** Should users control k, or auto-select based on validation?
3. **Road network updates:** How often to refresh OSM data for India?
4. **Multi-district computation:** Should route Voronoi respect administrative boundaries?

---

## References

**Technical foundations:**

- Filter-refine algorithms in computational geometry
- Road networks as geometric spanners (Eppstein et al.)
- Multi-source Dijkstra for graph Voronoi
- OSRM routing engine documentation

**Related implementations:**

- PostGIS pgRouting for network analysis
- Valhalla time-distance matrices
