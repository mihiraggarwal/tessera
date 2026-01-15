"""
Voronoi Population Mapping API - FastAPI Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')) # Try checking parent directory too

from app.routers import voronoi, upload, boundaries, population, copilot

app = FastAPI(
    title="Voronoi Population Mapping API",
    description="Compute Voronoi diagrams for facilities and weighted population estimates",
    version="0.1.0",
)

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
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
        "api_version": "0.1.0",
    }


# Include routers
app.include_router(voronoi.router, prefix="/api/voronoi", tags=["voronoi"])
app.include_router(upload.router, prefix="/api/upload", tags=["upload"])
app.include_router(boundaries.router, prefix="/api/boundaries", tags=["boundaries"])
app.include_router(population.router, prefix="/api/population", tags=["population"])
app.include_router(copilot.router, prefix="/api/copilot", tags=["copilot"])
