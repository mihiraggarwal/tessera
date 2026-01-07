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
    center?: [number, number];
    zoom?: number;
    onMapClick?: (lat: number, lng: number) => void;
}

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
    center = [20.5937, 78.9629], // Center of India
    zoom = 5,
    onMapClick,
}: MapProps) {
    const mapRef = useRef<L.Map | null>(null);
    const mapContainerRef = useRef<HTMLDivElement>(null);
    const markersLayerRef = useRef<L.LayerGroup | null>(null);
    const voronoiLayerRef = useRef<L.LayerGroup | null>(null);

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
        markersLayerRef.current = L.layerGroup().addTo(map);
        voronoiLayerRef.current = L.layerGroup().addTo(map);

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

                    const polygon = L.polygon(coords, {
                        color: '#2c3e50',
                        weight: 1,
                        fillColor: getRandomColor(index),
                        fillOpacity: 0.3,
                    });

                    const props = feature.properties;
                    polygon.bindPopup(`
            <div class="p-2">
              <strong>${props.name || 'Unknown'}</strong>
              ${props.type ? `<br><span class="text-gray-600">Type: ${props.type}</span>` : ''}
              ${props.area_sq_km ? `<br><span class="text-gray-500">Area: ${(props.area_sq_km as number).toFixed(1)} km²</span>` : ''}
            </div>
          `);

                    polygon.addTo(voronoiLayerRef.current!);
                }
            });
        }
    }, [voronoiData]);

    // Update map center/zoom
    useEffect(() => {
        if (mapRef.current) {
            mapRef.current.setView(center, zoom);
        }
    }, [center, zoom]);

    return (
        <div
            ref={mapContainerRef}
            className="w-full h-full min-h-[500px] rounded-lg overflow-hidden shadow-lg"
        />
    );
}
