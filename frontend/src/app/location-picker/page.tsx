"use client";

import React, { use, Suspense } from "react";
import dynamic from "next/dynamic";

const LocationPickerMap = dynamic(() => import("@/components/LocationPickerMap"), {
  ssr: false,
  loading: () => (
    <div className="flex flex-col items-center justify-center min-h-screen bg-slate-950 text-white text-center">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500 mb-3"></div>
      <p className="text-xs text-slate-500">Memuat peta...</p>
    </div>
  ),
});

interface SearchParams {
  session_id?: string;
}

interface PageProps {
  searchParams: Promise<SearchParams>;
}

// Inner component that handles readingSearchParams
function LocationPickerContent({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = use(searchParams);
  const sessionId = params.session_id;

  if (!sessionId) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-slate-950 text-white p-6 text-center">
        <div className="bg-red-500/10 p-4 rounded-full mb-4 text-red-500">
          <svg className="h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <h1 className="text-lg font-bold mb-2">Tautan Tidak Valid</h1>
        <p className="text-sm text-slate-400 max-w-sm">
          Sesi obrolan tidak terdeteksi. Silakan buka kembali tautan dari chat WhatsApp/Telegram resmi Kantor SAR Natuna.
        </p>
      </div>
    );
  }

  return <LocationPickerMap sessionId={sessionId} />;
}

export default function LocationPickerPage({ searchParams }: PageProps) {
  return (
    <Suspense
      fallback={
        <div className="flex flex-col items-center justify-center min-h-screen bg-slate-950 text-white text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500 mb-3"></div>
          <p className="text-xs text-slate-500">Memuat modul peta...</p>
        </div>
      }
    >
      <LocationPickerContent searchParams={searchParams} />
    </Suspense>
  );
}
