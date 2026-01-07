# Tessera

Tessera is a Voronoi-based population mapping application that visualizes catchment areas for health facilities across India. Upload facility coordinates via CSV or use sample data, and the app computes Voronoi diagrams clipped to India's boundaries, showing each facility's geographic coverage area on an interactive map.

## Tech Stack

**Frontend:** Next.js 16 with React, TypeScript, Tailwind CSS, and Leaflet for map rendering. **Backend:** Python FastAPI with SciPy for Voronoi computation, Shapely/GeoPandas for geospatial processing, and PyProj for coordinate transformations.

## Quick Start

```bash
# Backend
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
```
