"use client";

import { useState, useEffect } from "react";
import { routingApi, type PointAnalysisResponse } from "@/lib/api";

interface PointAnalysisPanelProps {
  lat: number | null;
  lng: number | null;
  onClose: () => void;
}

export default function PointAnalysisPanel({
  lat,
  lng,
  onClose,
}: PointAnalysisPanelProps) {
  const [analysis, setAnalysis] = useState<PointAnalysisResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Analyze point when coordinates change
  const analyzePoint = async () => {
    if (lat === null || lng === null) return;

    setIsLoading(true);
    setError(null);

    try {
      const result = await routingApi.analyzePoint({
        lat,
        lng,
        k_candidates: 5,
      });
      setAnalysis(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to analyze point");
    } finally {
      setIsLoading(false);
    }
  };

  // Trigger analysis when component mounts or coordinates change
  useEffect(() => {
    if (lat !== null && lng !== null) {
      analyzePoint();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lat, lng]);

  if (lat === null || lng === null) {
    return null;
  }

  return (
    <div className="fixed bottom-4 left-4 z-50 bg-white rounded-2xl shadow-2xl border border-gray-200 p-5 w-96 max-h-[80vh] overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-xl">📍</span>
          <h3 className="text-lg font-bold text-gray-900">Route Analysis</h3>
        </div>
        <button
          onClick={onClose}
          className="p-2 text-black hover:bg-gray-100 rounded-lg transition-colors"
        >
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      {/* Coordinates */}
      <div className="mb-4 p-3 bg-gray-50 rounded-xl">
        <p className="text-xs text-gray-500 mb-1">Selected Location</p>
        <p className="text-sm font-mono text-gray-700">
          {lat.toFixed(6)}, {lng.toFixed(6)}
        </p>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="flex items-center justify-center p-8">
          <div className="flex items-center gap-3">
            <svg
              className="animate-spin h-5 w-5 text-indigo-600"
              viewBox="0 0 24 24"
            >
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
            <span className="text-sm text-gray-600">
              Analyzing route distances...
            </span>
          </div>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-100 rounded-xl mb-4">
          <p className="text-sm text-red-700">{error}</p>
          <button
            onClick={analyzePoint}
            className="mt-2 text-xs text-red-600 hover:text-red-800 font-medium"
          >
            Try again
          </button>
        </div>
      )}

      {/* Results */}
      {analysis && !isLoading && (
        <div className="space-y-4">
          {/* Routing Status */}
          <div
            className={`flex items-center gap-2 p-2 rounded-lg ${
              analysis.routing_available
                ? "bg-green-50 text-green-700"
                : "bg-amber-50 text-amber-700"
            }`}
          >
            <span className="text-sm">
              {analysis.routing_available ? "🛣️" : "📏"}
            </span>
            <span className="text-xs font-medium">
              {analysis.routing_available
                ? "Road routing available"
                : "Using Euclidean distance only"}
            </span>
          </div>

          {/* Comparison Cards */}
          <div className="grid grid-cols-2 gap-3">
            {/* Euclidean Nearest */}
            <div className="p-3 bg-blue-50 rounded-xl border border-blue-100">
              <p className="text-[10px] uppercase tracking-wide text-blue-600 font-semibold mb-1">
                Euclidean Nearest
              </p>
              <p
                className="text-sm font-bold text-gray-900 truncate"
                title={analysis.euclidean_nearest.facility_name}
              >
                {analysis.euclidean_nearest.facility_name}
              </p>
              <p className="text-lg font-bold text-blue-700">
                {analysis.euclidean_nearest.distance_km} km
              </p>
            </div>

            {/* Route Nearest */}
            <div
              className={`p-3 rounded-xl border ${
                analysis.differs
                  ? "bg-amber-50 border-amber-200"
                  : "bg-green-50 border-green-100"
              }`}
            >
              <p
                className={`text-[10px] uppercase tracking-wide font-semibold mb-1 ${
                  analysis.differs ? "text-amber-600" : "text-green-600"
                }`}
              >
                Route Nearest
              </p>
              <p
                className="text-sm font-bold text-gray-900 truncate"
                title={analysis.route_nearest.facility_name}
              >
                {analysis.route_nearest.facility_name}
              </p>
              <p
                className={`text-lg font-bold ${
                  analysis.differs ? "text-amber-700" : "text-green-700"
                }`}
              >
                {analysis.route_nearest.distance_km} km
              </p>
              {analysis.route_nearest.duration_min && (
                <p className="text-xs text-gray-600">
                  ~{Math.round(analysis.route_nearest.duration_min)} min drive
                </p>
              )}
            </div>
          </div>

          {/* Warning if different */}
          {analysis.differs && (
            <div className="p-3 bg-gradient-to-r from-amber-50 to-orange-50 rounded-xl border border-amber-200">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-lg">⚠️</span>
                <span className="text-sm font-bold text-amber-800">
                  Route Differs!
                </span>
              </div>
              <p className="text-xs text-amber-700">
                Road network requires{" "}
                <span className="font-bold">
                  {Math.round((analysis.distortion_ratio - 1) * 100)}%
                </span>{" "}
                more distance. The nearest by road is different from
                straight-line nearest.
              </p>
            </div>
          )}

          {/* Distortion Ratio */}
          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-xl">
            <span className="text-xs text-gray-600">Distortion Ratio</span>
            <span
              className={`text-sm font-bold ${
                analysis.distortion_ratio > 1.5
                  ? "text-red-600"
                  : analysis.distortion_ratio > 1.2
                    ? "text-amber-600"
                    : "text-green-600"
              }`}
            >
              {analysis.distortion_ratio.toFixed(2)}×
            </span>
          </div>

          {/* All Candidates (Expandable) */}
          <details className="group">
            <summary className="cursor-pointer text-sm text-gray-600 hover:text-gray-900 flex items-center gap-1">
              <svg
                className="w-4 h-4 rotate-0 group-open:rotate-90 transition-transform"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
              View all {analysis.all_candidates.length} candidates
            </summary>
            <div className="mt-3 space-y-2">
              {analysis.all_candidates.map((candidate) => (
                <div
                  key={candidate.facility_id}
                  className={`flex items-center text-black justify-between p-2 rounded-lg text-xs ${
                    candidate.route_rank === 1
                      ? "bg-green-50 border border-green-200"
                      : "bg-gray-50"
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <p
                      className="font-medium truncate"
                      title={candidate.facility_name}
                    >
                      {candidate.facility_name}
                    </p>
                    <p className="text-gray-500">
                      Euc: #{candidate.euclidean_rank} | Route: #
                      {candidate.route_rank}
                    </p>
                  </div>
                  <div className="text-right ml-2">
                    <p className="font-mono">
                      {candidate.route_connected
                        ? `${candidate.route_distance_km} km`
                        : "—"}
                    </p>
                    {candidate.route_connected && (
                      <p className="text-gray-500">
                        {Math.round(candidate.route_duration_min)} min
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </details>
        </div>
      )}

      {/* Retry Button */}
      {!isLoading && !analysis && (
        <button
          onClick={analyzePoint}
          className="w-full py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors"
        >
          Analyze Point
        </button>
      )}
    </div>
  );
}
