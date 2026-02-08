@echo off
REM OSRM Setup Script for Tessera (Windows)
REM Downloads and processes Gujarat road network for routing

echo === Tessera OSRM Setup (Gujarat) ===
echo This script will download and process Gujarat road data for routing.
echo Requirements: ~200MB disk space, ~2GB RAM during processing
echo.

set SCRIPT_DIR=%~dp0
set DATA_DIR=%SCRIPT_DIR%osrm-data

REM Fix for missing Docker in PATH
set PATH=%PATH%;C:\Program Files\Docker\Docker\resources\bin

REM Create data directory
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
cd /d "%DATA_DIR%"

REM Step 1: Download Gujarat OSM data
if not exist "gujarat-latest.osm.pbf" (
    echo [1/4] Downloading Gujarat OSM data from OpenStreetMap.fr...
    curl -L -o gujarat-latest.osm.pbf "https://download.openstreetmap.fr/extracts/asia/india/gujarat.osm.pbf"
) else (
    echo [1/4] Gujarat OSM data already exists, skipping download.
)

REM Step 2: Extract road network
if not exist "gujarat-latest.osrm" (
    echo [2/4] Extracting road network...
    docker run --rm -t -v "%DATA_DIR%:/data" osrm/osrm-backend:latest osrm-extract -p /opt/car.lua /data/gujarat-latest.osm.pbf
) else (
    echo [2/4] Road network already extracted, skipping.
)

REM Step 3: Partition the graph
if not exist "gujarat-latest.osrm.partition" (
    echo [3/4] Partitioning graph...
    docker run --rm -t -v "%DATA_DIR%:/data" osrm/osrm-backend:latest osrm-partition /data/gujarat-latest.osrm
) else (
    echo [3/4] Graph already partitioned, skipping.
)

REM Step 4: Customize the graph
if not exist "gujarat-latest.osrm.cell_metrics" (
    echo [4/4] Customizing graph...
    docker run --rm -t -v "%DATA_DIR%:/data" osrm/osrm-backend:latest osrm-customize /data/gujarat-latest.osrm
) else (
    echo [4/4] Graph already customized, skipping.
)

echo.
echo === Setup Complete ===
echo To start OSRM, run: docker-compose up -d
echo Test with: curl "http://localhost:5001/route/v1/driving/72.5714,23.0225;72.5414,23.0225"
pause
