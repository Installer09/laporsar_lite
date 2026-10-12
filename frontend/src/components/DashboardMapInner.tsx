'use client';

import { useState, useEffect, useRef, Fragment } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polygon, Circle, useMap } from 'react-leaflet';
import L from 'leaflet';
import { Shield, MapPin, AlertTriangle, Calendar, Users, Anchor, Navigation } from 'lucide-react';
import { getBackendUrl } from '@/lib/api';
import IncidentMarkerCluster from './MarkerClusterGroup';
import HotspotMapLayer from './HotspotMapLayer';


interface DashboardMapInnerProps {
  reports?: any[];
  locations?: any[];
  kmlPath?: string;
  isPublic?: boolean;
}

// Custom Pulse Marker Icon (Red/Amber based on status)
const createIncidentMarker = (jenisKejadian: string, status: string, zoom: number) => {
  if (typeof window === 'undefined') return null;
  
  // Determine size based on zoom
  let size = 32;
  let containerClass = "w-8 h-8";
  let pingClass = "h-8 w-8";
  let textClass = "text-[12px]";
  let borderClass = "border-2";
  
  if (zoom <= 4) {
    size = 8;
    containerClass = "w-2 h-2";
    pingClass = "h-2 w-2";
    textClass = "text-[0px]"; // Hide emoji
    borderClass = "border-[0.5px]";
  } else if (zoom <= 5) {
    size = 10;
    containerClass = "w-2.5 h-2.5";
    pingClass = "h-2.5 w-2.5";
    textClass = "text-[0px]"; // Hide emoji
    borderClass = "border";
  } else if (zoom <= 7) {
    size = 16;
    containerClass = "w-4 h-4";
    pingClass = "h-4 w-4";
    textClass = "text-[0px]"; // Hide emoji
    borderClass = "border";
  } else if (zoom <= 9) {
    size = 22;
    containerClass = "w-5.5 h-5.5";
    pingClass = "h-5.5 w-5.5";
    textClass = "text-[9px]";
    borderClass = "border-2";
  } else if (zoom <= 11) {
    size = 28;
    containerClass = "w-7 h-7";
    pingClass = "h-7 w-7";
    textClass = "text-[11px]";
    borderClass = "border-2";
  }
  
  const getCategorySvg = (jenis: string) => {
    const lower = (jenis || '').toLowerCase();
    if (lower.includes("kapal") || lower.includes("laut") || lower.includes("tenggelam")) {
      return `<svg class="w-full h-full text-white p-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="5" r="3"/><line x1="12" y1="22" x2="12" y2="8"/><path d="M5 12H2a10 10 0 0 0 20 0h-3"/></svg>`;
    }
    if (lower.includes("manusia") || lower.includes("hilang") || lower.includes("kmm")) {
      return `<svg class="w-full h-full text-white p-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
    }
    if (lower.includes("pesawat") || lower.includes("udara")) {
      return `<svg class="w-full h-full text-white p-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m2 12 5-3 3 3 8-8 4 4-8 8 3 3-3 5-4-8-5-1Z"/></svg>`;
    }
    if (lower.includes("bencana") || lower.includes("alam") || lower.includes("banjir")) {
      return `<svg class="w-full h-full text-white p-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`;
    }
    return `<svg class="w-full h-full text-white p-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`;
  };

  const iconSvg = getCategorySvg(jenisKejadian);

  // Determine colors based on status: PENDING is amber, AKTIF is pulsing red
  let pulseColor = "bg-red-400";
  let gradientColors = "from-red-600 to-rose-700";
  
  if (status === 'PENDING') {
    pulseColor = "bg-amber-400";
    gradientColors = "from-amber-600 to-amber-700";
  }

  return L.divIcon({
    className: 'incident-marker-icon',
    html: `
      <div class="relative flex items-center justify-center">
        <span class="animate-ping absolute inline-flex rounded-full ${pulseColor} opacity-75 ${pingClass}"></span>
        <div class="relative ${containerClass} bg-gradient-to-br ${gradientColors} ${borderClass} border-white rounded-full flex items-center justify-center shadow-lg transition-transform hover:scale-110 p-0.5">
          ${iconSvg}
        </div>
      </div>
    `,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
};

// Custom Premium Pulse Marker Icon for SAR Posts (Blue)
const createPosMarker = (type: string, customIcon: string | undefined, zoom: number) => {
  if (typeof window === 'undefined') return null;
  
  let size = 32;
  let containerClass = "w-8 h-8";
  let textClass = "text-[12px]";
  let imgClass = "w-6 h-6";
  let borderClass = "border-2";
  
  if (zoom <= 4) {
    size = 8;
    containerClass = "w-2 h-2";
    textClass = "text-[0px]";
    imgClass = "w-1.5 h-1.5";
    borderClass = "border-[0.5px]";
  } else if (zoom <= 5) {
    size = 10;
    containerClass = "w-2.5 h-2.5";
    textClass = "text-[0px]";
    imgClass = "w-2 h-2";
    borderClass = "border";
  } else if (zoom <= 7) {
    size = 16;
    containerClass = "w-4 h-4";
    textClass = "text-[0px]";
    imgClass = "w-3 h-3";
    borderClass = "border";
  } else if (zoom <= 9) {
    size = 22;
    containerClass = "w-5.5 h-5.5";
    textClass = "text-[9px]";
    imgClass = "w-[16px] h-[16px]";
    borderClass = "border-2";
  } else if (zoom <= 11) {
    size = 28;
    containerClass = "w-7 h-7";
    textClass = "text-[11px]";
    imgClass = "w-[20px] h-[20px]";
    borderClass = "border-2";
  }
  
  let contentHtml = '';
  
  if (customIcon && (customIcon.startsWith('uploads/') || customIcon.startsWith('http'))) {
    const backendUrl = getBackendUrl();
    const imgUrl = customIcon.startsWith('http') ? customIcon : `${backendUrl}/${customIcon}`;
    if (zoom <= 5) {
      contentHtml = '';
    } else {
      contentHtml = `<img src="${imgUrl}" class="${imgClass} rounded-full object-cover" />`;
    }
  } else {
    if (!customIcon) {
      if (type === "Kantor SAR") {
        contentHtml = `<svg class="w-full h-full text-white p-1" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect width="16" height="20" x="4" y="2" rx="2" ry="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01"/><path d="M16 6h.01"/><path d="M8 10h.01"/><path d="M16 10h.01"/><path d="M8 14h.01"/><path d="M16 14h.01"/></svg>`;
      } else if (type === "Pos SAR") {
        contentHtml = `<svg class="w-full h-full text-white p-1" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`;
      } else if (type === "Unit Siaga SAR") {
        contentHtml = `<svg class="w-full h-full text-white p-1" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`;
      } else {
        contentHtml = `<svg class="w-full h-full text-white p-1" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`;
      }
    } else {
      contentHtml = `<span class="${textClass}">${customIcon}</span>`;
    }
  }

  return L.divIcon({
    className: 'pos-marker-icon',
    html: `
      <div class="relative flex items-center justify-center">
        <div class="relative ${containerClass} bg-gradient-to-br from-blue-500 to-indigo-700 ${borderClass} border-white rounded-full flex items-center justify-center shadow-lg transition-transform hover:scale-110">
          ${contentHtml}
        </div>
      </div>
    `,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
};

function MapController({ onMapReady }: { onMapReady: (map: L.Map) => void }) {
  const map = useMap();
  useEffect(() => {
    if (map) {
      onMapReady(map);
      const timer = setTimeout(() => {
        try {
          map.invalidateSize();
        } catch (_) {}
      }, 250);
      return () => clearTimeout(timer);
    }
  }, [map, onMapReady]);
  return null;
}

export default function DashboardMapInner({ reports = [], locations = [], kmlPath, isPublic = false }: DashboardMapInnerProps) {
  const [map, setMap] = useState<L.Map | null>(null);
  const [kmlPolygons, setKmlPolygons] = useState<[number, number][][]>([]);
  const [kmlLoading, setKmlLoading] = useState(false);
  const [zoom, setZoom] = useState(3.5);
  const hasInitializedPublicViewRef = useRef(false);

  useEffect(() => {
    if (!map || typeof map.on !== 'function') return;
    const handleZoom = () => {
      if (typeof map.getZoom === 'function') {
        const currentZoom = map.getZoom();
        setZoom((prev) => (Math.abs(prev - currentZoom) > 0.1 ? currentZoom : prev));
      }
    };
    map.on('zoomend', handleZoom);
    if (typeof map.getZoom === 'function') {
      const initialZoom = map.getZoom();
      setZoom((prev) => (Math.abs(prev - initialZoom) > 0.1 ? initialZoom : prev));
    }
    return () => {
      if (typeof map.off === 'function') {
        map.off('zoomend', handleZoom);
      }
    };
  }, [map]);
  
  // Center of Indonesia as default
  const defaultCenter: [number, number] = [-2.0, 118.0];

  // Fetch and parse KML file boundaries
  useEffect(() => {
    if (!kmlPath) {
      setKmlPolygons([]);
      return;
    }

    const fetchAndParseKml = async () => {
      setKmlLoading(true);
      let url = '';
      try {
        const backendUrl = getBackendUrl();
        url = `${backendUrl}/${kmlPath}`;
        console.log(`[DashboardMap] Fetching KML boundaries from: ${url}`);
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        const kmlText = await res.text();
        
        // Parse KML Coordinates
        const polygons: [number, number][][] = [];
        
        // Try DOMParser
        try {
          const parser = new DOMParser();
          const xmlDoc = parser.parseFromString(kmlText, 'text/xml');
          const coordinateElements = xmlDoc.getElementsByTagName('coordinates');
          
          for (let i = 0; i < coordinateElements.length; i++) {
            const coordStr = coordinateElements[i].textContent || '';
            const coords = coordStr.trim().split(/\s+/);
            const points: [number, number][] = [];
            
            for (const coord of coords) {
              if (!coord) continue;
              const parts = coord.split(',');
              if (parts.length >= 2) {
                const lng = parseFloat(parts[0]);
                const lat = parseFloat(parts[1]);
                if (!isNaN(lat) && !isNaN(lng)) {
                  points.push([lat, lng]);
                }
              }
            }
            if (points.length > 0) {
              polygons.push(points);
            }
          }
        } catch (e) {
          console.error("DOMParser parsing failed, trying regex fallback", e);
        }

        // Regex fallback
        if (polygons.length === 0) {
          const regex = /<coordinates>([\s\S]*?)<\/coordinates>/gi;
          let match;
          while ((match = regex.exec(kmlText)) !== null) {
            const coordStr = match[1] || '';
            const coords = coordStr.trim().split(/\s+/);
            const points: [number, number][] = [];
            
            for (const coord of coords) {
              if (!coord) continue;
              const parts = coord.split(',');
              if (parts.length >= 2) {
                const lng = parseFloat(parts[0]);
                const lat = parseFloat(parts[1]);
                if (!isNaN(lat) && !isNaN(lng)) {
                  points.push([lat, lng]);
                }
              }
            }
            if (points.length > 0) {
              polygons.push(points);
            }
          }
        }

        setKmlPolygons(polygons);
      } catch (err) {
        console.warn(`Gagal memuat atau memproses file KML (${url}):`, err);
        setKmlPolygons([]);
      } finally {
        setKmlLoading(false);
      }
    };

    fetchAndParseKml();
  }, [kmlPath]);

  // Try to fit bounds dynamically if there are markers or KML boundary, otherwise center on default
  useEffect(() => {
    if (!map || typeof map.setView !== 'function') return;

    // For public landing map, center once on Indonesia without recurring setView or setZoom
    if (isPublic) {
      if (!hasInitializedPublicViewRef.current) {
        map.setView(defaultCenter, 3.5);
        hasInitializedPublicViewRef.current = true;
      }
      return;
    }

    const coords: [number, number][] = [];
    
    if (Array.isArray(reports)) {
      reports.forEach((rep) => {
        if (rep.koordinat_lat && rep.koordinat_lng) {
          coords.push([rep.koordinat_lat, rep.koordinat_lng]);
        }
      });
    }

    if (Array.isArray(locations)) {
      locations.forEach((loc) => {
        if (loc.lat && loc.lng) {
          coords.push([loc.lat, loc.lng]);
        }
      });
    }

    // Add KML coordinates to bounds calculation
    kmlPolygons.forEach((poly) => {
      poly.forEach((pt) => {
        coords.push(pt);
      });
    });

    if (coords.length > 0 && typeof map.fitBounds === 'function') {
      try {
        const bounds = L.latLngBounds(coords);
        // Fit bounds but cap at zoom 5.0 to allow regional zoom while keeping public map at 3.5
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 5.0 });
      } catch (e) {
        console.warn('Failed to fitBounds:', e);
        map.setView(defaultCenter, 5.0);
      }
    } else {
      map.setView(defaultCenter, 5.0);
    }
  }, [reports, locations, kmlPolygons, map, isPublic]);

  return (
    <div className="relative h-full w-full">
      <MapContainer
        center={defaultCenter}
        zoom={3.5}
        zoomSnap={0.5}
        scrollWheelZoom={true}
        zoomControl={false}
        style={{ height: '100%', width: '100%' }}
        className="z-0"
      >
        <MapController onMapReady={setMap} />

        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        
        {/* Render KML Boundaries */}
        {kmlPolygons.map((polygonCoords, index) => (
          <Polygon
            key={`kml_poly_${index}`}
            positions={polygonCoords}
            pathOptions={{
              color: '#475569',      // Slate border
              fillColor: '#475569',  // Subtle slate fill
              fillOpacity: 0.05,     // Low opacity for subtle commands center look
              weight: 2,             // Semi-thin elegant border
              dashArray: '5, 5'      // Dashed border for official boundary look
            }}
          />
        ))}
        
        {/* Render Spatial Hotspot Layer (PostGIS ST_ClusterDBSCAN) - Internal only */}
        {!isPublic && <HotspotMapLayer epsKm={5.0} minSamples={2} />}

        {/* Render Clustered Incident Markers (Dynamic Radius Spatial Cluster) */}
        <IncidentMarkerCluster reports={reports} zoom={zoom} />


        {/* Render Pos/Unit SAR Markers */}
        {locations
          .filter((l) => l.lat && l.lng)
          .map((loc) => {
            const markerIcon = createPosMarker(loc.type, loc.icon, zoom);
            return markerIcon ? (
              <Marker 
                key={`pos_${loc.id}`} 
                position={[loc.lat, loc.lng]} 
                icon={markerIcon}
              >
                <Popup className="premium-leaflet-popup">
                  <div className="p-2 space-y-3 min-w-[240px] text-gray-700 text-xs">
                    {/* Header */}
                    <div className="flex items-center justify-between border-b border-gray-100 pb-2">
                      <span className="font-extrabold text-[10px] text-blue-600 bg-blue-50 border border-blue-100 px-2 py-0.5 rounded-lg tracking-wider uppercase flex items-center gap-1">
                        <Shield className="w-3 h-3" /> UNIT SAR
                      </span>
                      <span className="text-[10px] font-bold text-gray-500">
                        {loc.type}
                      </span>
                    </div>

                    {/* Title */}
                    <div>
                      <h4 className="font-bold text-gray-900 text-sm leading-snug">{loc.name}</h4>
                      <p className="text-[10px] text-gray-500 mt-0.5 flex items-center gap-1 leading-normal">
                        <MapPin className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                        {loc.address || 'Alamat tidak tercantum'}
                      </p>
                    </div>

                    {/* Resources */}
                    <div className="space-y-1.5 font-medium">
                      {loc.unsur && (
                        <div className="flex items-start gap-1.5">
                          <Users className="w-3.5 h-3.5 text-gray-400 shrink-0 mt-0.5" />
                          <div className="text-[10px] text-gray-600">
                            <span className="font-bold text-gray-700">Personil/Unsur:</span> {loc.unsur}
                          </div>
                        </div>
                      )}
                      {loc.alut && (
                        <div className="flex items-start gap-1.5">
                          <Anchor className="w-3.5 h-3.5 text-gray-400 shrink-0 mt-0.5" />
                          <div className="text-[10px] text-gray-600">
                            <span className="font-bold text-gray-700">Alut/Palsar:</span> {loc.alut}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </Popup>
              </Marker>
            ) : null;
          })}
      </MapContainer>

      {/* Clean Map Zoom Controls */}
      <div className="absolute top-4 right-4 z-[1000] flex flex-col pointer-events-auto shadow-sm">
        <div className="bg-white/95 backdrop-blur-md rounded-xl border border-slate-200/80 flex flex-col divide-y divide-slate-100 select-none overflow-hidden">
          <button 
            onClick={() => map?.zoomIn()}
            className="h-8 w-8 hover:bg-slate-100 text-slate-700 font-bold text-sm flex items-center justify-center transition-colors cursor-pointer"
            title="Perbesar Peta"
          >
            +
          </button>
          <button 
            onClick={() => map?.zoomOut()}
            className="h-8 w-8 hover:bg-slate-100 text-slate-700 font-bold text-base flex items-center justify-center transition-colors cursor-pointer"
            title="Perkecil Peta"
          >
            −
          </button>
        </div>
      </div>
    </div>
  );
}
