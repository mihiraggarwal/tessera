"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { GeoJSONFeatureCollection, Facility } from "@/lib/api";

// Fix for default markers in Next.js
import icon from "leaflet/dist/images/marker-icon.png";
import iconShadow from "leaflet/dist/images/marker-shadow.png";

const DefaultIcon = L.icon({
  iconUrl: icon.src,
  shadowUrl: iconShadow.src,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

L.Marker.prototype.options.icon = DefaultIcon;

interface EnclosingCircle {
  center: [number, number]; // [lng, lat]
  radius_km: number;
}

interface MapProps {
  facilities?: Facility[];
  voronoiData?: GeoJSONFeatureCollection;
  districtData?: GeoJSONFeatureCollection;
  showDistricts?: boolean;
  center?: [number, number];
  zoom?: number;
  onMapClick?: (lat: number, lng: number) => void;
  onMapDoubleClick?: (lat: number, lng: number) => void;
  flyTo?: { lat: number; lng: number; zoom: number } | null;
  enclosingCircles?: {
    mec?: EnclosingCircle;
    largestEmpty?: EnclosingCircle;
  };
  showEnclosingCircles?: boolean;
  editMode?: "add" | "remove" | null;
  heatmapData?: Array<{ lat: number; lng: number; weight: number }>;
  heatmapType?: "emergency" | "living" | null;
}

// Population coloring (Yellow -> Red)
const getPopulationColor = (pop: number): string => {
  return pop > 10000000
    ? "#800026"
    : pop > 5000000
      ? "#BD0026"
      : pop > 2000000
        ? "#E31A1C"
        : pop > 1000000
          ? "#FC4E2A"
          : pop > 500000
            ? "#FD8D3C"
            : pop > 200000
              ? "#FEB24C"
              : pop > 100000
                ? "#FED976"
                : "#FFEDA0";
};

// Random color generator for Voronoi cells
const getRandomColor = (seed: number): string => {
  const colors = [
    "#FF6B6B",
    "#4ECDC4",
    "#45B7D1",
    "#96CEB4",
    "#FFEAA7",
    "#DDA0DD",
    "#98D8C8",
    "#F7DC6F",
    "#BB8FCE",
    "#85C1E9",
    "#F8B500",
    "#00CED1",
    "#FF69B4",
    "#32CD32",
    "#FFD700",
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
  onMapDoubleClick,
  flyTo,
  enclosingCircles,
  showEnclosingCircles = false,
  editMode = null,
  heatmapData = [],
  heatmapType = null,
}: MapProps) {
  const mapRef = useRef<L.Map | null>(null);
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const voronoiLayerRef = useRef<L.LayerGroup | null>(null);
  const districtsLayerRef = useRef<L.LayerGroup | null>(null);
  const enclosingCirclesLayerRef = useRef<L.LayerGroup | null>(null);
  const heatmapLayerRef = useRef<any>(null);

  // Initialize map
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const map = L.map(mapContainerRef.current).setView(center, zoom);

    // Add tile layer (CartoDB Positron for clean look)
    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
      {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        maxZoom: 19,
      },
    ).addTo(map);

    // Create layer groups
    districtsLayerRef.current = L.layerGroup().addTo(map); // Bottom layer
    voronoiLayerRef.current = L.layerGroup().addTo(map); // Middle layer
    markersLayerRef.current = L.layerGroup().addTo(map); // Facility markers
    enclosingCirclesLayerRef.current = L.layerGroup().addTo(map); // Top layer for circles

    // Heatmap layer
    heatmapLayerRef.current = L.layerGroup().addTo(map);

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
        fillColor: "#e74c3c",
        color: "#c0392b",
        weight: 2,
        opacity: 1,
        fillOpacity: 0.8,
        interactive: editMode !== "remove" && editMode !== "add", // Let map handle clicks in edit mode
      });

      if (editMode !== "remove" && editMode !== "add") {
        marker.bindPopup(`
                    <div class="p-2">
                        <strong>${facility.name}</strong>
                        ${facility.type ? `<br><span class="text-gray-600">${facility.type}</span>` : ""}
                        ${facility.state ? `<br><span class="text-gray-500">${facility.state}</span>` : ""}
                    </div>
                `);
      }

      marker.addTo(markersLayerRef.current!);
    });
  }, [facilities, editMode]);

  // Update Voronoi layer
  useEffect(() => {
    if (!voronoiLayerRef.current) return;

    voronoiLayerRef.current.clearLayers();

    if (voronoiData && voronoiData.features) {
      voronoiData.features.forEach((feature, index) => {
        if (feature.geometry && feature.geometry.type === "Polygon") {
          const coords = (feature.geometry.coordinates[0] as number[][]).map(
            (coord) => [coord[1], coord[0]] as [number, number],
          );

          const props = feature.properties;
          const hasPop = props.population !== undefined;

          const polygon = L.polygon(coords, {
            color: "#2c3e50",
            weight: 1,
            // Use population color if available, otherwise random
            fillColor: hasPop
              ? getPopulationColor(props.population as number)
              : getRandomColor(index),
            fillOpacity: 0.5,
            interactive: editMode !== "remove" && editMode !== "add", // Let map handle clicks
          });

          let popupContent = `
                        <div class="p-2 min-w-[200px]">
                            <h3 class="font-bold text-lg mb-1">${props.name || "Unknown"}</h3>
                            <div class="text-sm space-y-1">
                                ${props.type ? `<div class="text-gray-600">Type: ${props.type}</div>` : ""}
                                ${props.area_sq_km ? `<div>Area: <span class="font-medium">${(props.area_sq_km as number).toLocaleString(undefined, { maximumFractionDigits: 0 })} km²</span></div>` : ""}
                                
                                ${
                                  hasPop
                                    ? `
                                    <div class="mt-3 pt-2 border-t border-gray-200">
                                        <div class="font-semibold text-blue-600">Total Population: ${(props.population as number).toLocaleString()}</div>
                                        <div class="text-xs text-gray-500 mt-1">Top Districts:</div>
                                        <ul class="list-disc list-inside pl-1 text-xs text-gray-700 mt-1">
                                            ${(
                                              (props.population_breakdown as any[]) ||
                                              []
                                            )
                                              .map(
                                                (b) =>
                                                  `<li>${b.district}: ${b.contributed_population.toLocaleString()}</li>`,
                                              )
                                              .join("")}
                                        </ul>
                                    </div>
                                `
                                    : ""
                                }
                            </div>
                        </div>
                    `;

          if (editMode !== "remove" && editMode !== "add") {
            polygon.bindPopup(popupContent);
          }
          polygon.addTo(voronoiLayerRef.current!);
        }
      });
    }
  }, [voronoiData, editMode]);

  // Update Districts layer
  useEffect(() => {
    if (!districtsLayerRef.current) return;

    districtsLayerRef.current.clearLayers();

    if (showDistricts && districtData && districtData.features) {
      districtData.features.forEach((feature) => {
        if (
          feature.geometry &&
          (feature.geometry.type === "Polygon" ||
            feature.geometry.type === "MultiPolygon")
        ) {
          // Create GeoJSON layer for simplicity in handling MultiPolygons
          L.geoJSON(feature as any, {
            style: {
              color: "#666",
              weight: 1,
              fillOpacity: 0, // Transparent fill, just borders
              dashArray: "3",
            },
          }).addTo(districtsLayerRef.current!);
        }
      });
    }
  }, [showDistricts, districtData, editMode]);

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

  // Update enclosing circles layer
  useEffect(() => {
    if (!enclosingCirclesLayerRef.current) return;

    enclosingCirclesLayerRef.current.clearLayers();

    if (showEnclosingCircles && enclosingCircles) {
      // Minimum Enclosing Circle (MEC) - blue dashed
      if (enclosingCircles.mec?.center && enclosingCircles.mec.radius_km > 0) {
        const [lng, lat] = enclosingCircles.mec.center;
        const radiusMeters = enclosingCircles.mec.radius_km * 1000;

        const mecCircle = L.circle([lat, lng], {
          radius: radiusMeters,
          color: "#3B82F6",
          weight: 4,
          fillOpacity: 0.1,
          dashArray: "10, 10",
        });
        mecCircle.bindPopup(`
                    <div class="p-2">
                        <strong>Minimum Enclosing Circle</strong><br>
                        <span class="text-gray-600">Radius: ${enclosingCircles.mec.radius_km.toFixed(1)} km</span><br>
                        <span class="text-xs text-gray-500">Smallest circle covering all facilities</span>
                    </div>
                `);
        mecCircle.addTo(enclosingCirclesLayerRef.current);
      }

      // Largest Empty Circle - orange dashed
      if (
        enclosingCircles.largestEmpty?.center &&
        enclosingCircles.largestEmpty.radius_km > 0
      ) {
        const [lng, lat] = enclosingCircles.largestEmpty.center;
        const radiusMeters = enclosingCircles.largestEmpty.radius_km * 1000;

        const emptyCircle = L.circle([lat, lng], {
          radius: radiusMeters,
          color: "#EF4444", // Red for underserved
          weight: 5,
          fillOpacity: 0.2,
          fillColor: "#FEE2E2",
          dashArray: "5, 5",
        });
        emptyCircle.bindPopup(`
                    <div class="p-2">
                        <strong>Largest Underserved Area</strong><br>
                        <span class="text-gray-600">Radius: ${enclosingCircles.largestEmpty.radius_km.toFixed(1)} km</span><br>
                        <span class="text-xs text-gray-500">Largest area without a facility</span>
                    </div>
                `);
        emptyCircle.addTo(enclosingCirclesLayerRef.current);

        // Add marker at center of empty circle
        const centerMarker = L.circleMarker([lat, lng], {
          radius: 10,
          fillColor: "#EF4444",
          color: "#B91C1C",
          weight: 3,
          opacity: 1,
          fillOpacity: 0.9,
        });
        centerMarker.bindPopup("Suggested location for new facility");
        centerMarker.addTo(enclosingCirclesLayerRef.current);
      }
    }
  }, [showEnclosingCircles, enclosingCircles]);

  // Update heatmap layer
  useEffect(() => {
    if (!heatmapLayerRef.current) return;

    heatmapLayerRef.current.clearLayers();

    if (heatmapData && heatmapData.length > 0) {
      heatmapData.forEach((point) => {
        let color = "#FED976";
        let opacityWeight = point.weight;

        if (heatmapType === "emergency") {
          const risk = 1.0 - point.weight;
          opacityWeight = point.weight;
          color =
            risk > 0.8
              ? "#800026"
              : risk > 0.6
                ? "#BD0026"
                : risk > 0.4
                  ? "#E31A1C"
                  : risk > 0.2
                    ? "#FC4E2A"
                    : "#FED976";
        } else if (heatmapType === "living") {
          opacityWeight = point.weight;
          color =
            point.weight > 0.8
              ? "#006837"
              : point.weight > 0.6
                ? "#31a354"
                : point.weight > 0.4
                  ? "#78c679"
                  : point.weight > 0.2
                    ? "#c2e699"
                    : "#ffffcc";
        }

        const circle = L.circleMarker([point.lat, point.lng], {
          radius: 5,
          fillColor: color,
          color: color,
          weight: 1,
          opacity: 0.2,
          fillOpacity: 0.2 + opacityWeight * 0.6,
          interactive: false,
        });
        circle.addTo(heatmapLayerRef.current!);
      });
    }
  }, [heatmapData, heatmapType]);

  // Update cursor style based on edit mode
  useEffect(() => {
    if (mapContainerRef.current) {
      if (editMode === "add") {
        mapContainerRef.current.style.cursor = "crosshair";
      } else if (editMode === "remove") {
        mapContainerRef.current.style.cursor = "pointer";
      } else {
        mapContainerRef.current.style.cursor = "";
      }
    }
  }, [editMode]);

  // Update map click listener
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const onClick = (e: L.LeafletMouseEvent) => {
      if (onMapClick) {
        onMapClick(e.latlng.lat, e.latlng.lng);
      }
    };

    const onDblClick = (e: L.LeafletMouseEvent) => {
      if (onMapDoubleClick) {
        onMapDoubleClick(e.latlng.lat, e.latlng.lng);
      }
    };

    map.on("click", onClick);
    map.on("dblclick", onDblClick);
    return () => {
      map.off("click", onClick);
      map.off("dblclick", onDblClick);
    };
  }, [onMapClick, onMapDoubleClick]);

  return (
    <div
      ref={mapContainerRef}
      className="w-full h-full min-h-[500px] rounded-lg overflow-hidden shadow-lg"
    />
  );
}
