#!/bin/bash
# OSRM Setup Script for Tessera
# Downloads and processes India road network for routing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="$SCRIPT_DIR/osrm-data"
PROFILE="car"

echo "=== Tessera OSRM Setup ==="
echo "This script will download and process India road data for routing."
echo "Requirements: ~10GB disk space, ~8GB RAM during processing"
echo ""

# Create data directory
mkdir -p "$DATA_DIR"
cd "$DATA_DIR"

# Step 1: Download India OSM data
if [ ! -f "india-latest.osm.pbf" ]; then
    echo "[1/4] Downloading India OSM data from Geofabrik..."
    curl -L -o india-latest.osm.pbf \
        "https://download.geofabrik.de/asia/india-latest.osm.pbf"
else
    echo "[1/4] India OSM data already exists, skipping download."
fi

# Step 2: Extract road network
if [ ! -f "india-latest.osrm" ]; then
    echo "[2/4] Extracting road network (this takes ~30 minutes)..."
    docker run --rm -t -v "$DATA_DIR:/data" osrm/osrm-backend:latest \
        osrm-extract -p /opt/$PROFILE.lua /data/india-latest.osm.pbf
else
    echo "[2/4] Road network already extracted, skipping."
fi

# Step 3: Partition the graph
if [ ! -f "india-latest.osrm.partition" ]; then
    echo "[3/4] Partitioning graph (this takes ~10 minutes)..."
    docker run --rm -t -v "$DATA_DIR:/data" osrm/osrm-backend:latest \
        osrm-partition /data/india-latest.osrm
else
    echo "[3/4] Graph already partitioned, skipping."
fi

# Step 4: Customize the graph
if [ ! -f "india-latest.osrm.cell_metrics" ]; then
    echo "[4/4] Customizing graph (this takes ~5 minutes)..."
    docker run --rm -t -v "$DATA_DIR:/data" osrm/osrm-backend:latest \
        osrm-customize /data/india-latest.osrm
else
    echo "[4/4] Graph already customized, skipping."
fi

echo ""
echo "=== Setup Complete ==="
echo "To start OSRM, run: docker-compose up -d"
echo "Test with: curl 'http://localhost:5000/route/v1/driving/77.2090,28.6139;77.2310,28.6139'"
