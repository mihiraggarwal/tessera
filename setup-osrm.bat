@echo off
REM OSRM Setup Script for Tessera (Windows)
REM Downloads and processes India road network for routing

echo === Tessera OSRM Setup ===
echo This script will download and process India road data for routing.
echo Requirements: ~10GB disk space, ~8GB RAM during processing
echo.

set SCRIPT_DIR=%~dp0
set DATA_DIR=%SCRIPT_DIR%osrm-data

REM Create data directory
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
cd /d "%DATA_DIR%"

REM Step 1: Download India OSM data
if not exist "india-latest.osm.pbf" (
    echo [1/4] Downloading India OSM data from Geofabrik...
    curl -L -o india-latest.osm.pbf "https://download.geofabrik.de/asia/india-latest.osm.pbf"
) else (
    echo [1/4] India OSM data already exists, skipping download.
)

REM Step 2: Extract road network
if not exist "india-latest.osrm" (
    echo [2/4] Extracting road network (this takes ~30 minutes)...
    docker run --rm -t -v "%DATA_DIR%:/data" osrm/osrm-backend:latest osrm-extract -p /opt/car.lua /data/india-latest.osm.pbf
) else (
    echo [2/4] Road network already extracted, skipping.
)

REM Step 3: Partition the graph
if not exist "india-latest.osrm.partition" (
    echo [3/4] Partitioning graph (this takes ~10 minutes)...
    docker run --rm -t -v "%DATA_DIR%:/data" osrm/osrm-backend:latest osrm-partition /data/india-latest.osrm
) else (
    echo [3/4] Graph already partitioned, skipping.
)

REM Step 4: Customize the graph
if not exist "india-latest.osrm.cell_metrics" (
    echo [4/4] Customizing graph (this takes ~5 minutes)...
    docker run --rm -t -v "%DATA_DIR%:/data" osrm/osrm-backend:latest osrm-customize /data/india-latest.osrm
) else (
    echo [4/4] Graph already customized, skipping.
)

echo.
echo === Setup Complete ===
echo To start OSRM, run: docker-compose up -d
echo Test with: curl "http://localhost:5000/route/v1/driving/77.2090,28.6139;77.2310,28.6139"
pause
