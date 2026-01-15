'use client';

import { useState, useCallback, useEffect, useMemo } from 'react';
import dynamic from 'next/dynamic';
import FileUpload from '@/components/FileUpload';
import ChatInterface from '@/components/MapCopilot/ChatInterface';
import { voronoiApi, populationApi, boundariesApi, type Facility, type GeoJSONFeatureCollection, type GeoJSONFeature } from '@/lib/api';
import { exportToPNG, exportToGeoJSON } from '@/lib/export';
import * as turf from '@turf/turf';

// Dynamic import for Map (no SSR)
const MapComponent = dynamic(() => import('@/components/Map'), {
  ssr: false,
  loading: () => (
    <div className="w-full h-[600px] bg-gray-100 rounded-xl flex items-center justify-center">
      <div className="text-gray-500 animate-pulse">Loading map...</div>
    </div>
  ),
});

export default function Home() {
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [voronoiData, setVoronoiData] = useState<GeoJSONFeatureCollection | null>(null);
  const [isComputing, setIsComputing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showVoronoi, setShowVoronoi] = useState(true);
  const [boundaryLevel, setBoundaryLevel] = useState<'none' | 'state' | 'district'>('none');
  const [stateData, setStateData] = useState<GeoJSONFeatureCollection | undefined>(undefined);
  const [districtData, setDistrictData] = useState<GeoJSONFeatureCollection | undefined>(undefined);
  const [apiStatus, setApiStatus] = useState<'unknown' | 'online' | 'offline'>('unknown');
  const [isExporting, setIsExporting] = useState(false);
  const [isLoadingBoundaries, setIsLoadingBoundaries] = useState(false);
  const [statesList, setStatesList] = useState<string[]>([]);
  const [selectedState, setSelectedState] = useState<string | null>(null);
  const [filterOutOfRegion, setFilterOutOfRegion] = useState(false);
  const [selectedStateBoundary, setSelectedStateBoundary] = useState<GeoJSONFeature | null>(null);
  const [indiaBoundary, setIndiaBoundary] = useState<GeoJSONFeature | null>(null);
  const [mapCenter, setMapCenter] = useState<{ lat: number; lng: number; zoom: number } | null>(null);

  // Fetch states list and India boundary on mount
  useEffect(() => {
    boundariesApi.getStatesList()
      .then(setStatesList)
      .catch((err) => console.error('Failed to load states list', err));

    // Fetch India boundary for filtering
    boundariesApi.getIndiaBoundary()
      .then(setIndiaBoundary)
      .catch((err) => console.error('Failed to load India boundary', err));
  }, []);

  // Fetch state boundary when selectedState changes
  useEffect(() => {
    if (selectedState) {
      boundariesApi.getStateBoundary(selectedState)
        .then(setSelectedStateBoundary)
        .catch((err) => {
          console.error('Failed to load state boundary', err);
          setSelectedStateBoundary(null);
        });
    } else {
      setSelectedStateBoundary(null);
    }
  }, [selectedState]);

  // Filter facilities: always exclude outside India, then optionally filter by state
  const displayedFacilities = useMemo(() => {
    // First filter to only facilities inside India
    let filtered = facilities;

    if (indiaBoundary) {
      filtered = facilities.filter(facility => {
        try {
          const point = turf.point([facility.lng, facility.lat]);
          const polygon = indiaBoundary.geometry as GeoJSON.Polygon | GeoJSON.MultiPolygon;
          return turf.booleanPointInPolygon(point, polygon);
        } catch {
          return false; // Exclude if we can't determine
        }
      });
    }

    // Then optionally filter by selected state
    if (filterOutOfRegion && selectedState && selectedStateBoundary) {
      filtered = filtered.filter(facility => {
        try {
          const point = turf.point([facility.lng, facility.lat]);
          const polygon = selectedStateBoundary.geometry as GeoJSON.Polygon | GeoJSON.MultiPolygon;
          return turf.booleanPointInPolygon(point, polygon);
        } catch {
          return true;
        }
      });
    }

    return filtered;
  }, [facilities, indiaBoundary, filterOutOfRegion, selectedState, selectedStateBoundary]);

  // Compute insights from Voronoi data
  const insights = useMemo(() => {
    if (!voronoiData || voronoiData.features.length === 0) {
      return null;
    }

    // Extract features with population data
    const featuresWithPop = voronoiData.features
      .filter(f => f.properties.population && f.properties.area_sq_km)
      .map(f => ({
        name: f.properties.name || 'Unknown',
        population: f.properties.population as number,
        area_sq_km: f.properties.area_sq_km as number,
        density: (f.properties.population as number) / (f.properties.area_sq_km as number),
        lat: f.properties.centroid_lat as number,
        lng: f.properties.centroid_lng as number,
      }));

    if (featuresWithPop.length === 0) {
      return null;
    }

    // Top 5 by population
    const topByPopulation = [...featuresWithPop]
      .sort((a, b) => b.population - a.population)
      .slice(0, 5);

    // Top 5 by density
    const topByDensity = [...featuresWithPop]
      .sort((a, b) => b.density - a.density)
      .slice(0, 5);

    // Top 5 by area
    const topByArea = [...featuresWithPop]
      .sort((a, b) => b.area_sq_km - a.area_sq_km)
      .slice(0, 5);

    return { topByPopulation, topByDensity, topByArea };
  }, [voronoiData]);

  // Handle uploaded facilities
  const handleUploadSuccess = useCallback((uploadedFacilities: Facility[], _filename: string) => {
    setFacilities(uploadedFacilities);
    setVoronoiData(null);
    setError(null);
  }, []);

  const handleUploadError = useCallback((errorMessage: string) => {
    setError(errorMessage);
  }, []);

  // Change boundary level
  const handleBoundaryChange = useCallback(async (level: 'none' | 'state' | 'district') => {
    setBoundaryLevel(level);
    setError(null);

    if (level === 'state' && !stateData) {
      setIsLoadingBoundaries(true);
      try {
        const data = await populationApi.getStateBoundaries();
        setStateData(data);
      } catch (err) {
        console.error('Failed to load states', err);
        setError('Failed to load state boundaries');
        setBoundaryLevel('none');
      } finally {
        setIsLoadingBoundaries(false);
      }
    } else if (level === 'district' && !districtData) {
      setIsLoadingBoundaries(true);
      try {
        const data = await populationApi.getDistrictBoundaries();
        setDistrictData(data);
      } catch (err) {
        console.error('Failed to load districts', err);
        setError('Failed to load district boundaries');
        setBoundaryLevel('none');
      } finally {
        setIsLoadingBoundaries(false);
      }
    }
  }, [stateData, districtData]);

  // Compute Voronoi diagram
  const computeVoronoi = useCallback(async () => {
    if (facilities.length < 3) {
      setError('Need at least 3 facilities to compute Voronoi diagram');
      return;
    }

    setIsComputing(true);
    setError(null);

    try {
      const result = await voronoiApi.compute({
        facilities,
        clip_to_india: true,
        include_population: true,
        state_filter: selectedState,
      });
      setVoronoiData(result);
      setApiStatus('online');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to compute Voronoi';
      setError(message);
      if (message.includes('Network Error')) {
        setApiStatus('offline');
      }
    } finally {
      setIsComputing(false);
    }
  }, [facilities, selectedState]);

  // Export handlers
  const handleExportPNG = useCallback(async () => {
    setIsExporting(true);
    setError(null);
    try {
      await exportToPNG('map-container', 'tessera-voronoi-map.png');
    } catch (err) {
      setError('Failed to export PNG');
    } finally {
      setIsExporting(false);
    }
  }, []);

  const handleExportGeoJSON = useCallback(() => {
    if (!voronoiData) {
      setError('No Voronoi data to export');
      return;
    }
    exportToGeoJSON(voronoiData, 'tessera-voronoi.geojson');
  }, [voronoiData]);

  // Context for Chatbot
  const chatContext = useMemo(() => {
    return {
      facilities_count: facilities.length,
      selected_state: selectedState,
      boundary_level: boundaryLevel,
      has_voronoi: !!voronoiData,
      insights: insights,
      largest_cell: insights?.topByArea[0] ? {
        name: insights.topByArea[0].name,
        area_sq_km: insights.topByArea[0].area_sq_km
      } : null,
      most_populated_cell: insights?.topByPopulation[0] ? {
        name: insights.topByPopulation[0].name,
        population: insights.topByPopulation[0].population,
        density: insights.topByPopulation[0].density
      } : null
    };
  }, [facilities.length, selectedState, boundaryLevel, voronoiData, insights]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-sm border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                </svg>
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900">Tessera</h1>
                <p className="text-sm text-gray-500">Voronoi Population Mapping</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm ${apiStatus === 'online' ? 'bg-green-100 text-green-700' :
                apiStatus === 'offline' ? 'bg-red-100 text-red-700' :
                  'bg-gray-100 text-gray-600'
                }`}>
                <span className={`w-2 h-2 rounded-full ${apiStatus === 'online' ? 'bg-green-500' :
                  apiStatus === 'offline' ? 'bg-red-500' :
                    'bg-gray-400'
                  }`} />
                {apiStatus === 'online' ? 'API Connected' :
                  apiStatus === 'offline' ? 'API Offline' :
                    'Checking API...'}
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Sidebar */}
          <div className="lg:col-span-1 space-y-6">
            {/* Upload Card */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Upload Facilities</h2>
              <FileUpload
                onUploadSuccess={handleUploadSuccess}
                onUploadError={handleUploadError}
              />
            </div>

            {/* Controls Card */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Controls</h2>

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-gray-700">Facilities loaded</span>
                  <span className="font-semibold text-blue-600">{facilities.length}</span>
                </div>

                <div className="flex items-center justify-between">
                  <label className="text-gray-700">Show Voronoi</label>
                  <button
                    onClick={() => setShowVoronoi(!showVoronoi)}
                    className={`relative w-12 h-6 rounded-full transition-colors ${showVoronoi ? 'bg-blue-500' : 'bg-gray-300'
                      }`}
                  >
                    <span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${showVoronoi ? 'translate-x-6' : 'translate-x-0.5'
                      }`} />
                  </button>
                </div>

                <div className="flex items-center justify-between">
                  <label className="text-gray-700">Boundaries</label>
                  <select
                    value={boundaryLevel}
                    onChange={(e) => handleBoundaryChange(e.target.value as 'none' | 'state' | 'district')}
                    disabled={isLoadingBoundaries}
                    className="bg-gray-50 border border-gray-300 text-gray-700 text-sm rounded-lg px-3 py-1.5 focus:ring-blue-500 focus:border-blue-500"
                  >
                    <option value="none">None</option>
                    <option value="state">States</option>
                    <option value="district">Districts</option>
                  </select>
                </div>

                <div className="flex items-center justify-between">
                  <label className="text-gray-700">Region</label>
                  <select
                    value={selectedState ?? 'all'}
                    onChange={(e) => setSelectedState(e.target.value === 'all' ? null : e.target.value)}
                    className="bg-gray-50 border border-gray-300 text-gray-700 text-sm rounded-lg px-3 py-1.5 focus:ring-blue-500 focus:border-blue-500 max-w-[140px]"
                  >
                    <option value="all">All India</option>
                    {statesList.map(state => (
                      <option key={state} value={state}>{state}</option>
                    ))}
                  </select>
                </div>

                {/* Filter Out-of-Region toggle - only show when a region is selected */}
                {selectedState && (
                  <div className="flex items-center justify-between">
                    <label className="text-gray-700 text-sm">Hide outside points</label>
                    <button
                      onClick={() => setFilterOutOfRegion(!filterOutOfRegion)}
                      className={`relative w-12 h-6 rounded-full transition-colors ${filterOutOfRegion ? 'bg-blue-500' : 'bg-gray-300'}`}
                    >
                      <span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${filterOutOfRegion ? 'translate-x-6' : 'translate-x-0.5'}`} />
                    </button>
                  </div>
                )}

                <button
                  onClick={computeVoronoi}
                  disabled={facilities.length < 3 || isComputing}
                  className={`w-full py-3 px-4 rounded-xl font-semibold text-white transition-all ${facilities.length >= 3 && !isComputing
                    ? 'bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 shadow-lg shadow-blue-500/25'
                    : 'bg-gray-300 cursor-not-allowed'
                    }`}
                >
                  {isComputing ? (
                    <span className="flex items-center justify-center gap-2">
                      <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Computing...
                    </span>
                  ) : (
                    'Compute Voronoi Diagram'
                  )}
                </button>

                {/* Export Buttons */}
                {voronoiData && (
                  <div className="flex gap-2 mt-2">
                    <button
                      onClick={handleExportPNG}
                      disabled={isExporting}
                      className="flex-1 py-2 px-3 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 flex items-center justify-center gap-1"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      PNG
                    </button>
                    <button
                      onClick={handleExportGeoJSON}
                      className="flex-1 py-2 px-3 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-1"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                      </svg>
                      GeoJSON
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Error Display */}
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-4">
                <div className="flex gap-3">
                  <svg className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p className="text-red-700 text-sm">{error}</p>
                </div>
              </div>
            )}
          </div>

          {/* Map + Legend Row */}
          <div className="lg:col-span-2">
            <div className="flex gap-4">
              {/* Map */}
              <div id="map-container" className="flex-1 bg-white rounded-2xl shadow-sm border border-gray-200 p-4 h-[700px] min-w-0">
                <MapComponent
                  facilities={displayedFacilities}
                  voronoiData={showVoronoi ? voronoiData ?? undefined : undefined}
                  districtData={boundaryLevel === 'state' ? stateData : boundaryLevel === 'district' ? districtData : undefined}
                  showDistricts={boundaryLevel !== 'none'}
                  flyTo={mapCenter}
                />
              </div>

              {/* Population Legend - Side Panel */}
              {voronoiData && showVoronoi && (
                <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-4 flex-shrink-0 w-32 h-44 self-start">
                  <div className="font-semibold text-black mb-3 text-sm">Population</div>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-3 rounded" style={{ backgroundColor: '#800026' }}></div>
                      <span className="text-xs text-black">&gt; 10M</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-3 rounded" style={{ backgroundColor: '#E31A1C' }}></div>
                      <span className="text-xs text-black">2M - 10M</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-3 rounded" style={{ backgroundColor: '#FD8D3C' }}></div>
                      <span className="text-xs text-black">500K - 2M</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-3 rounded" style={{ backgroundColor: '#FED976' }}></div>
                      <span className="text-xs text-black">100K - 500K</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-3 rounded" style={{ backgroundColor: '#FFEDA0' }}></div>
                      <span className="text-xs text-black">&lt; 100K</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Insights Panel - Below Map */}
            {insights && (
              <div className="mt-4 bg-white rounded-2xl shadow-sm border border-gray-200 p-4">
                <h3 className="font-semibold text-gray-800 flex items-center gap-2 mb-4">
                  <svg className="w-5 h-5 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  Insights
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Top by Population */}
                  <div>
                    <h4 className="text-sm font-medium text-gray-600 mb-3">Top 5 by Population</h4>
                    <div className="space-y-2">
                      {insights.topByPopulation.map((item, i) => (
                        <button
                          key={`pop-${i}`}
                          onClick={() => setMapCenter({ lat: item.lat, lng: item.lng, zoom: 10 })}
                          className="w-full flex justify-between items-center text-sm p-2 rounded-lg hover:bg-purple-50 transition-colors text-left"
                        >
                          <span className="text-gray-700 truncate flex-1 mr-2">
                            <span className="text-gray-400 font-mono mr-1">{i + 1}.</span>
                            <span className="text-blue-600 hover:underline">{item.name}</span>
                          </span>
                          <span className="text-gray-900 font-medium whitespace-nowrap">
                            {(item.population / 1000000).toFixed(1)}M
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Top by Density */}
                  <div>
                    <h4 className="text-sm font-medium text-gray-600 mb-3">Top 5 by Density</h4>
                    <div className="space-y-2">
                      {insights.topByDensity.map((item, i) => (
                        <button
                          key={`den-${i}`}
                          onClick={() => setMapCenter({ lat: item.lat, lng: item.lng, zoom: 10 })}
                          className="w-full flex justify-between items-center text-sm p-2 rounded-lg hover:bg-purple-50 transition-colors text-left"
                        >
                          <span className="text-gray-700 truncate flex-1 mr-2">
                            <span className="text-gray-400 font-mono mr-1">{i + 1}.</span>
                            <span className="text-blue-600 hover:underline">{item.name}</span>
                          </span>
                          <span className="text-gray-900 font-medium whitespace-nowrap">
                            {item.density.toFixed(0)}/km²
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Chat Interface */}
      <ChatInterface context={chatContext} />
    </div>
  );
}
