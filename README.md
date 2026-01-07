# Tessera

Voronoi-based population mapping for health facility catchment areas in India. Upload facility coordinates, compute Voronoi diagrams clipped to India's boundaries, and visualize population coverage.

## Features

- **Voronoi Diagrams** - Compute facility catchment areas clipped to India
- **Population Integration** - Color cells by estimated catchment population
- **Boundary Overlays** - Toggle state/district administrative boundaries
- **Export** - Download as PNG screenshot or GeoJSON data
- **Interactive Map** - Click cells for population breakdown

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 16, React, TypeScript, Tailwind, Leaflet |
| Backend | Python FastAPI, SciPy, Shapely, GeoPandas |
| Data | GADM boundaries, Census 2011 population |

## Quick Start

```bash
# Backend
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000

# Frontend  
cd frontend && npm install && npm run dev
```

Open http://localhost:3000 and click **Load Sample Data** to get started.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/voronoi/compute` | POST | Compute Voronoi from coordinates |
| `/api/population/districts` | GET | District boundaries GeoJSON |
| `/api/population/states` | GET | State boundaries GeoJSON |
| `/api/upload/csv` | POST | Upload facility CSV |

## Project Structure

```
tessera/
├── backend/
│   ├── app/
│   │   ├── routers/      # API endpoints
│   │   ├── services/     # Business logic
│   │   └── data/         # GeoJSON & CSV
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── app/          # Next.js pages
    │   ├── components/   # React components
    │   └── lib/          # API client, utilities
    └── package.json
```
