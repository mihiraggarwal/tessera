'use client';

import { useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import FileUpload from '@/components/FileUpload';
import { voronoiApi, populationApi, type Facility, type GeoJSONFeatureCollection } from '@/lib/api';
import { exportToPNG, exportToGeoJSON } from '@/lib/export';

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

  // Handle uploaded facilities
  const handleUploadSuccess = useCallback((uploadedFacilities: Facility[]) => {
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
  }, [facilities]);

  // Load sample data
  const loadSampleData = useCallback(async () => {
    setIsComputing(true);
    setError(null);

    try {
      const result = await voronoiApi.getSample();

      // Extract facilities from the sample response
      const sampleFacilities: Facility[] = result.features.map((f, i) => ({
        id: String(f.id || i),
        name: String(f.properties.name || `Sample ${i}`),
        lat: f.properties.centroid_lat as number,
        lng: f.properties.centroid_lng as number,
        type: f.properties.type as string,
      }));

      setFacilities(sampleFacilities);
      setVoronoiData(result);
      setApiStatus('online');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load sample';
      setError(message);
      if (message.includes('Network Error')) {
        setApiStatus('offline');
      }
    } finally {
      setIsComputing(false);
    }
  }, []);

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

              <div className="mt-4 flex items-center justify-center">
                <span className="text-gray-400 text-sm">or</span>
              </div>

              <button
                onClick={loadSampleData}
                disabled={isComputing}
                className="mt-4 w-full py-2.5 px-4 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl font-medium transition-colors disabled:opacity-50"
              >
                Load Sample Data
              </button>
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

          {/* Map */}
          <div className="lg:col-span-2">
            <div id="map-container" className="bg-white rounded-2xl shadow-sm border border-gray-200 p-4 h-[700px] relative">
              <MapComponent
                facilities={facilities}
                voronoiData={showVoronoi ? voronoiData ?? undefined : undefined}
                districtData={boundaryLevel === 'state' ? stateData : boundaryLevel === 'district' ? districtData : undefined}
                showDistricts={boundaryLevel !== 'none'}
              />

              {/* Population Legend */}
              {voronoiData && showVoronoi && (
                <div className="absolute bottom-6 right-6 bg-white/95 backdrop-blur-sm rounded-lg shadow-lg p-3 text-xs border border-gray-200">
                  <div className="font-semibold text-gray-700 mb-2">Population</div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-3 rounded" style={{ backgroundColor: '#800026' }}></div>
                      <span>&gt; 10M</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-3 rounded" style={{ backgroundColor: '#E31A1C' }}></div>
                      <span>2M - 10M</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-3 rounded" style={{ backgroundColor: '#FD8D3C' }}></div>
                      <span>500K - 2M</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-3 rounded" style={{ backgroundColor: '#FED976' }}></div>
                      <span>100K - 500K</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-3 rounded" style={{ backgroundColor: '#FFEDA0' }}></div>
                      <span>&lt; 100K</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
