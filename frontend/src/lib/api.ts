import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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
export const voronoiApi = {
    compute: async (request: VoronoiRequest): Promise<GeoJSONFeatureCollection> => {
        const response = await api.post('/api/voronoi/compute', request);
        return response.data;
    },

    getSample: async (): Promise<GeoJSONFeatureCollection> => {
        const response = await api.get('/api/voronoi/sample');
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

export default api;
