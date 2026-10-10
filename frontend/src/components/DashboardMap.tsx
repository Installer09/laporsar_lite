'use client';

import dynamic from 'next/dynamic';
import { Loader2, Navigation } from 'lucide-react';

interface DashboardMapProps {
  reports?: any[];
  locations?: any[];
  kmlPath?: string;
  isPublic?: boolean;
}

// Dynamically import DashboardMapInner with SSR disabled
const DashboardMapInner = dynamic(() => import('./DashboardMapInner'), {
  ssr: false,
  loading: () => (
    <div className="h-full w-full bg-gray-50 flex flex-col items-center justify-center gap-3">
      <Loader2 className="w-8 h-8 animate-spin text-slate-500" />
      <p className="text-sm font-medium text-gray-400 animate-pulse">Memuat Peta Pemantauan SAR...</p>
    </div>
  ),
});

export default function DashboardMap(props: DashboardMapProps) {
  return (
    <div className="h-full w-full rounded-2xl overflow-hidden border border-gray-100 shadow-sm relative">
      {/* Decorative Absolute Header Accent */}
      <div className="absolute top-4 left-4 z-10 bg-white/90 backdrop-blur-md px-3.5 py-2 rounded-2xl shadow-md border border-gray-100/50 flex items-center gap-2">
        <div className="w-2.5 h-2.5 bg-red-500 rounded-full animate-pulse" />
        <span className="text-[11px] font-extrabold text-gray-800 uppercase tracking-wider flex items-center gap-1">
          <Navigation className="w-3.5 h-3.5 text-slate-500 animate-spin" /> Live Incident Map
        </span>
      </div>

      <DashboardMapInner {...props} />
    </div>
  );
}
