import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

export interface Facility {
    id?: string;
    name: string;
    lat: number;
    lng: number;
    type?: string;
    state?: string;
    district?: string;
}

export interface VoronoiRequest {
    facilities: Facility[];
    clip_to_india: boolean;
    include_population?: boolean;
    state_filter?: string | null;  // If set, clip to this state instead of all India
}

export interface PopulationBreakdown {
    district: string;
    state: string;
    intersection_area_km2: number;
    overlap_percentage: number;
    contributed_population: number;
}

export interface GeoJSONFeature {
    type: 'Feature';
    id?: string;
    properties: {
        name?: string;
        facility_id?: string;
        type?: string;
        area_sq_km?: number;
        centroid_lat?: number;
        centroid_lng?: number;
        population?: number;
        population_breakdown?: PopulationBreakdown[];
        [key: string]: unknown;
    };
    geometry: {
        type: string;
        coordinates: number[][][] | number[][];
    };
}

export interface GeoJSONFeatureCollection {
    type: 'FeatureCollection';
    features: GeoJSONFeature[];
}

export interface UploadResponse {
    success: boolean;
    total_rows: number;
    valid_facilities: number;
    facilities: Facility[];
    errors: string[];
}

// API Functions
export interface FacilityInsights {
    minimum_enclosing_circle?: { center: [number, number]; radius_km: number };
    largest_empty_circle?: { center: [number, number]; radius_km: number };
    most_overburdened: Array<{
        name: string;
        population: number;
        area_sq_km: number;
        density: number;
        lat: number;
        lng: number;
    }>;
    most_underserved: Array<{
        name: string;
        area_sq_km: number;
        lat: number;
        lng: number;
    }>;
    coverage_stats: {
        total_population: number;
        total_area_sq_km: number;
        avg_population_per_facility: number;
        avg_area_per_facility: number;
        facility_count: number;
    };
    recommendations: Array<{
        type: string;
        priority: 'HIGH' | 'MEDIUM' | 'LOW';
        message: string;
        action: string;
        coords?: [number, number];
    }>;
}

export interface FindNearestRequest {
    click_lat: number;
    click_lng: number;
    facilities: Facility[];
}

export interface FindNearestResponse {
    index: number;
    facility: Facility | null;
}

export const voronoiApi = {
    compute: async (request: VoronoiRequest): Promise<GeoJSONFeatureCollection> => {
        const response = await api.post('/api/voronoi/compute', request);
        return response.data;
    },

    getSample: async (): Promise<GeoJSONFeatureCollection> => {
        const response = await api.get('/api/voronoi/sample');
        return response.data;
    },

    getInsights: async (request: VoronoiRequest): Promise<FacilityInsights> => {
        const response = await api.post('/api/voronoi/insights', request);
        return response.data;
    },

    findNearest: async (request: FindNearestRequest): Promise<FindNearestResponse> => {
        const response = await api.post('/api/voronoi/find-nearest', request);
        return response.data;
    },
};

export const uploadApi = {
    uploadCSV: async (file: File): Promise<UploadResponse> => {
        const formData = new FormData();
        formData.append('file', file);

        const response = await api.post('/api/upload/csv', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        return response.data;
    },

    getSampleData: async (): Promise<UploadResponse> => {
        const response = await api.get('/api/upload/sample-data');
        return response.data;
    },

    getAvailableFiles: async (): Promise<{ user_data: string[]; public_facilities: string[] }> => {
        const response = await api.get('/api/upload/available-files');
        return response.data;
    },

    loadFile: async (filename: string): Promise<UploadResponse> => {
        const response = await api.get(`/api/upload/load-file/${encodeURIComponent(filename)}`);
        return response.data;
    },

    loadPublicFile: async (filename: string): Promise<UploadResponse> => {
        const response = await api.get(`/api/upload/load-public-file/${encodeURIComponent(filename)}`);
        return response.data;
    },

    getBusStops: async (stateName: string): Promise<UploadResponse> => {
        const response = await api.get(`/api/upload/bus-stops/${encodeURIComponent(stateName)}`);
        return response.data;
    },
    uploadRawCSV: async (file: File): Promise<{ success: boolean; filename: string; path: string }> => {
        const formData = new FormData();
        formData.append('file', file);

        const response = await api.post('/api/upload/raw-csv', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        return response.data;
    },
};

export const boundariesApi = {
    getIndiaBoundary: async (): Promise<GeoJSONFeature> => {
        const response = await api.get('/api/boundaries/india');
        return response.data;
    },

    getBoundaries: async (level: 'state' | 'district'): Promise<GeoJSONFeatureCollection> => {
        const response = await api.get(`/api/boundaries/${level}`);
        return response.data;
    },

    getStatesList: async (): Promise<string[]> => {
        const response = await api.get('/api/boundaries/states/list');
        return response.data;
    },

    getStateBoundary: async (stateName: string): Promise<GeoJSONFeature> => {
        const response = await api.get(`/api/boundaries/states/${encodeURIComponent(stateName)}`);
        return response.data;
    },
};

export const populationApi = {
    getDistrictBoundaries: async (): Promise<GeoJSONFeatureCollection> => {
        const response = await api.get('/api/population/districts');
        return response.data;
    },
    getStateBoundaries: async (): Promise<GeoJSONFeatureCollection> => {
        const response = await api.get('/api/population/states');
        return response.data;
    },
};

export const healthApi = {
    check: async (): Promise<{ status: string; message: string }> => {
        const response = await api.get('/');
        return response.data;
    },
};

// Area Rating API Types
export interface PincodeInfo {
    pincode: string;
    place_name: string;
    state: string;
    district: string;
    lat: number;
    lng: number;
}

export interface FacilityBreakdown {
    score: number;
    distance_km: number | null;
    facility_name: string | null;
    weight: number;
}

export interface NearestFacility {
    type: string;
    name: string | null;
    distance_km: number;
    lat: number | null;
    lng: number | null;
}

export interface AreaRatingResponse {
    overall_score: number;
    grade: 'A' | 'B' | 'C' | 'D' | 'F';
    analysis_type: string;
    location: { lat: number; lng: number };
    breakdown: Record<string, FacilityBreakdown>;
    nearest_facilities: NearestFacility[];
    recommendations: Array<{
        type: string;
        priority: 'HIGH' | 'MEDIUM' | 'LOW';
        message: string;
    }>;
    pincode_info?: PincodeInfo;
}

export interface AnalysisType {
    id: string;
    name: string;
    description: string;
    datasets: string[];
}

export const areaRatingApi = {
    analyzeByPincode: async (pincode: string, analysisType: 'emergency' | 'living'): Promise<AreaRatingResponse> => {
        const response = await api.post('/api/rating/analyze', {
            pincode,
            analysis_type: analysisType,
        });
        return response.data;
    },

    analyzeByLocation: async (lat: number, lng: number, analysisType: 'emergency' | 'living'): Promise<AreaRatingResponse> => {
        const response = await api.post('/api/rating/analyze-location', {
            lat,
            lng,
            analysis_type: analysisType,
        });
        return response.data;
    },

    getPincodeInfo: async (pincode: string): Promise<PincodeInfo> => {
        const response = await api.get(`/api/rating/pincode/${pincode}`);
        return response.data;
    },

    searchPincodes: async (query: string, limit: number = 10): Promise<{ results: PincodeInfo[] }> => {
        const response = await api.get(`/api/rating/pincode/search/${query}?limit=${limit}`);
        return response.data;
    },

    reverseGeocode: async (lat: number, lng: number): Promise<PincodeInfo> => {
        const response = await api.post('/api/rating/reverse-geocode', { lat, lng });
        return response.data;
    },

    getDatasets: async (analysisType: 'emergency' | 'living'): Promise<{ analysis_type: string; datasets: string[] }> => {
        const response = await api.get(`/api/rating/datasets/${analysisType}`);
        return response.data;
    },

    getAnalysisTypes: async (): Promise<{ types: AnalysisType[] }> => {
        const response = await api.get('/api/rating/analysis-types');
        return response.data;
    },
};

// Chat API for AI assistant
export interface ChatMessage {
    role: 'user' | 'assistant';
    content: string;
    timestamp: string;
}

export interface ChatMessageRequest {
    session_id: string;
    message: string;
    api_key: string;
    provider?: string; // 'openai' or 'gemini'
}

export interface ChatMessageResponse {
    response: string;
    session_id: string;
    timestamp: string;
    data?: {
        type: string;
        facilities: Facility[];
    } | null;
}

export interface ConversationHistoryResponse {
    session_id: string;
    messages: ChatMessage[];
    count: number;
}

export interface NewSessionResponse {
    session_id: string;
    created_at: string;
}

export const chatApi = {
    newSession: async (): Promise<NewSessionResponse> => {
        const response = await api.post('/api/chat/new');
        return response.data;
    },

    sendMessage: async (request: ChatMessageRequest): Promise<ChatMessageResponse> => {
        const response = await api.post('/api/chat/message', request, {
            timeout: 120000, // 2 minutes for LLM responses
        });
        return response.data;
    },

    getHistory: async (sessionId: string): Promise<ConversationHistoryResponse> => {
        const response = await api.get(`/api/chat/history/${sessionId}`);
        return response.data;
    },

    clearHistory: async (sessionId: string): Promise<{ status: string; session_id: string }> => {
        const response = await api.delete(`/api/chat/clear/${sessionId}`);
        return response.data;
    },
};

export default api;

