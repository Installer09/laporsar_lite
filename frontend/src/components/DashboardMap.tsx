'use client';

import React, { Component, ErrorInfo, ReactNode } from 'react';
import dynamic from 'next/dynamic';
import { Loader2, Navigation, AlertCircle } from 'lucide-react';

interface DashboardMapProps {
  reports?: any[];
  locations?: any[];
  kmlPath?: string;
  isPublic?: boolean;
}

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

class MapErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(_: Error): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.warn('DashboardMap error caught by boundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="h-full w-full bg-slate-100 flex flex-col items-center justify-center p-6 text-center">
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-2xl text-amber-600 mb-2">
            <AlertCircle className="w-6 h-6" />
          </div>
          <p className="text-xs font-bold text-slate-700">Peta Pemantauan Sementara Tidak Tersedia</p>
          <p className="text-[11px] text-slate-500 mt-1 max-w-xs">Gunakan daftar laporan aktif atau hubungi call center 115.</p>
        </div>
      );
    }
    return this.props.children;
  }
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
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <div className="h-full w-full rounded-2xl overflow-hidden border border-gray-100 shadow-sm relative">
      {/* Decorative Absolute Header Accent */}
      <div className="absolute top-4 left-4 z-10 bg-white/90 backdrop-blur-md px-3.5 py-2 rounded-2xl shadow-md border border-gray-100/50 flex items-center gap-2 pointer-events-none">
        <div className="w-2.5 h-2.5 bg-red-500 rounded-full animate-pulse" />
        <span className="text-[11px] font-extrabold text-gray-800 uppercase tracking-wider flex items-center gap-1">
          <Navigation className="w-3.5 h-3.5 text-slate-500 animate-spin" /> Live Incident Map
        </span>
      </div>

      <MapErrorBoundary>
        {mounted ? (
          <DashboardMapInner {...props} />
        ) : (
          <div className="h-full w-full bg-gray-50 flex flex-col items-center justify-center gap-3">
            <Loader2 className="w-8 h-8 animate-spin text-slate-500" />
            <p className="text-sm font-medium text-gray-400 animate-pulse">Menyiapkan Peta Pemantauan SAR...</p>
          </div>
        )}
      </MapErrorBoundary>
    </div>
  );
}
