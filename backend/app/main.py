"""
Voronoi Population Mapping API - FastAPI Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import voronoi, upload, boundaries, population, dcel, chat, area_rating, routing
from pathlib import Path

app = FastAPI(
    title="Voronoi Population Mapping API",
    description="Compute Voronoi diagrams for facilities and weighted population estimates",
    version="0.2.0",
)

# Ensure data directories exist
DATA_DIR = Path(__file__).parent.parent / "data"
(DATA_DIR / "raw").mkdir(parents=True, exist_ok=True)

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",              # Local dev
        "http://localhost:3001",              # Local dev alternate port
        "https://tessera-chi.vercel.app",     # Production Vercel
        "https://tessera-*.vercel.app",       # Vercel preview deployments
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "message": "Voronoi Population Mapping API"}


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "api_version": "0.2.0",
    }


# Include routers
app.include_router(voronoi.router, prefix="/api/voronoi", tags=["voronoi"])
app.include_router(upload.router, prefix="/api/upload", tags=["upload"])
app.include_router(boundaries.router, prefix="/api/boundaries", tags=["boundaries"])
app.include_router(population.router, prefix="/api/population", tags=["population"])
app.include_router(area_rating.router, prefix="/api/rating", tags=["area-rating"])
app.include_router(dcel.router, prefix="/api/dcel", tags=["dcel"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(routing.router, prefix="/api/routing", tags=["routing"])

