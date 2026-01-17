import type { GeoJSONFeatureCollection } from './api';
import { toPng } from 'html-to-image';

/**
 * Export the map container as a PNG image
 */
export async function exportToPNG2(elementId: string, filename: string = 'tessera-map.png'): Promise<void> {
    const element = document.getElementById(elementId);
    if (!element) {
        throw new Error(`Element with id "${elementId}" not found`);
    }

    try {
        console.log(`Starting PNG export for element: ${elementId}`);

        const dataUrl = await toPng(element, {
            cacheBust: true,
            pixelRatio: 1.5,
            backgroundColor: '#ffffff',
        });

        const link = document.createElement('a');
        link.href = dataUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        console.log('PNG export successful');
    } catch (error) {
        console.error('Failed to export PNG:', error);
        throw error;
    }
}

/**
 * Export GeoJSON data as a downloadable file
 */
export function exportToGeoJSON(
    data: GeoJSONFeatureCollection,
    filename: string = 'tessera-voronoi.geojson'
): void {
    const jsonString = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonString], { type: 'application/geo+json' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}
