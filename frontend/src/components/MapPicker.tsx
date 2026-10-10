'use client';

import dynamic from 'next/dynamic';
import { Loader2 } from 'lucide-react';

interface MapPickerProps {
  initialLat?: number;
  initialLng?: number;
  onChange: (lat: number, lng: number, address?: string) => void;
}

// Dynamically import MapPickerInner with ssr disabled
const MapPickerInner = dynamic(() => import('./MapPickerInner'), {
  ssr: false,
  loading: () => (
    <div className="h-[300px] w-full rounded-2xl bg-gray-50 border border-gray-100 flex flex-col items-center justify-center gap-3">
      <Loader2 className="w-8 h-8 animate-spin text-slate-500" />
      <p className="text-sm font-medium text-gray-400 animate-pulse">Memuat Peta Interaktif Leaflet...</p>
    </div>
  ),
});

export default function MapPicker(props: MapPickerProps) {
  return <MapPickerInner {...props} />;
}
