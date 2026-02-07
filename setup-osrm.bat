@echo off
REM OSRM Setup Script for Tessera (Windows) - Delhi Region
REM Downloads and processes Delhi road network for routing

echo === Tessera OSRM Setup (Delhi) ===
echo This script will download and process Delhi road data for routing.
echo.

set SCRIPT_DIR=%~dp0
set DATA_DIR=%SCRIPT_DIR%osrm-data

REM Create data directory
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
cd /d "%DATA_DIR%"

REM Step 1: Download Delhi OSM data
if not exist "delhi-latest.osm.pbf" (
    echo [1/4] Downloading Delhi OSM data from Geofabrik...
    curl -L -o delhi-latest.osm.pbf "https://download.geofabrik.de/asia/india/delhi-latest.osm.pbf"
) else (
    echo [1/4] Delhi OSM data already exists, skipping download.
)

REM Step 2: Extract road network
if not exist "delhi-latest.osrm.ebg" (
    echo [2/4] Extracting road network... This takes about 2 minutes for Delhi.
    docker run --rm -t -v "%DATA_DIR%:/data" osrm/osrm-backend:latest osrm-extract -p /opt/car.lua /data/delhi-latest.osm.pbf
) else (
    echo [2/4] Road network already extracted, skipping.
)

REM Step 3: Partition the graph
if not exist "delhi-latest.osrm.partition" (
    echo [3/4] Partitioning graph...
    docker run --rm -t -v "%DATA_DIR%:/data" osrm/osrm-backend:latest osrm-partition /data/delhi-latest.osrm
) else (
    echo [3/4] Graph already partitioned, skipping.
)

REM Step 4: Customize the graph
if not exist "delhi-latest.osrm.cell_metrics" (
    echo [4/4] Customizing graph...
    docker run --rm -t -v "%DATA_DIR%:/data" osrm/osrm-backend:latest osrm-customize /data/delhi-latest.osrm
) else (
    echo [4/4] Graph already customized, skipping.
)

echo.
echo === Setup Complete ===
echo To start OSRM, run: docker-compose up -d
echo Test with: curl "http://localhost:5000/route/v1/driving/77.2090,28.6139;77.2310,28.6139"
pause
