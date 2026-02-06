---
description: Workflow for implementing Emergency vs Living Condition Area Analysis with pre-computed Voronoi diagrams
---

# Emergency vs Living Condition Area Analysis

This workflow implements a feature to rate an area (by pincode) based on **Emergency Response Readiness** or **Living Condition Suitability** using pre-computed multi-layer Voronoi diagrams.

---

## 🎯 Feature Overview

### Two Analysis Modes:
1. **Emergency Analysis** - Rates areas based on emergency facility coverage (hospitals, fire stations, police stations, blood banks)
2. **Living Condition Analysis** - Rates areas based on all amenities (schools, parks, banks, petrol pumps, metros, etc.)

### Core Concept:
- Pre-compute Voronoi diagrams for each dataset category
- Compute intersection of multiple Voronoi layers
- Rate areas based on:
  - Average distance to nearest facilities
  - Number of facilities covering the area
  - Population-weighted accessibility scores

---

## 📁 Dataset Categorization

### Emergency Datasets (`data/public/`)
| File | Description |
|------|-------------|
| `hospitals.csv` | Hospitals and healthcare facilities |
| `fire_stations.csv` | Fire stations |
| `police_stations.csv` | Police stations |
| `blood_banks.csv` | Blood banks |

### Living Condition Datasets (`data/public/`)
| File | Description |
|------|-------------|
| `schools.csv` | Schools |
| `preschools.csv` | Preschools |
| `universities.csv` | Universities |
| `daycares.csv` | Daycare centers |
| `parks.csv` | Parks and recreation |
| `banks.csv` | Banks |
| `atms.csv` | ATMs |
| `post_offices.csv` | Post offices |
| `petrol_pumps.csv` | Petrol/gas stations |
| `metro_stations.csv` | Metro/railway stations |
| `airports.csv` | Airports |

---

## 🏗️ Implementation Steps

### Phase 1: Backend - Pre-computation Infrastructure

#### Step 1.1: Create Dataset Registry
Create `backend/app/services/dataset_registry.py`:
```python
# Define dataset categories
EMERGENCY_DATASETS = [
    "hospitals",
    "fire_stations", 
    "police_stations",
    "blood_banks"
]

LIVING_DATASETS = [
    "schools", "preschools", "universities", "daycares",
    "parks", "banks", "atms", "post_offices",
    "petrol_pumps", "metro_stations", "airports"
]

# Weights for scoring (configurable)
EMERGENCY_WEIGHTS = {
    "hospitals": 0.4,
    "fire_stations": 0.25,
    "police_stations": 0.25,
    "blood_banks": 0.1
}

LIVING_WEIGHTS = {
    "schools": 0.15,
    "hospitals": 0.12,
    "parks": 0.10,
    "banks": 0.08,
    # ... etc
}
```

#### Step 1.2: Create Pre-computation Service
Create `backend/app/services/precompute_service.py`:
```python
# Key functions:
# 1. load_dataset(dataset_name) -> List[Facility]
# 2. compute_and_cache_voronoi(dataset_name, state_filter=None)
# 3. get_cached_voronoi(dataset_name, state_filter=None)
# 4. precompute_all_voronois(analysis_type, state_filter=None)
```

**Storage Strategy:**
- Cache GeoJSON files in `backend/app/cache/voronoi/<state>/<dataset>.geojson`
- Use pickle for fast polygon intersection operations
- Store metadata (timestamp, point count) in a manifest file

#### Step 1.3: Create Voronoi Intersection Engine
Create `backend/app/services/intersection_engine.py`:
```python
# Key functions:
# 1. compute_multi_layer_intersection(voronoi_layers: List[GeoJSON])
# 2. analyze_area_by_pincode(pincode: str, analysis_type: str)
# 3. get_facilities_covering_point(lat, lng, analysis_type)
```

**Intersection Logic:**
1. For each dataset Voronoi, find which polygon covers the target pincode centroid
2. Compute intersection of all covering polygons
3. Calculate accessibility scores based on:
   - Distance to facility centroid
   - Polygon area (smaller = better coverage)
   - Weighted sum across datasets

---

### Phase 2: Pre-computation Script

#### Step 2.1: Create CLI Script for Pre-computation
// turbo-all
Create `backend/app/scripts/precompute_voronois.py`:

```bash
# Usage:
python -m app.scripts.precompute_voronois --type emergency --state "Maharashtra"
python -m app.scripts.precompute_voronois --type living --all-states
python -m app.scripts.precompute_voronois --type all --state "Karnataka"
```

**Script Flow:**
1. Parse arguments (type, state filter)
2. Load relevant datasets based on type
3. Call VoronoiEngine for each dataset
4. Save results to cache directory
5. Build intersection index for fast queries

---

### Phase 3: Area Rating API

#### Step 3.1: Create Rating Router
Create `backend/app/routers/area_rating.py`:

```python
# Endpoints:
# POST /api/rating/analyze
# - Body: { pincode: str, analysis_type: "emergency" | "living" }
# - Returns: AreaRatingResponse with scores and facility details

# GET /api/rating/precomputed/{state}/{analysis_type}
# - Returns pre-computed intersection GeoJSON for visualization
```

#### Step 3.2: Create Rating Models
```python
class AreaRatingRequest(BaseModel):
    pincode: str
    analysis_type: Literal["emergency", "living"]
    
class AreaRatingResponse(BaseModel):
    pincode: str
    overall_score: float  # 0-100
    grade: str  # A/B/C/D/F
    breakdown: Dict[str, FacilityScore]
    nearest_facilities: List[NearestFacility]
    recommendations: List[str]
```

---

### Phase 4: Frontend UI

#### Step 4.1: Add Analysis Mode Selector
Modify `frontend/src/app/page.tsx`:
- Add toggle/dropdown for "Emergency Response" vs "Living Conditions"
- Change UI theme based on mode (red for emergency, green for living)

#### Step 4.2: Add Pincode Search
- Input field for pincode
- "Analyze Area" button
- Results panel showing:
  - Overall score with visual gauge
  - Breakdown by category
  - Map highlighting the target area
  - Nearest facilities with distances

#### Step 4.3: Pre-computed Voronoi Visualization
- Load pre-computed intersection GeoJSON on state selection
- Layer toggle for individual datasets
- Color-coded overlay showing coverage quality

---

### Phase 5: Pincode Data

#### Step 5.1: Acquire Pincode Dataset
Need a pincode-to-geometry mapping:
- Option A: Use India Post Office pincode centroids (existing post_offices.csv)
- Option B: Download pincode boundary shapefile
- Option C: API integration with postal service

Create `backend/app/data/pincodes/` directory with:
- `pincode_centroids.csv` (pincode, lat, lng, district, state)
- Optional: `pincode_boundaries.geojson`

---

## ⚡ Performance Optimizations

### Pre-computation Benefits:
1. **Fast User Experience**: No real-time Voronoi computation
2. **Scalable**: Compute once, serve many times
3. **Updatable**: Refresh cache when data changes

### Caching Strategy:
```
backend/app/cache/
├── voronoi/
│   ├── all_india/
│   │   ├── hospitals.geojson
│   │   ├── fire_stations.geojson
│   │   └── ...
│   ├── Maharashtra/
│   │   ├── hospitals.geojson
│   │   └── ...
│   └── manifest.json  # timestamps, counts
├── intersections/
│   ├── emergency_Maharashtra.pkl
│   ├── living_Maharashtra.pkl
│   └── ...
```

### Indexing:
- Use R-tree spatial index for fast point-in-polygon queries
- Pre-compute pincode-to-Voronoi-cell mapping

---

## 🧪 Verification Plan

### Unit Tests:
1. Test dataset loading for each CSV
2. Test Voronoi pre-computation
3. Test intersection computation
4. Test rating calculation

### Integration Tests:
```bash
# Run after pre-computation
pytest backend/tests/test_area_rating.py -v
```

### Manual Testing:
1. Run pre-computation script for a single state
2. Query a known pincode via API
3. Verify frontend displays results correctly

---

## 📋 Task Breakdown

### Backend Tasks:
- [ ] Create dataset registry with category definitions
- [ ] Implement pre-computation service
- [ ] Create intersection engine
- [ ] Build pre-computation CLI script
- [ ] Create area rating router and models
- [ ] Add pincode data/lookup

### Frontend Tasks:
- [ ] Add Emergency/Living mode selector
- [ ] Implement pincode search UI
- [ ] Create rating results panel
- [ ] Add pre-computed Voronoi layer visualization
- [ ] Add layer toggle controls

### Data Tasks:
- [ ] Verify all datasets have consistent schema (name, lat, lng, type, state)
- [ ] Acquire/generate pincode centroid data
- [ ] Run initial pre-computation for test state

---

## 🚀 Quick Start Commands

```bash
# 1. Pre-compute Voronois for Maharashtra (test)
cd backend
python -m app.scripts.precompute_voronois --type emergency --state "Maharashtra"

# 2. Start backend server
uvicorn app.main:app --reload

# 3. Test rating API
curl -X POST http://localhost:8000/api/rating/analyze \
  -H "Content-Type: application/json" \
  -d '{"pincode": "400001", "analysis_type": "emergency"}'

# 4. Start frontend
cd frontend
npm run dev
```

---

## 📊 Rating Algorithm

### Score Calculation:
```
For each dataset category:
  1. Find Voronoi cell covering the pincode centroid
  2. Calculate distance to facility (km)
  3. Calculate coverage score:
     - Excellent (< 2km): 100 points
     - Good (2-5km): 80 points
     - Fair (5-10km): 60 points
     - Poor (10-20km): 40 points
     - Very Poor (> 20km): 20 points
  4. Apply category weight

Overall Score = Σ(category_score × category_weight)
Grade = A (80+), B (60-79), C (40-59), D (20-39), F (<20)
```

### Emergency-specific Adjustments:
- Double weight for hospitals in health emergencies
- Consider 24/7 availability data if available
- Factor in facility capacity/size if available

---

## 🔄 Update Workflow

When new facility data is added:
```bash
# Re-run pre-computation for affected datasets
python -m app.scripts.precompute_voronois --dataset hospitals --all-states

# Clear old cache
rm -rf backend/app/cache/voronoi/*/hospitals.*
rm -rf backend/app/cache/intersections/emergency_*
```
