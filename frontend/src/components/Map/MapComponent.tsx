'use client';

import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { GeoJSONFeatureCollection, Facility } from '@/lib/api';

// Fix for default markers in Next.js
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

const DefaultIcon = L.icon({
    iconUrl: icon.src,
    shadowUrl: iconShadow.src,
    iconSize: [25, 41],
    iconAnchor: [12, 41],
});

L.Marker.prototype.options.icon = DefaultIcon;

interface MapProps {
    facilities?: Facility[];
    voronoiData?: GeoJSONFeatureCollection;
    districtData?: GeoJSONFeatureCollection;
    showDistricts?: boolean;
    center?: [number, number];
    zoom?: number;
    onMapClick?: (lat: number, lng: number) => void;
    flyTo?: { lat: number; lng: number; zoom: number } | null;
}

// Population coloring (Yellow -> Red)
const getPopulationColor = (pop: number): string => {
    return pop > 10000000 ? '#800026' :
        pop > 5000000 ? '#BD0026' :
            pop > 2000000 ? '#E31A1C' :
                pop > 1000000 ? '#FC4E2A' :
                    pop > 500000 ? '#FD8D3C' :
                        pop > 200000 ? '#FEB24C' :
                            pop > 100000 ? '#FED976' :
                                '#FFEDA0';
};

// Random color generator for Voronoi cells
const getRandomColor = (seed: number): string => {
    const colors = [
        '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
        '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
        '#F8B500', '#00CED1', '#FF69B4', '#32CD32', '#FFD700',
    ];
    return colors[seed % colors.length];
};

export default function MapComponent({
    facilities = [],
    voronoiData,
    districtData,
    showDistricts = false,
    center = [20.5937, 78.9629], // Center of India
    zoom = 5,
    onMapClick,
    flyTo,
}: MapProps) {
    const mapRef = useRef<L.Map | null>(null);
    const mapContainerRef = useRef<HTMLDivElement>(null);
    const markersLayerRef = useRef<L.LayerGroup | null>(null);
    const voronoiLayerRef = useRef<L.LayerGroup | null>(null);
    const districtsLayerRef = useRef<L.LayerGroup | null>(null);

    // Initialize map
    useEffect(() => {
        if (!mapContainerRef.current || mapRef.current) return;

        const map = L.map(mapContainerRef.current).setView(center, zoom);

        // Add tile layer (CartoDB Positron for clean look)
        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            maxZoom: 19,
        }).addTo(map);

        // Create layer groups
        districtsLayerRef.current = L.layerGroup().addTo(map);  // Bottom layer
        voronoiLayerRef.current = L.layerGroup().addTo(map);    // Middle layer
        markersLayerRef.current = L.layerGroup().addTo(map);    // Top layer

        // Map click handler
        if (onMapClick) {
            map.on('click', (e) => {
                onMapClick(e.latlng.lat, e.latlng.lng);
            });
        }

        mapRef.current = map;

        return () => {
            map.remove();
            mapRef.current = null;
        };
    }, []);

    // Update facilities markers
    useEffect(() => {
        if (!markersLayerRef.current) return;

        markersLayerRef.current.clearLayers();

        facilities.forEach((facility) => {
            const marker = L.circleMarker([facility.lat, facility.lng], {
                radius: 6,
                fillColor: '#e74c3c',
                color: '#c0392b',
                weight: 2,
                opacity: 1,
                fillOpacity: 0.8,
            });

            marker.bindPopup(`
        <div class="p-2">
          <strong>${facility.name}</strong>
          ${facility.type ? `<br><span class="text-gray-600">${facility.type}</span>` : ''}
          ${facility.state ? `<br><span class="text-gray-500">${facility.state}</span>` : ''}
        </div>
      `);

            marker.addTo(markersLayerRef.current!);
        });
    }, [facilities]);

    // Update Voronoi layer
    useEffect(() => {
        if (!voronoiLayerRef.current) return;

        voronoiLayerRef.current.clearLayers();

        if (voronoiData && voronoiData.features) {
            voronoiData.features.forEach((feature, index) => {
                if (feature.geometry && feature.geometry.type === 'Polygon') {
                    const coords = (feature.geometry.coordinates[0] as number[][]).map(
                        (coord) => [coord[1], coord[0]] as [number, number]
                    );

                    const props = feature.properties;
                    const hasPop = props.population !== undefined;

                    const polygon = L.polygon(coords, {
                        color: '#2c3e50',
                        weight: 1,
                        // Use population color if available, otherwise random
                        fillColor: hasPop ? getPopulationColor(props.population as number) : getRandomColor(index),
                        fillOpacity: 0.5,
                    });

                    let popupContent = `
                        <div class="p-2 min-w-[200px]">
                            <h3 class="font-bold text-lg mb-1">${props.name || 'Unknown'}</h3>
                            <div class="text-sm space-y-1">
                                ${props.type ? `<div class="text-gray-600">Type: ${props.type}</div>` : ''}
                                ${props.area_sq_km ? `<div>Area: <span class="font-medium">${(props.area_sq_km as number).toLocaleString(undefined, { maximumFractionDigits: 0 })} km²</span></div>` : ''}
                                
                                ${hasPop ? `
                                    <div class="mt-3 pt-2 border-t border-gray-200">
                                        <div class="font-semibold text-blue-600">Total Population: ${(props.population as number).toLocaleString()}</div>
                                        <div class="text-xs text-gray-500 mt-1">Top Districts:</div>
                                        <ul class="list-disc list-inside pl-1 text-xs text-gray-700 mt-1">
                                            ${(props.population_breakdown as any[] || []).map(b =>
                        `<li>${b.district}: ${b.contributed_population.toLocaleString()}</li>`
                    ).join('')}
                                        </ul>
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                    `;

                    polygon.bindPopup(popupContent);
                    polygon.addTo(voronoiLayerRef.current!);
                }
            });
        }
    }, [voronoiData]);

    // Update Districts layer
    useEffect(() => {
        if (!districtsLayerRef.current) return;

        districtsLayerRef.current.clearLayers();

        if (showDistricts && districtData && districtData.features) {
            districtData.features.forEach((feature) => {
                if (feature.geometry && (feature.geometry.type === 'Polygon' || feature.geometry.type === 'MultiPolygon')) {
                    // Create GeoJSON layer for simplicity in handling MultiPolygons
                    L.geoJSON(feature as any, {
                        style: {
                            color: '#666',
                            weight: 1,
                            fillOpacity: 0, // Transparent fill, just borders
                            dashArray: '3'
                        }
                    }).addTo(districtsLayerRef.current!);
                }
            });
        }
    }, [showDistricts, districtData]);

    // Update map center/zoom
    useEffect(() => {
        if (mapRef.current) {
            mapRef.current.setView(center, zoom);
        }
    }, [center, zoom]);

    // Handle flyTo navigation
    useEffect(() => {
        if (mapRef.current && flyTo) {
            mapRef.current.flyTo([flyTo.lat, flyTo.lng], flyTo.zoom, {
                duration: 1,
            });
        }
    }, [flyTo]);

    return (
        <div
            ref={mapContainerRef}
            className="w-full h-full min-h-[500px] rounded-lg overflow-hidden shadow-lg"
        />
    );
}
