'use client';

import { useState, useEffect } from 'react';
import { Polygon, Circle, Popup, Marker } from 'react-leaflet';
import L from 'leaflet';
import { Flame, AlertTriangle, Users, Calendar, ShieldAlert } from 'lucide-react';
import { getBackendUrl } from '@/lib/api';

interface HotspotFeature {
  type: string;
  id: string;
  geometry: {
    type: string;
    coordinates: any;
  };
  properties: {
    cluster_id: number;
    centroid: [number, number];
    total_incidents: number;
    total_korban: number;
    total_meninggal: number;
    total_hilang: number;
    total_selamat: number;
    risk_score: number;
    risk_level: string;
    risk_label: string;
    color: string;
    incidents: Array<{
      id: number;
      no_laporan: string;
      jenis_kejadian: string;
      lat: number;
      lng: number;
      created_at: string;
    }>;
    radius_km: number;
  };
}

interface HotspotMapLayerProps {
  epsKm?: number;
  minSamples?: number;
  showToggle?: boolean;
}

export default function HotspotMapLayer({ epsKm = 5.0, minSamples = 2 }: HotspotMapLayerProps) {
  const [hotspots, setHotspots] = useState<HotspotFeature[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchHotspots = async () => {
      setLoading(true);
      try {
        const backendUrl = getBackendUrl();
        const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
        const headers: Record<string, string> = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const res = await fetch(`${backendUrl}/api/hotspots?eps_km=${epsKm}&min_samples=${minSamples}`, { headers });
        if (res.ok) {
          const data = await res.json();
          setHotspots(data.features || []);
        }
      } catch (err) {
        console.warn('Gagal memuat data hotspot spasial:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchHotspots();
  }, [epsKm, minSamples]);

  if (loading || hotspots.length === 0) return null;

  return (
    <>
      {hotspots.map((feature) => {
        const props = feature.properties;
        const [lat, lng] = props.centroid;
        const color = props.color || '#EF4444';

        // Polygon coordinates conversion if geometry is Polygon
        let polygonPositions: [number, number][] = [];
        if (feature.geometry && feature.geometry.type === 'Polygon') {
          polygonPositions = feature.geometry.coordinates[0].map((coord: [number, number]) => [coord[1], coord[0]]);
        }

        const hotspotMarkerIcon = L.divIcon({
          className: 'hotspot-pulse-icon',
          html: `
            <div class="relative flex items-center justify-center">
              <span class="animate-ping absolute inline-flex h-8 w-8 rounded-full" style="background-color: ${color}; opacity: 0.6;"></span>
              <div class="relative w-7 h-7 rounded-full flex items-center justify-center text-white shadow-lg font-black text-[10px] border-2 border-white" style="background-color: ${color};">
                🔥
              </div>
            </div>
          `,
          iconSize: [28, 28],
          iconAnchor: [14, 14],
        });

        return (
          <div key={feature.id}>
            {/* Render Convex Hull Polygon if available */}
            {polygonPositions.length > 0 ? (
              <Polygon
                positions={polygonPositions}
                pathOptions={{
                  color: color,
                  fillColor: color,
                  fillOpacity: 0.25,
                  weight: 3,
                  dashArray: '4, 4'
                }}
              />
            ) : (
              /* Render Circle Buffer fallback */
              <Circle
                center={[lat, lng]}
                radius={(props.radius_km || 5.0) * 1000}
                pathOptions={{
                  color: color,
                  fillColor: color,
                  fillOpacity: 0.2,
                  weight: 2,
                  dashArray: '6, 6'
                }}
              />
            )}

            {/* Hotspot Center Marker & Detail Popup */}
            <Marker position={[lat, lng]} icon={hotspotMarkerIcon}>
              <Popup className="premium-leaflet-popup">
                <div className="p-3 space-y-3 min-w-[260px] text-gray-800 text-xs">
                  {/* Header Badge */}
                  <div className="flex items-center justify-between border-b border-gray-100 pb-2">
                    <span
                      className="font-black text-[10px] px-2 py-0.5 rounded-lg text-white flex items-center gap-1 uppercase tracking-wider shadow-sm"
                      style={{ backgroundColor: color }}
                    >
                      <ShieldAlert className="w-3 h-3" />
                      {props.risk_level} RISK (SKOR: {props.risk_score})
                    </span>
                    <span className="text-[10px] font-bold text-gray-500 flex items-center gap-1">
                      <Flame className="w-3 h-3 text-slate-500" />
                      Hotspot #{props.cluster_id}
                    </span>
                  </div>

                  {/* Title */}
                  <div>
                    <h4 className="font-extrabold text-gray-900 text-sm">{props.risk_label}</h4>
                    <p className="text-[10px] text-gray-500 mt-0.5">
                      Kluster spasial ber-radius {props.radius_km} km dengan konsentrasi kejadian tinggi.
                    </p>
                  </div>

                  {/* Casualty Stats Grid */}
                  <div className="grid grid-cols-3 gap-1.5 p-2 bg-gray-50 rounded-xl border border-gray-100 text-center font-bold">
                    <div className="p-1 bg-white rounded-lg border border-gray-100">
                      <div className="text-[9px] text-gray-400">Total Kejadian</div>
                      <div className="text-xs text-blue-600 font-extrabold">{props.total_incidents}</div>
                    </div>
                    <div className="p-1 bg-white rounded-lg border border-gray-100">
                      <div className="text-[9px] text-gray-400">Meninggal</div>
                      <div className="text-xs text-red-600 font-extrabold">{props.total_meninggal}</div>
                    </div>
                    <div className="p-1 bg-white rounded-lg border border-gray-100">
                      <div className="text-[9px] text-gray-400">Hilang</div>
                      <div className="text-xs text-amber-600 font-extrabold">{props.total_hilang}</div>
                    </div>
                  </div>

                  {/* Incident list */}
                  <div className="space-y-1">
                    <div className="text-[10px] font-extrabold text-gray-700 uppercase tracking-wider">
                      Laporan Terkait ({props.incidents.length}):
                    </div>
                    <div className="max-h-24 overflow-y-auto divide-y divide-gray-100 text-[10px]">
                      {props.incidents.map((inc) => (
                        <div key={inc.id} className="py-1 flex items-center justify-between">
                          <span className="font-bold text-gray-800">{inc.no_laporan}</span>
                          <span className="text-gray-500 truncate max-w-[120px]">{inc.jenis_kejadian}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </Popup>
            </Marker>
          </div>
        );
      })}
    </>
  );
}
