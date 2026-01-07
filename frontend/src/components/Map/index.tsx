'use client';

import dynamic from 'next/dynamic';
import type { ComponentProps } from 'react';

// Dynamic import to prevent SSR issues with Leaflet
const MapComponent = dynamic(
    () => import('./MapComponent'),
    {
        ssr: false,
        loading: () => (
            <div className="w-full h-full min-h-[500px] rounded-lg bg-gray-100 flex items-center justify-center">
                <div className="text-gray-500">Loading map...</div>
            </div>
        ),
    }
);

export default MapComponent;
export type MapProps = ComponentProps<typeof MapComponent>;
