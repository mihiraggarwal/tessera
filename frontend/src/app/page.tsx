"use client";

import { useState, useCallback, useEffect, useMemo } from "react";
import dynamic from "next/dynamic";
import FileUpload from "@/components/FileUpload";
import AreaAnalysis from "@/components/AreaAnalysis";
import { ChatButton } from "@/components/Chat";
import {
  voronoiApi,
  populationApi,
  boundariesApi,
  type Facility,
  type GeoJSONFeatureCollection,
  type GeoJSONFeature,
  type FacilityInsights,
} from "@/lib/api";
import { exportToPNG2, exportToGeoJSON } from "@/lib/export";
import * as turf from "@turf/turf";

// Dynamic import for Map (no SSR)
const MapComponent = dynamic(() => import("@/components/Map"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-[600px] bg-gray-100 rounded-xl flex items-center justify-center">
      <div className="text-gray-500 animate-pulse">Loading map...</div>
    </div>
  ),
});

export default function Home() {
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [voronoiData, setVoronoiData] =
    useState<GeoJSONFeatureCollection | null>(null);
  const [isComputing, setIsComputing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showVoronoi, setShowVoronoi] = useState(true);
  const [boundaryLevel, setBoundaryLevel] = useState<
    "none" | "state" | "district"
  >("none");
  const [stateData, setStateData] = useState<
    GeoJSONFeatureCollection | undefined
  >(undefined);
  const [districtData, setDistrictData] = useState<
    GeoJSONFeatureCollection | undefined
  >(undefined);
  const [apiStatus, setApiStatus] = useState<"unknown" | "online" | "offline">(
    "unknown",
  );
  const [isExporting, setIsExporting] = useState(false);
  const [isLoadingBoundaries, setIsLoadingBoundaries] = useState(false);
  const [statesList, setStatesList] = useState<string[]>([]);
  const [selectedState, setSelectedState] = useState<string | null>(null);
  const [filterOutOfRegion, setFilterOutOfRegion] = useState(false);
  const [selectedStateBoundary, setSelectedStateBoundary] =
    useState<GeoJSONFeature | null>(null);
  const [indiaBoundary, setIndiaBoundary] = useState<GeoJSONFeature | null>(
    null,
  );
  const [mapCenter, setMapCenter] = useState<{
    lat: number;
    lng: number;
    zoom: number;
  } | null>(null);

  // New state for facility management and insights
  const [editMode, setEditMode] = useState<"add" | "remove" | null>(null);
  const [facilityInsights, setFacilityInsights] =
    useState<FacilityInsights | null>(null);
  const [showEnclosingCircles, setShowEnclosingCircles] = useState(false);
  const [isLoadingInsights, setIsLoadingInsights] = useState(false);
  const [insightsError, setInsightsError] = useState<string | null>(null);

  // Fetch states list and India boundary on mount
  useEffect(() => {
    boundariesApi
      .getStatesList()
      .then(setStatesList)
      .catch((err) => console.error("Failed to load states list", err));

    // Fetch India boundary for filtering
    boundariesApi
      .getIndiaBoundary()
      .then(setIndiaBoundary)
      .catch((err) => console.error("Failed to load India boundary", err));
  }, []);

  // Fetch state boundary when selectedState changes
  useEffect(() => {
    if (selectedState) {
      boundariesApi
        .getStateBoundary(selectedState)
        .then(setSelectedStateBoundary)
        .catch((err) => {
          console.error("Failed to load state boundary", err);
          setSelectedStateBoundary(null);
        });
    } else {
      setSelectedStateBoundary(null);
    }
  }, [selectedState]);

  // Go back to the top after map center changed
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [mapCenter]);

  // Filter facilities: always exclude outside India, then optionally filter by state
  const displayedFacilities = useMemo(() => {
    // First filter to only facilities inside India
    let filtered = facilities;

    if (indiaBoundary) {
      filtered = facilities.filter((facility) => {
        try {
          const point = turf.point([facility.lng, facility.lat]);
          const polygon = indiaBoundary.geometry as
            | GeoJSON.Polygon
            | GeoJSON.MultiPolygon;
          return turf.booleanPointInPolygon(point, polygon);
        } catch {
          return false; // Exclude if we can't determine
        }
      });
    }

    // Then optionally filter by selected state
    if (filterOutOfRegion && selectedState && selectedStateBoundary) {
      filtered = filtered.filter((facility) => {
        try {
          const point = turf.point([facility.lng, facility.lat]);
          const polygon = selectedStateBoundary.geometry as
            | GeoJSON.Polygon
            | GeoJSON.MultiPolygon;
          return turf.booleanPointInPolygon(point, polygon);
        } catch {
          return true;
        }
      });
    }

    return filtered;
  }, [
    facilities,
    indiaBoundary,
    filterOutOfRegion,
    selectedState,
    selectedStateBoundary,
  ]);

  // Compute insights from Voronoi data
  const insights = useMemo(() => {
    if (!voronoiData || voronoiData.features.length === 0) {
      return null;
    }

    // Extract features with population data
    const featuresWithPop = voronoiData.features
      .filter((f) => f.properties.population && f.properties.area_sq_km)
      .map((f) => ({
        name: f.properties.name || "Unknown",
        population: f.properties.population as number,
        area_sq_km: f.properties.area_sq_km as number,
        density:
          (f.properties.population as number) /
          (f.properties.area_sq_km as number),
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

    return { topByPopulation, topByDensity };
  }, [voronoiData]);

  // Track if data came from chat (to clear FileUpload display)
  const [chatLoadedData, setChatLoadedData] = useState(false);

  // Handle uploaded facilities
  const handleUploadSuccess = useCallback(
    (uploadedFacilities: Facility[], _filename: string, fromChat = false) => {
      setFacilities(uploadedFacilities);
      setVoronoiData(null);
      setError(null);
      setChatLoadedData(fromChat);
    },
    [],
  );

  const handleUploadError = useCallback((errorMessage: string) => {
    setError(errorMessage);
  }, []);

  // Change boundary level
  const handleBoundaryChange = useCallback(
    async (level: "none" | "state" | "district") => {
      setBoundaryLevel(level);
      setError(null);

      if (level === "state" && !stateData) {
        setIsLoadingBoundaries(true);
        try {
          const data = await populationApi.getStateBoundaries();
          setStateData(data);
        } catch (err) {
          console.error("Failed to load states", err);
          setError("Failed to load state boundaries");
          setBoundaryLevel("none");
        } finally {
          setIsLoadingBoundaries(false);
        }
      } else if (level === "district" && !districtData) {
        setIsLoadingBoundaries(true);
        try {
          const data = await populationApi.getDistrictBoundaries();
          setDistrictData(data);
        } catch (err) {
          console.error("Failed to load districts", err);
          setError("Failed to load district boundaries");
          setBoundaryLevel("none");
        } finally {
          setIsLoadingBoundaries(false);
        }
      }
    },
    [stateData, districtData],
  );

  // Fetch facility insights
  const fetchInsights = useCallback(async () => {
    if (facilities.length < 3) return;

    setIsLoadingInsights(true);
    setInsightsError(null);
    try {
      const insights = await voronoiApi.getInsights({
        facilities,
        clip_to_india: true,
        include_population: true,
        state_filter: selectedState,
      });
      setFacilityInsights(insights);
    } catch (err) {
      console.error("Failed to fetch insights:", err);
      setInsightsError(
        "Could not load advanced analytics. Try re-computing the diagram.",
      );
    } finally {
      setIsLoadingInsights(false);
    }
  }, [facilities, selectedState]);

  // Compute Voronoi diagram
  const computeVoronoi = useCallback(async () => {
    if (facilities.length < 3) {
      setError("Need at least 3 facilities to compute Voronoi diagram");
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
      setApiStatus("online");

      // Also fetch insights after computing Voronoi
      fetchInsights();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to compute Voronoi";
      setError(message);
      if (message.includes("Network Error")) {
        setApiStatus("offline");
      }
    } finally {
      setIsComputing(false);
    }
  }, [facilities, selectedState, fetchInsights]);

  // Handle map click for adding/removing facilities
  const handleMapClick = useCallback(
    async (lat: number, lng: number) => {
      if (!editMode) return;

      if (editMode === "add") {
        // Add a new facility at the clicked location
        const newFacility: Facility = {
          id: `new-${Date.now()}`,
          name: `New Facility`,
          lat,
          lng,
          type: "added",
        };
        setFacilities((prev) => [...prev, newFacility]);
        setVoronoiData(null); // Clear voronoi to indicate recompute needed
        setFacilityInsights(null);
      } else if (editMode === "remove") {
        // Remove the nearest facility
        if (facilities.length === 0) return;

        try {
          const result = await voronoiApi.findNearest({
            click_lat: lat,
            click_lng: lng,
            facilities,
          });

          if (result.index >= 0) {
            setFacilities((prev) => prev.filter((_, i) => i !== result.index));
            setVoronoiData(null);
            setFacilityInsights(null);
          }
        } catch (err) {
          console.error("Failed to find nearest facility:", err);
        }
      }
    },
    [editMode, facilities],
  );

  const handleExportPNG = useCallback(async () => {
    setIsExporting(true);
    setError(null);
    try {
      await exportToPNG2("map-container", "tessera-voronoi-map.png");
    } catch (err) {
      setError("Failed to export PNG");
    } finally {
      setIsExporting(false);
    }
  }, []);

  const handleExportGeoJSON = useCallback(() => {
    if (!voronoiData) {
      setError("No Voronoi data to export");
      return;
    }
    exportToGeoJSON(voronoiData, "tessera-voronoi.geojson");
  }, [voronoiData]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-sm border-b border-gray-200 sticky top-0 z-2000">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                <svg
                  className="w-6 h-6 text-white"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"
                  />
                </svg>
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900">Tessera</h1>
                <p className="text-sm text-gray-500">
                  Voronoi Population Mapping
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm ${
                  apiStatus === "online"
                    ? "bg-green-100 text-green-700"
                    : apiStatus === "offline"
                      ? "bg-red-100 text-red-700"
                      : "bg-gray-100 text-gray-600"
                }`}
              >
                <span
                  className={`w-2 h-2 rounded-full ${
                    apiStatus === "online"
                      ? "bg-green-500"
                      : apiStatus === "offline"
                        ? "bg-red-500"
                        : "bg-gray-400"
                  }`}
                />
                {apiStatus === "online"
                  ? "API Connected"
                  : apiStatus === "offline"
                    ? "API Offline"
                    : "Checking API..."}
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
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Upload Facilities
              </h2>
              <FileUpload
                onUploadSuccess={handleUploadSuccess}
                onUploadError={handleUploadError}
                externalClear={chatLoadedData}
              />
            </div>

            {/* Controls Card */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Controls
              </h2>

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-gray-700">Facilities loaded</span>
                  <span className="font-semibold text-blue-600">
                    {facilities.length}
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <label className="text-gray-700">Show Voronoi</label>
                  <button
                    onClick={() => setShowVoronoi(!showVoronoi)}
                    className={`relative w-12 h-6 rounded-full transition-colors ${
                      showVoronoi ? "bg-blue-500" : "bg-gray-300"
                    }`}
                  >
                    <span
                      className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                        showVoronoi ? "translate-x-0.5" : "-translate-x-5.5"
                      }`}
                    />
                  </button>
                </div>

                <div className="flex items-center justify-between">
                  <label className="text-gray-700">Boundaries</label>
                  <select
                    value={boundaryLevel}
                    onChange={(e) =>
                      handleBoundaryChange(
                        e.target.value as "none" | "state" | "district",
                      )
                    }
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
                    value={selectedState ?? "all"}
                    onChange={(e) =>
                      setSelectedState(
                        e.target.value === "all" ? null : e.target.value,
                      )
                    }
                    className="bg-gray-50 border border-gray-300 text-gray-700 text-sm rounded-lg px-3 py-1.5 focus:ring-blue-500 focus:border-blue-500 max-w-[140px]"
                  >
                    <option value="all">All India</option>
                    {statesList.map((state) => (
                      <option key={state} value={state}>
                        {state}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Filter Out-of-Region toggle - only show when a region is selected */}
                {selectedState && (
                  <div className="flex items-center justify-between">
                    <label className="text-gray-700 text-sm">
                      Hide outside points
                    </label>
                    <button
                      onClick={() => setFilterOutOfRegion(!filterOutOfRegion)}
                      className={`relative w-12 h-6 rounded-full transition-colors ${filterOutOfRegion ? "bg-blue-500" : "bg-gray-300"}`}
                    >
                      <span
                        className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${filterOutOfRegion ? "translate-x-0.5" : "-translate-x-5.5"}`}
                      />
                    </button>
                  </div>
                )}

                {/* Edit Mode Controls */}
                <div className="pt-3 border-t border-gray-100">
                  <label className="text-gray-700 text-sm font-medium mb-2 block">
                    Edit Facilities
                  </label>
                  <div className="flex gap-2">
                    <button
                      onClick={() =>
                        setEditMode(editMode === "add" ? null : "add")
                      }
                      className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-1 ${
                        editMode === "add"
                          ? "bg-green-500 text-white"
                          : "bg-gray-100 text-gray-700 hover:bg-green-100"
                      }`}
                    >
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M12 4v16m8-8H4"
                        />
                      </svg>
                      Add
                    </button>
                    <button
                      onClick={() =>
                        setEditMode(editMode === "remove" ? null : "remove")
                      }
                      className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-1 ${
                        editMode === "remove"
                          ? "bg-red-500 text-white"
                          : "bg-gray-100 text-gray-700 hover:bg-red-100"
                      }`}
                    >
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M20 12H4"
                        />
                      </svg>
                      Remove
                    </button>
                  </div>
                  {editMode && (
                    <p className="text-xs text-gray-500 mt-1">
                      Click on map to{" "}
                      {editMode === "add"
                        ? "add a new facility"
                        : "remove nearest facility"}
                    </p>
                  )}
                </div>

                {/* Show Enclosing Circles Toggle */}
                {voronoiData && (
                  <div className="flex items-center justify-between">
                    <label className="text-gray-700 text-sm">
                      Show Insights on Map
                    </label>
                    <button
                      onClick={() =>
                        setShowEnclosingCircles(!showEnclosingCircles)
                      }
                      className={`relative w-12 h-6 rounded-full transition-colors ${showEnclosingCircles ? "bg-orange-500" : "bg-gray-300"}`}
                    >
                      <span
                        className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${showEnclosingCircles ? "translate-x-0.5" : "-translate-x-5.5"}`}
                      />
                    </button>
                  </div>
                )}

                <button
                  onClick={computeVoronoi}
                  disabled={facilities.length < 3 || isComputing}
                  className={`w-full py-3 px-4 rounded-xl font-semibold text-white transition-all ${
                    facilities.length >= 3 && !isComputing
                      ? "bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 shadow-lg shadow-blue-500/25"
                      : "bg-gray-300 cursor-not-allowed"
                  }`}
                >
                  {isComputing ? (
                    <span className="flex items-center justify-center gap-2">
                      <svg
                        className="animate-spin w-5 h-5"
                        fill="none"
                        viewBox="0 0 24 24"
                      >
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                        />
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                        />
                      </svg>
                      Computing...
                    </span>
                  ) : (
                    "Compute Voronoi Diagram"
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
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                        />
                      </svg>
                      PNG
                    </button>
                    <button
                      onClick={handleExportGeoJSON}
                      className="flex-1 py-2 px-3 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-1"
                    >
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                        />
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
                  <svg
                    className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                  <p className="text-red-700 text-sm">{error}</p>
                </div>
              </div>
            )}

            {/* Area Analysis Card */}
            <AreaAnalysis
              onLocationSelect={(lat, lng) => {
                setMapCenter({ lat, lng, zoom: 12 });
              }}
            />
          </div>

          {/* Map + Legend Row */}
          <div className="lg:col-span-2">
            <div className="flex gap-4">
              {/* Map */}
              <div
                id="map-container"
                className="flex-1 bg-white rounded-2xl shadow-sm border border-gray-200 p-4 h-[700px] min-w-0"
              >
                <MapComponent
                  facilities={displayedFacilities}
                  voronoiData={
                    showVoronoi ? (voronoiData ?? undefined) : undefined
                  }
                  districtData={
                    boundaryLevel === "state"
                      ? stateData
                      : boundaryLevel === "district"
                        ? districtData
                        : undefined
                  }
                  showDistricts={boundaryLevel !== "none"}
                  flyTo={mapCenter}
                  onMapClick={handleMapClick}
                  editMode={editMode}
                  showEnclosingCircles={showEnclosingCircles}
                  enclosingCircles={
                    facilityInsights
                      ? {
                          mec: facilityInsights.minimum_enclosing_circle,
                          largestEmpty: facilityInsights.largest_empty_circle,
                        }
                      : undefined
                  }
                />
              </div>

              {/* Population Legend - Side Panel */}
              {voronoiData && showVoronoi && (
                <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-4 flex-shrink-0 w-32 h-44 self-start">
                  <div className="font-semibold text-black mb-3 text-sm">
                    Population
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-4 h-3 rounded"
                        style={{ backgroundColor: "#800026" }}
                      ></div>
                      <span className="text-xs text-black">&gt; 10M</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div
                        className="w-4 h-3 rounded"
                        style={{ backgroundColor: "#E31A1C" }}
                      ></div>
                      <span className="text-xs text-black">2M - 10M</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div
                        className="w-4 h-3 rounded"
                        style={{ backgroundColor: "#FD8D3C" }}
                      ></div>
                      <span className="text-xs text-black">500K - 2M</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div
                        className="w-4 h-3 rounded"
                        style={{ backgroundColor: "#FED976" }}
                      ></div>
                      <span className="text-xs text-black">100K - 500K</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div
                        className="w-4 h-3 rounded"
                        style={{ backgroundColor: "#FFEDA0" }}
                      ></div>
                      <span className="text-xs text-black">&lt; 100K</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Insights Panel - Below Map */}
            {/* Consolidated Analytics & Insights Panel */}
            {(insights ||
              facilityInsights ||
              isLoadingInsights ||
              insightsError) && (
              <div className="mt-8 bg-white rounded-3xl shadow-xl border border-gray-200 overflow-hidden">
                {/* Panel Header */}
                <div className="bg-gradient-to-r from-gray-50 to-white px-6 py-4 border-b border-gray-100 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-indigo-100 flex items-center justify-center">
                      <svg
                        className="w-5 h-5 text-indigo-600"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                        />
                      </svg>
                    </div>
                    <h3 className="text-lg font-bold text-gray-900 tracking-tight">
                      Facility Analytics & Strategic Insights
                    </h3>
                  </div>
                  {isLoadingInsights && (
                    <div className="flex items-center gap-2 text-indigo-600">
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                          fill="none"
                        />
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                        />
                      </svg>
                      <span className="text-xs font-semibold animate-pulse">
                        Analyzing...
                      </span>
                    </div>
                  )}
                </div>

                <div className="p-6">
                  {/* Error State */}
                  {insightsError && (
                    <div className="mb-6 p-4 bg-red-50 border border-red-100 rounded-2xl flex items-center gap-3">
                      <span className="text-2xl">⚠️</span>
                      <div>
                        <p className="text-sm font-bold text-red-800">
                          Advanced analysis unavailable
                        </p>
                        <p className="text-xs text-red-600">{insightsError}</p>
                      </div>
                    </div>
                  )}

                  {/* AI Recommendations - Prominent at the top */}
                  {(facilityInsights?.recommendations?.length ?? 0) > 0 && (
                    <div className="mb-8 p-5 bg-gradient-to-br from-indigo-50 via-purple-50 to-blue-50 rounded-2xl border border-indigo-100 shadow-sm relative overflow-hidden">
                      <div className="absolute top-0 right-0 p-4 opacity-10">
                        <span className="text-6xl text-indigo-600">✨</span>
                      </div>
                      <h4 className="text-sm font-bold text-indigo-900 mb-4 flex items-center gap-2">
                        Strategic Recommendations
                      </h4>
                      <div className="grid grid-cols-1 gap-3 relative z-10">
                        {facilityInsights?.recommendations?.map((rec, i) => (
                          <div
                            key={i}
                            className={`p-4 rounded-xl border flex gap-4 bg-white/80 backdrop-blur-sm shadow-sm transition-all hover:shadow-md ${
                              rec.priority === "HIGH"
                                ? "border-red-100"
                                : "border-indigo-100"
                            }`}
                          >
                            <div
                              className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
                                rec.priority === "HIGH"
                                  ? "bg-red-50 text-red-600"
                                  : "bg-indigo-50 text-indigo-600"
                              }`}
                            >
                              <span className="text-xl">
                                {rec.type === "CRITICAL_GAP"
                                  ? "🚩"
                                  : rec.type === "OVERBURDENED"
                                    ? "⚖️"
                                    : "💡"}
                              </span>
                            </div>
                            <div className="flex-1">
                              <div className="flex items-center justify-between mb-1">
                                <span
                                  className={`text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full ${
                                    rec.priority === "HIGH"
                                      ? "bg-red-100 text-red-700"
                                      : "bg-indigo-100 text-indigo-700"
                                  }`}
                                >
                                  {rec.priority} PRIORITY
                                </span>
                                {rec.coords && (
                                  <button
                                    onClick={() =>
                                      setMapCenter({
                                        lat: rec.coords![1],
                                        lng: rec.coords![0],
                                        zoom: 10,
                                      })
                                    }
                                    className="text-xs font-bold text-indigo-600 hover:text-indigo-800 transition-colors"
                                  >
                                    VIEW SITE →
                                  </button>
                                )}
                              </div>
                              <p className="text-sm text-gray-900 font-bold leading-snug">
                                {rec.message}
                              </p>
                              <p className="text-xs text-gray-600 mt-1.5">
                                {rec.action}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
                    {/* Stats Grid */}
                    {facilityInsights?.coverage_stats && (
                      <div className="lg:col-span-12 grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                        <div className="bg-blue-50/50 rounded-2xl p-4 border border-blue-100/50">
                          <p className="text-[10px] font-bold text-blue-600 uppercase mb-1">
                            Population Reach
                          </p>
                          <p className="text-2xl font-black text-blue-900">
                            {(
                              facilityInsights.coverage_stats.total_population /
                              1000000
                            ).toFixed(1)}
                            M
                          </p>
                          <p className="text-xs text-blue-600/70 mt-1">
                            Total across{" "}
                            {facilityInsights.coverage_stats.facility_count}{" "}
                            regions
                          </p>
                        </div>

                        <div className="bg-orange-50/50 rounded-2xl p-4 border border-orange-100/50">
                          <p className="text-[10px] font-bold text-orange-600 uppercase mb-1">
                            Coverage Gap
                          </p>
                          <p className="text-2xl font-black text-orange-900">
                            {facilityInsights.largest_empty_circle?.radius_km
                              ? `${facilityInsights.largest_empty_circle.radius_km.toFixed(1)}km`
                              : "N/A"}
                          </p>
                          <p className="text-xs text-orange-600/70 mt-1">
                            Max underserved radius
                          </p>
                          {facilityInsights.largest_empty_circle?.center && (
                            <button
                              onClick={() => {
                                const [lng, lat] =
                                  facilityInsights.largest_empty_circle!.center;
                                setMapCenter({ lat, lng, zoom: 8 });
                              }}
                              className="mt-2 text-[10px] font-bold text-orange-700 hover:underline"
                            >
                              LOCATE GAP →
                            </button>
                          )}
                        </div>

                        <div className="bg-purple-50/50 rounded-2xl p-4 border border-purple-100/50">
                          <p className="text-[10px] font-bold text-purple-600 uppercase mb-1">
                            Service Density
                          </p>
                          <p className="text-2xl font-black text-purple-900">
                            {(
                              facilityInsights.coverage_stats
                                .avg_population_per_facility / 1000
                            ).toFixed(0)}
                            K
                          </p>
                          <p className="text-xs text-purple-600/70 mt-1">
                            Avg people per facility
                          </p>
                        </div>
                      </div>
                    )}

                    {/* Top 5 Lists */}
                    {insights && (
                      <div className="lg:col-span-12 grid grid-cols-1 md:grid-cols-2 gap-8 pt-8 border-t border-gray-100">
                        {/* Top by Population */}
                        <div className="bg-gray-50/50 rounded-2xl p-6">
                          <h4 className="text-sm font-bold text-gray-800 mb-4 flex items-center gap-2">
                            High Load Regions
                          </h4>
                          <div className="space-y-3">
                            {insights.topByPopulation.map((item, i) => (
                              <button
                                key={`pop-${i}`}
                                onClick={() =>
                                  setMapCenter({
                                    lat: item.lat,
                                    lng: item.lng,
                                    zoom: 10,
                                  })
                                }
                                className="w-full flex justify-between items-center group hover:cursor-pointer"
                              >
                                <span className="text-sm text-gray-700 font-medium group-hover:text-indigo-600 transition-colors truncate flex-1 text-left">
                                  {i + 1}. {item.name}
                                </span>
                                <span className="text-sm font-bold text-gray-900 bg-white px-2 py-0.5 rounded-md shadow-sm">
                                  {(item.population / 1000000).toFixed(1)}M
                                </span>
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* Top by Density */}
                        <div className="bg-gray-50/50 rounded-2xl p-6">
                          <h4 className="text-sm font-bold text-gray-800 mb-4 flex items-center gap-2">
                            Dense Regions
                          </h4>
                          <div className="space-y-3">
                            {insights.topByDensity.map((item, i) => (
                              <button
                                key={`den-${i}`}
                                onClick={() =>
                                  setMapCenter({
                                    lat: item.lat,
                                    lng: item.lng,
                                    zoom: 10,
                                  })
                                }
                                className="w-full flex justify-between items-center group hover:cursor-pointer"
                              >
                                <span className="text-sm text-gray-700 font-medium group-hover:text-indigo-600 transition-colors truncate flex-1 text-left">
                                  {i + 1}. {item.name}
                                </span>
                                <span className="text-sm font-bold text-gray-900 bg-white px-2 py-0.5 rounded-md shadow-sm">
                                  {item.density.toFixed(0)}/km²
                                </span>
                              </button>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {!facilityInsights &&
                  facilities.length >= 3 &&
                  !isComputing && (
                    <div className="p-12 bg-gray-50 text-center border-t border-gray-100">
                      <p className="text-gray-500 text-sm mb-4">
                        Detailed coverage analytics and underscores are ready to
                        be computed.
                      </p>
                      <button
                        onClick={computeVoronoi}
                        className="px-8 py-3 bg-indigo-600 text-white rounded-xl font-bold hover:bg-indigo-700 transition-all shadow-lg shadow-indigo-200"
                      >
                        Compute Advanced Insights
                      </button>
                    </div>
                  )}
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Floating Chat Button */}
      <ChatButton
        onDataLoad={(facilities, filename) =>
          handleUploadSuccess(facilities, filename, true)
        }
      />
    </div>
  );
}
