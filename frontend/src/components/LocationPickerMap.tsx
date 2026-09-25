"use client";

import React, { useState, useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import axios from "axios";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Fix Leaflet marker icon path resolution in Next.js
if (typeof window !== "undefined") {
  delete (L.Icon.Default.prototype as any)._getIconUrl;
  L.Icon.Default.mergeOptions({
    iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
    iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
    shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  });
}

// Dynamically import Leaflet components to prevent SSR errors
const MapContainer = dynamic(
  () => import("react-leaflet").then((mod) => mod.MapContainer),
  { ssr: false }
);
const TileLayer = dynamic(
  () => import("react-leaflet").then((mod) => mod.TileLayer),
  { ssr: false }
);
const Marker = dynamic(
  () => import("react-leaflet").then((mod) => mod.Marker),
  { ssr: false }
);
const useMapEvents = (dynamic as any)(
  () => import("react-leaflet").then((mod) => mod.useMapEvents),
  { ssr: false }
);

interface LocationPickerMapProps {
  sessionId: string;
}

export default function LocationPickerMap({ sessionId }: LocationPickerMapProps) {
  const [position, setPosition] = useState<[number, number] | null>(null);
  const [center, setCenter] = useState<[number, number]>([3.95, 108.35]); // Default Natuna
  const [zoom, setZoom] = useState(13);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<"idle" | "success" | "error">("idle");
  const [address, setAddress] = useState("");
  const [detecting, setDetecting] = useState(false);
  
  const mapRef = useRef<any>(null);

  // 1. Fetch existing coordinates from ChatSession or use browser Geolocation
  useEffect(() => {
    async function loadSessionCoords() {
      try {
        const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const response = await axios.get(`${backendUrl}/api/public/webview-session/${sessionId}`);
        const data = response.data;
        
        if (data.koordinat_lat !== null && data.koordinat_lng !== null) {
          const lat = parseFloat(data.koordinat_lat);
          const lng = parseFloat(data.koordinat_lng);
          setPosition([lat, lng]);
          setCenter([lat, lng]);
          if (data.lokasi_teks) {
            setAddress(data.lokasi_teks);
          }
          setLoading(false);
        } else {
          // No coords stored -> trigger browser GPS geolocation detection
          detectCurrentLocation();
        }
      } catch (err) {
        console.error("Failed to load session coords, falling back to GPS", err);
        detectCurrentLocation();
      }
    }
    
    if (sessionId) {
      loadSessionCoords();
    }
  }, [sessionId]);

  const detectCurrentLocation = () => {
    if (typeof window === "undefined" || !navigator.geolocation) {
      setLoading(false);
      return;
    }

    setDetecting(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        setPosition([lat, lng]);
        setCenter([lat, lng]);
        setDetecting(false);
        setLoading(false);
        reverseGeocode(lat, lng);
      },
      (err) => {
        console.warn("Geolocation permission denied or error:", err);
        // Keep default Natuna coords
        setPosition([3.95, 108.35]);
        setDetecting(false);
        setLoading(false);
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  // Reverse geocode to get clean address name from OSM Nominatim
  const reverseGeocode = async (lat: number, lng: number) => {
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lng}`,
        { headers: { "Accept-Language": "id" } }
      );
      const data = await res.json();
      if (data && data.display_name) {
        // Get simple name (first 3 parts of address for concise display)
        const parts = data.display_name.split(",");
        const shortName = parts.slice(0, 3).join(",").trim();
        setAddress(shortName);
      }
    } catch (e) {
      console.warn("Reverse geocoding failed:", e);
    }
  };

  // Handle map clicks to position the marker
  function MapClickHandler() {
    useMapEvents({
      click(e: any) {
        const lat = e.latlng.lat;
        const lng = e.latlng.lng;
        setPosition([lat, lng]);
        reverseGeocode(lat, lng);
      },
    });
    return null;
  }

  // Handle submitting coordinates to the backend
  const handleSubmit = async () => {
    if (!position) return;
    
    setSaving(true);
    setStatus("idle");
    try {
      const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      await axios.post(`${backendUrl}/api/public/webview-session/${sessionId}/location`, {
        koordinat_lat: position[0],
        koordinat_lng: position[1],
        lokasi_teks: address || `Koordinat ${position[0].toFixed(5)}, ${position[1].toFixed(5)}`
      });
      setStatus("success");
    } catch (err) {
      console.error("Failed to submit location", err);
      setStatus("error");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] text-slate-400">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-500 mb-4"></div>
        <p className="text-sm font-medium">Mendeteksi GPS Anda...</p>
      </div>
    );
  }

  if (status === "success") {
    return (
      <div className="flex flex-col items-center justify-center p-8 bg-slate-900 border border-emerald-500/30 rounded-2xl shadow-xl text-center max-w-md mx-auto my-12 animate-in fade-in zoom-in-95 duration-200">
        <div className="bg-emerald-500/10 p-4 rounded-full mb-4">
          <svg className="h-12 w-12 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h2 className="text-xl font-bold text-white mb-2">Lokasi Terkirim!</h2>
        <p className="text-slate-400 text-sm mb-6 leading-relaxed">
          Koordinat lokasi kejadian berhasil disimpan. Silakan tutup halaman ini dan kembali ke WhatsApp/Telegram untuk melanjutkan laporan.
        </p>
        <button
          onClick={() => {
            if (typeof window !== "undefined") {
              window.close();
            }
          }}
          className="w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl font-semibold shadow-md transition-colors"
        >
          Selesai & Kembali
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen max-h-screen bg-slate-950 text-white select-none">
      {/* Top Banner */}
      <div className="p-4 bg-slate-900 border-b border-slate-800 flex items-center justify-between shrink-0">
        <div>
          <h1 className="text-base font-bold flex items-center gap-2 text-orange-400">
            <span className="h-2 w-2 rounded-full bg-red-500"></span>
            PETA LOKASI LAPOR SAR
          </h1>
          <p className="text-[11px] text-slate-400">
            Ketuk/geser peta untuk menentukan posisi kejadian musibah
          </p>
        </div>
        <button 
          onClick={detectCurrentLocation}
          disabled={detecting}
          className="p-2 bg-slate-800 hover:bg-slate-700 active:scale-95 rounded-lg border border-slate-700 transition-all text-orange-400 text-xs flex items-center gap-1.5"
        >
          {detecting ? (
            <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-orange-400 border-t-transparent"></div>
          ) : (
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          )}
          GPS Saya
        </button>
      </div>

      {/* Map Container */}
      <div className="grow relative overflow-hidden">
        {position && (
          <MapContainer
            center={center}
            zoom={zoom}
            className="h-full w-full"
            ref={mapRef}
            zoomControl={false}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <MapClickHandler />
            <Marker 
              position={position} 
              draggable={true}
              eventHandlers={{
                dragend: (e) => {
                  const marker = e.target;
                  const coords = marker.getLatLng();
                  setPosition([coords.lat, coords.lng]);
                  reverseGeocode(coords.lat, coords.lng);
                }
              }}
            />
          </MapContainer>
        )}
      </div>

      {/* Bottom Panel */}
      <div className="p-4 bg-slate-900 border-t border-slate-800 shrink-0 flex flex-col gap-3">
        {/* Selected Coordinates Card */}
        <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl">
          <div className="flex items-start gap-2.5">
            <svg className="h-5 w-5 text-orange-400 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <div className="grow min-w-0">
              <p className="text-[10px] uppercase tracking-wider text-slate-500 font-bold">Lokasi Terpilih</p>
              <textarea
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder="Memuat nama alamat..."
                rows={1}
                className="w-full bg-transparent text-sm font-semibold text-white focus:outline-none resize-none border-b border-transparent focus:border-slate-800 py-0.5"
              />
              <p className="text-[11px] text-slate-400 font-mono mt-0.5">
                {position ? `${position[0].toFixed(6)}, ${position[1].toFixed(6)}` : "-"}
              </p>
            </div>
          </div>
        </div>

        {status === "error" && (
          <div className="p-3 bg-red-950/50 border border-red-500/20 text-red-400 text-xs rounded-xl flex items-center justify-center gap-2">
            <svg className="w-4 h-4 shrink-0 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span>Gagal mengirim lokasi. Silakan coba lagi.</span>
          </div>
        )}

        {/* Submit Button */}
        <button
          onClick={handleSubmit}
          disabled={saving || !position}
          className={`w-full py-3.5 rounded-xl font-bold flex items-center justify-center gap-2 shadow-lg transition-all active:scale-95 ${
            saving 
              ? "bg-slate-800 text-slate-400 cursor-not-allowed" 
              : "bg-orange-600 hover:bg-orange-700 text-white"
          }`}
        >
          {saving ? (
            <>
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-slate-400 border-t-transparent"></div>
              Mengirim Lokasi...
            </>
          ) : (
            <>
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
              </svg>
              Kirim Lokasi Kejadian
            </>
          )}
        </button>
      </div>
    </div>
  );
}
