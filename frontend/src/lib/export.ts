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
        console.log(`Starting PNG export for element: ${elementId}`);

        const canvas = await html2canvas(element, {
            useCORS: true,
            allowTaint: false, // Don't allow tainted canvas, use CORS for tiles
            backgroundColor: '#ffffff',
            scale: 2, // Higher resolution
            logging: true, // Enable logging for debugging in console
        });

        console.log('Canvas generated, converting to blob...');

        // Convert to blob and download - wrapped in promise for reliability
        return new Promise((resolve, reject) => {
            canvas.toBlob((blob) => {
                try {
                    if (blob) {
                        const url = URL.createObjectURL(blob);
                        const link = document.createElement('a');
                        link.href = url;
                        link.download = filename;
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                        URL.revokeObjectURL(url);
                        console.log('PNG export successful');
                        resolve();
                    } else {
                        reject(new Error('Canvas toBlob failed - returned null'));
                    }
                } catch (e) {
                    reject(e);
                }
            }, 'image/png', 1.0);
        });
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
