'use client';

import React, { useState, useCallback } from 'react';
import { areaRatingApi, AreaRatingResponse, PincodeInfo } from '@/lib/api';

interface AreaAnalysisProps {
    onLocationSelect?: (lat: number, lng: number) => void;
}

export default function AreaAnalysis({ onLocationSelect }: AreaAnalysisProps) {
    const [analysisType, setAnalysisType] = useState<'emergency' | 'living'>('emergency');
    const [inputMethod, setInputMethod] = useState<'pincode' | 'location'>('pincode');
    const [pincode, setPincode] = useState('');
    const [pincodeResults, setPincodeResults] = useState<PincodeInfo[]>([]);
    const [showPincodeDropdown, setShowPincodeDropdown] = useState(false);
    const [loading, setLoading] = useState(false);
    const [locationLoading, setLocationLoading] = useState(false);
    const [result, setResult] = useState<AreaRatingResponse | null>(null);
    const [error, setError] = useState<string | null>(null);

    // Handle pincode search
    const handlePincodeChange = async (value: string) => {
        setPincode(value);
        setError(null);

        if (value.length >= 3) {
            try {
                const response = await areaRatingApi.searchPincodes(value, 5);
                setPincodeResults(response.results);
                setShowPincodeDropdown(true);
            } catch {
                setPincodeResults([]);
            }
        } else {
            setPincodeResults([]);
            setShowPincodeDropdown(false);
        }
    };

    // Handle pincode selection from dropdown
    const handlePincodeSelect = (info: PincodeInfo) => {
        setPincode(info.pincode);
        setShowPincodeDropdown(false);
        setPincodeResults([]);
    };

    // Get user's current location
    const handleUseLocation = useCallback(() => {
        if (!navigator.geolocation) {
            setError('Geolocation is not supported by your browser');
            return;
        }

        setLocationLoading(true);
        setError(null);

        navigator.geolocation.getCurrentPosition(
            async (position) => {
                const { latitude, longitude } = position.coords;
                setLocationLoading(false);

                // Analyze by location
                try {
                    setLoading(true);
                    const response = await areaRatingApi.analyzeByLocation(latitude, longitude, analysisType);
                    setResult(response);
                    if (onLocationSelect) {
                        onLocationSelect(latitude, longitude);
                    }
                } catch (err: unknown) {
                    const errorMessage = err instanceof Error ? err.message : 'Failed to analyze location';
                    setError(errorMessage);
                } finally {
                    setLoading(false);
                }
            },
            (err) => {
                setLocationLoading(false);
                setError(`Location error: ${err.message}`);
            },
            { enableHighAccuracy: true, timeout: 10000 }
        );
    }, [analysisType, onLocationSelect]);

    // Analyze by pincode
    const handleAnalyze = async () => {
        if (!pincode || pincode.length !== 6) {
            setError('Please enter a valid 6-digit pincode');
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const response = await areaRatingApi.analyzeByPincode(pincode, analysisType);
            setResult(response);
            if (onLocationSelect && response.location) {
                onLocationSelect(response.location.lat, response.location.lng);
            }
        } catch (err: unknown) {
            const errorMessage = err instanceof Error ? err.message : 'Failed to analyze pincode';
            setError(errorMessage);
        } finally {
            setLoading(false);
        }
    };

    // Get grade color
    const getGradeColor = (grade: string) => {
        switch (grade) {
            case 'A': return 'bg-green-500';
            case 'B': return 'bg-lime-500';
            case 'C': return 'bg-yellow-500';
            case 'D': return 'bg-orange-500';
            case 'F': return 'bg-red-500';
            default: return 'bg-gray-500';
        }
    };

    // Get priority color
    const getPriorityColor = (priority: string) => {
        switch (priority) {
            case 'HIGH': return 'text-red-700 bg-red-50 border border-red-200';
            case 'MEDIUM': return 'text-yellow-700 bg-yellow-50 border border-yellow-200';
            case 'LOW': return 'text-green-700 bg-green-50 border border-green-200';
            default: return 'text-gray-700 bg-gray-50 border border-gray-200';
        }
    };

    return (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">📊 Area Analysis</h2>

            {/* Analysis Type Toggle */}
            <div className="flex gap-2 mb-4">
                <button
                    onClick={() => setAnalysisType('emergency')}
                    className={`flex-1 py-2 px-4 rounded-lg font-medium transition-all ${analysisType === 'emergency'
                            ? 'bg-red-500 text-white shadow-lg shadow-red-200'
                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                        }`}
                >
                    🚨 Emergency
                </button>
                <button
                    onClick={() => setAnalysisType('living')}
                    className={`flex-1 py-2 px-4 rounded-lg font-medium transition-all ${analysisType === 'living'
                            ? 'bg-green-500 text-white shadow-lg shadow-green-200'
                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                        }`}
                >
                    🏠 Living
                </button>
            </div>

            {/* Input Method Toggle */}
            <div className="flex gap-2 mb-4">
                <button
                    onClick={() => setInputMethod('pincode')}
                    className={`flex-1 py-2 px-3 rounded-lg text-sm transition-all ${inputMethod === 'pincode'
                            ? 'bg-blue-500 text-white'
                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                        }`}
                >
                    📮 Enter Pincode
                </button>
                <button
                    onClick={() => setInputMethod('location')}
                    className={`flex-1 py-2 px-3 rounded-lg text-sm transition-all ${inputMethod === 'location'
                            ? 'bg-blue-500 text-white'
                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                        }`}
                >
                    📍 Use Location
                </button>
            </div>

            {/* Pincode Input */}
            {inputMethod === 'pincode' && (
                <div className="relative mb-4">
                    <div className="flex gap-2">
                        <input
                            type="text"
                            value={pincode}
                            onChange={(e) => handlePincodeChange(e.target.value)}
                            placeholder="Enter 6-digit pincode"
                            maxLength={6}
                            className="flex-1 bg-gray-50 border border-gray-300 rounded-lg px-4 py-2 text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        />
                        <button
                            onClick={handleAnalyze}
                            disabled={loading || pincode.length !== 6}
                            className="px-4 py-2 bg-blue-500 text-white rounded-lg font-medium hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                            {loading ? '...' : 'Analyze'}
                        </button>
                    </div>

                    {/* Pincode Dropdown */}
                    {showPincodeDropdown && pincodeResults.length > 0 && (
                        <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                            {pincodeResults.map((info) => (
                                <button
                                    key={info.pincode}
                                    onClick={() => handlePincodeSelect(info)}
                                    className="w-full px-4 py-2 text-left hover:bg-gray-50 transition-colors"
                                >
                                    <span className="text-gray-900 font-medium">{info.pincode}</span>
                                    <span className="text-gray-500 text-sm ml-2">
                                        {info.place_name}, {info.district}
                                    </span>
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Location Button */}
            {inputMethod === 'location' && (
                <div className="mb-4">
                    <button
                        onClick={handleUseLocation}
                        disabled={locationLoading || loading}
                        className="w-full py-3 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-lg font-medium hover:from-blue-600 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2 shadow-lg shadow-blue-200"
                    >
                        {locationLoading ? (
                            <>
                                <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                </svg>
                                Getting Location...
                            </>
                        ) : (
                            <>📍 Analyze My Current Location</>
                        )}
                    </button>
                </div>
            )}

            {/* Error Message */}
            {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                    {error}
                </div>
            )}

            {/* Results */}
            {result && (
                <div className="space-y-4 pt-4 border-t border-gray-100">
                    {/* Score Card */}
                    <div className="flex items-center gap-4 p-4 bg-gray-50 rounded-xl">
                        <div className={`w-14 h-14 ${getGradeColor(result.grade)} rounded-full flex items-center justify-center text-white text-xl font-bold shadow-lg`}>
                            {result.grade}
                        </div>
                        <div className="flex-1">
                            <div className="text-2xl font-bold text-gray-900">{result.overall_score.toFixed(0)}/100</div>
                            <div className="text-gray-500 text-sm">
                                {result.analysis_type === 'emergency' ? 'Emergency Response' : 'Living Condition'} Score
                            </div>
                            {result.pincode_info && (
                                <div className="text-gray-600 text-xs mt-1">
                                    📍 {result.pincode_info.place_name}, {result.pincode_info.district}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Breakdown */}
                    <div className="bg-gray-50 rounded-xl p-4">
                        <h3 className="text-gray-900 font-medium mb-3 text-sm">Facility Breakdown</h3>
                        <div className="space-y-2">
                            {Object.entries(result.breakdown).map(([facility, data]) => (
                                <div key={facility} className="flex items-center gap-2">
                                    <span className="text-gray-700 text-xs capitalize flex-1 truncate">
                                        {facility.replace(/_/g, ' ')}
                                    </span>
                                    <div className="w-20 bg-gray-200 rounded-full h-1.5">
                                        <div
                                            className={`h-1.5 rounded-full ${data.score >= 80 ? 'bg-green-500' : data.score >= 60 ? 'bg-yellow-500' : data.score >= 40 ? 'bg-orange-500' : 'bg-red-500'}`}
                                            style={{ width: `${data.score}%` }}
                                        />
                                    </div>
                                    <span className="text-gray-500 text-xs w-10 text-right">
                                        {data.distance_km != null ? `${data.distance_km.toFixed(1)}km` : 'N/A'}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Nearest Facilities */}
                    {result.nearest_facilities.length > 0 && (
                        <div className="bg-gray-50 rounded-xl p-4">
                            <h3 className="text-gray-900 font-medium mb-3 text-sm">Nearest Facilities</h3>
                            <div className="space-y-2">
                                {result.nearest_facilities.slice(0, 5).map((facility, idx) => (
                                    <div key={idx} className="flex items-center justify-between text-xs">
                                        <span className="text-gray-700">
                                            <span className="capitalize">{facility.type.replace(/_/g, ' ')}</span>
                                            {facility.name && <span className="text-gray-500 ml-1">({facility.name})</span>}
                                        </span>
                                        <span className="text-blue-500">{facility.distance_km.toFixed(1)} km</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Recommendations */}
                    {result.recommendations.length > 0 && (
                        <div className="space-y-2">
                            {result.recommendations.slice(0, 2).map((rec, idx) => (
                                <div
                                    key={idx}
                                    className={`text-xs p-2 rounded-lg ${getPriorityColor(rec.priority)}`}
                                >
                                    {rec.message}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
