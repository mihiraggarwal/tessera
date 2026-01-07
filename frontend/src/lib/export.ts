import html2canvas from 'html2canvas';
import type { GeoJSONFeatureCollection } from './api';

/**
 * Export the map container as a PNG image
 */
export async function exportToPNG(elementId: string, filename: string = 'tessera-map.png'): Promise<void> {
    const element = document.getElementById(elementId);
    if (!element) {
        throw new Error(`Element with id "${elementId}" not found`);
    }

    try {
        const canvas = await html2canvas(element, {
            useCORS: true,
            allowTaint: true,
            backgroundColor: '#ffffff',
            scale: 2, // Higher resolution
        });

        // Convert to blob and download
        canvas.toBlob((blob) => {
            if (blob) {
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = filename;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(url);
            }
        }, 'image/png');
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
