# Remaining Work for Route Voronoi

## To Complete MVP

1. **OSRM Setup** - Run processing steps:

   ```bash
   docker run --rm -v "${PWD}/osrm-data:/data" osrm/osrm-backend osrm-extract -p /opt/car.lua /data/india-latest.osm.pbf
   docker run --rm -v "${PWD}/osrm-data:/data" osrm/osrm-backend osrm-partition /data/india-latest.osrm
   docker run --rm -v "${PWD}/osrm-data:/data" osrm/osrm-backend osrm-customize /data/india-latest.osrm
   docker-compose up -d
   ```

2. **Testing** - Verify route computation works end-to-end

## Optional Enhancements

- Caching route queries (Redis/in-memory)
- Progress indicators for long computations
- Route metadata visualization (avg distortion, unreachable areas)
- Grid density auto-tuning based on facility count
- Comparison analytics (area change %, population shift)
