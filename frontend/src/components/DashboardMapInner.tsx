'use client';

import { useState, useEffect, Fragment } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polygon, Circle } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Shield, MapPin, AlertTriangle, Calendar, Users, Anchor, Navigation, ChevronUp, ChevronDown, ChevronLeft, ChevronRight } from 'lucide-react';
import { getBackendUrl } from '@/lib/api';
import IncidentMarkerCluster from './MarkerClusterGroup';
import HotspotMapLayer from './HotspotMapLayer';


interface DashboardMapInnerProps {
  reports?: any[];
  locations?: any[];
  kmlPath?: string;
  isPublic?: boolean;
}

// Custom Premium Pulse Marker Icon for Emergencies (Red/Orange based on status)
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
  
  let emoji = "🚨";
  const lowerJenis = (jenisKejadian || '').toLowerCase();
  if (lowerJenis.includes("kapal") || lowerJenis.includes("laut") || lowerJenis.includes("tenggelam")) {
    emoji = "🚢";
  } else if (lowerJenis.includes("manusia") || lowerJenis.includes("hilang") || lowerJenis.includes("kmm")) {
    emoji = "👤";
  } else if (lowerJenis.includes("pesawat") || lowerJenis.includes("udara")) {
    emoji = "✈️";
  } else if (lowerJenis.includes("bencana") || lowerJenis.includes("alam") || lowerJenis.includes("banjir")) {
    emoji = "🌊";
  }

  // Determine colors based on status: PENDING is orange/amber, AKTIF is pulsing red
  let pulseColor = "bg-red-400";
  let gradientColors = "from-red-500 to-rose-700";
  
  if (status === 'PENDING') {
    pulseColor = "bg-orange-400";
    gradientColors = "from-orange-500 to-amber-700";
  }

  return L.divIcon({
    className: 'incident-marker-icon',
    html: `
      <div class="relative flex items-center justify-center">
        <span class="animate-ping absolute inline-flex rounded-full ${pulseColor} opacity-75 ${pingClass}"></span>
        <div class="relative ${containerClass} bg-gradient-to-br ${gradientColors} ${borderClass} border-white rounded-full flex items-center justify-center shadow-lg transition-transform hover:scale-110">
          <span class="${textClass}">${emoji}</span>
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
    let emoji = customIcon || "🏠";
    if (!customIcon) {
      if (type === "Kantor SAR") {
        emoji = "🏢";
      } else if (type === "Pos SAR") {
        emoji = "🏠";
      } else if (type === "Unit Siaga SAR") {
        emoji = "🛡️";
      }
    }
    contentHtml = `<span class="${textClass}">${emoji}</span>`;
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

export default function DashboardMapInner({ reports = [], locations = [], kmlPath, isPublic = false }: DashboardMapInnerProps) {
  const [map, setMap] = useState<L.Map | null>(null);
  const [kmlPolygons, setKmlPolygons] = useState<[number, number][][]>([]);
  const [kmlLoading, setKmlLoading] = useState(false);
  const [zoom, setZoom] = useState(3.5);

  useEffect(() => {
    if (!map) return;
    const handleZoom = () => {
      setZoom(map.getZoom());
    };
    map.on('zoomend', handleZoom);
    // Get initial zoom
    setZoom(map.getZoom());
    return () => {
      map.off('zoomend', handleZoom);
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
    if (!map) return;

    // For public landing map, we want to center on the entire map of Indonesia and not fit bounds of individual UPTs/reports
    if (isPublic) {
      map.setView(defaultCenter, 3.5);
      setZoom(3.5);
      return;
    }

    const coords: [number, number][] = [];
    
    reports.forEach((rep) => {
      if (rep.koordinat_lat && rep.koordinat_lng) {
        coords.push([rep.koordinat_lat, rep.koordinat_lng]);
      }
    });

    locations.forEach((loc) => {
      if (loc.lat && loc.lng) {
        coords.push([loc.lat, loc.lng]);
      }
    });

    // Add KML coordinates to bounds calculation
    kmlPolygons.forEach((poly) => {
      poly.forEach((pt) => {
        coords.push(pt);
      });
    });

    if (coords.length > 0) {
      const bounds = L.latLngBounds(coords);
      // Fit bounds but cap at zoom 5.0 to allow regional zoom while keeping public map at 3.5
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 5.0 });
    } else {
      map.setView(defaultCenter, 5.0);
    }
  }, [reports, locations, kmlPolygons, map]);

  return (
    <div className="relative h-full w-full">
      <MapContainer
        center={defaultCenter}
        zoom={3.5}
        zoomSnap={0.5}
        scrollWheelZoom={true}
        zoomControl={false}
        style={{ height: '100%', width: '100%' }}
        ref={setMap}
        className="z-0"
      >
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
              color: '#ea580c',      // Orange border (amber-600)
              fillColor: '#f97316',  // Amber fill
              fillOpacity: 0.05,     // Low opacity for subtle commands center look
              weight: 2,             // Semi-thin elegant border
              dashArray: '5, 5'      // Dashed border for official boundary look
            }}
          />
        ))}
        
        {/* Render Spatial Hotspot Layer (PostGIS ST_ClusterDBSCAN) */}
        <HotspotMapLayer epsKm={5.0} minSamples={2} />

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

      {/* Custom Unified Navigation Widget (D-pad Panning & Zoom Controls) */}
      <div className="absolute top-4 right-4 z-[1000] flex flex-col gap-1.5 pointer-events-auto">
        {/* Pan Controls (D-pad) */}
        <div className="bg-white/95 backdrop-blur-md p-1 rounded-xl shadow-md border border-slate-200/60 flex flex-col items-center justify-center w-18 h-18 relative select-none">
          <button 
            onClick={() => map?.panBy([0, -80])}
            className="absolute top-0.5 p-0.5 hover:bg-slate-100 rounded-md text-slate-600 transition-colors flex items-center justify-center"
            title="Geser Atas"
          >
            <ChevronUp className="w-3.5 h-3.5" />
          </button>
          <div className="flex gap-2 items-center justify-center w-full h-full">
            <button 
              onClick={() => map?.panBy([-80, 0])}
              className="p-0.5 hover:bg-slate-100 rounded-md text-slate-600 transition-colors flex items-center justify-center"
              title="Geser Kiri"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <div className="w-2 h-2 rounded-full bg-slate-200/60 border border-slate-300/20" />
            <button 
              onClick={() => map?.panBy([80, 0])}
              className="p-0.5 hover:bg-slate-100 rounded-md text-slate-600 transition-colors flex items-center justify-center"
              title="Geser Kanan"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
          <button 
            onClick={() => map?.panBy([0, 80])}
            className="absolute bottom-0.5 p-0.5 hover:bg-slate-100 rounded-md text-slate-600 transition-colors flex items-center justify-center"
            title="Geser Bawah"
          >
            <ChevronDown className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Zoom Controls */}
        <div className="bg-white/95 backdrop-blur-md p-0.5 rounded-lg shadow-md border border-slate-200/60 flex flex-col divide-y divide-slate-100 select-none items-center">
          <button 
            onClick={() => map?.zoomIn()}
            className="h-6 w-6 hover:bg-slate-100 rounded-md text-slate-700 font-extrabold text-xs flex items-center justify-center transition-colors"
            title="Perbesar"
          >
            +
          </button>
          <button 
            onClick={() => map?.zoomOut()}
            className="h-6 w-6 hover:bg-slate-100 rounded-md text-slate-700 font-extrabold text-sm flex items-center justify-center transition-colors"
            title="Perkecil"
          >
            −
          </button>
        </div>
      </div>
    </div>
  );
}
