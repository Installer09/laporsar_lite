'use client';

import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';

interface IncidentMarkerClusterProps {
  reports?: any[];
  zoom?: number;
}

// Custom Pulse Marker Icon for Emergency Reports
const createIncidentMarkerIcon = (jenisKejadian: string, status: string, zoom: number) => {
  let size = 32;
  let containerClass = "w-8 h-8";
  let pingClass = "h-8 w-8";
  let textClass = "text-[12px]";
  let borderClass = "border-2";

  if (zoom <= 4) {
    size = 12;
    containerClass = "w-3 h-3";
    pingClass = "h-3 w-3";
    textClass = "text-[0px]";
    borderClass = "border";
  } else if (zoom <= 7) {
    size = 18;
    containerClass = "w-4.5 h-4.5";
    pingClass = "h-4.5 w-4.5";
    textClass = "text-[0px]";
    borderClass = "border";
  } else if (zoom <= 9) {
    size = 24;
    containerClass = "w-6 h-6";
    pingClass = "h-6 w-6";
    textClass = "text-[10px]";
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

// Custom Cluster Badge Icon Generator
export const createCustomClusterIcon = (cluster: any): L.DivIcon => {
  const childMarkers = cluster.getAllChildMarkers();
  const totalCount = childMarkers.length;

  // Check if any incident in the cluster is AKTIF
  const hasActiveEmergency = childMarkers.some((marker: any) => {
    return marker.options?.reportData?.status === 'AKTIF';
  });

  const clusterClass = hasActiveEmergency 
    ? 'sar-cluster-emergency' 
    : 'sar-cluster-warning';

  let size = 36;
  let textStyle = 'text-xs font-black';
  if (totalCount > 50) {
    size = 48;
    textStyle = 'text-base font-black';
  } else if (totalCount > 10) {
    size = 42;
    textStyle = 'text-sm font-black';
  }

  return L.divIcon({
    html: `
      <div class="sar-cluster-container ${clusterClass}" style="width: ${size}px; height: ${size}px;">
        ${hasActiveEmergency ? '<div class="sar-cluster-ping"></div>' : ''}
        <div class="relative z-10 flex flex-col items-center justify-center leading-none">
          <span class="${textStyle}">${totalCount}</span>
          <span class="text-[7.5px] uppercase tracking-tighter opacity-90 mt-0.5 font-bold">Laporan</span>
        </div>
      </div>
    `,
    className: 'sar-cluster-icon',
    iconSize: L.point(size, size, true),
    iconAnchor: L.point(size / 2, size / 2),
  });
};

// Generate Popup HTML for Report
const createReportPopupHtml = (report: any) => {
  const statusBg = report.status === 'PENDING'
    ? 'background:#fff7ed; color:#c2410c; border:1px solid #ffedd5;'
    : report.status === 'AKTIF'
    ? 'background:#eff6ff; color:#1d4ed8; border:1px solid #dbeafe;'
    : 'background:#f0fdf4; color:#15803d; border:1px solid #dcfce7;';

  const radiusHtml = report.radius_pencarian ? `
    <div style="grid-column: span 2; border-top: 1px solid #f1f5f9; padding-top: 4px; margin-top: 4px;">
      <span style="font-size: 9px; color: #94a3b8; text-transform: uppercase; font-weight: 700; display: block;">Radius Pencarian</span>
      <span style="font-size: 10px; color: #334155; font-weight: 600;">${report.radius_pencarian} km (${(report.radius_pencarian / 1.852).toFixed(1)} Nm)</span>
    </div>
  ` : '';

  const gmapsUrl = report.gmaps_link || `https://www.google.com/maps?q=${report.koordinat_lat},${report.koordinat_lng}`;

  return `
    <div style="padding: 8px; min-width: 240px; font-family: sans-serif; color: #334155;">
      <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #f1f5f9; padding-bottom: 8px; margin-bottom: 8px;">
        <span style="font-weight: 800; font-size: 10px; color: #dc2626; background: #fef2f2; border: 1px solid #fee2e2; padding: 2px 6px; border-radius: 6px; text-transform: uppercase; letter-spacing: 0.05em;">
          DARURAT
        </span>
        <span style="font-size: 10px; font-weight: 700; color: #64748b; font-family: monospace;">
          ${report.no_laporan || ''}
        </span>
      </div>

      <div style="margin-bottom: 8px;">
        <h4 style="font-weight: 700; color: #0f172a; font-size: 13px; margin: 0; line-height: 1.3;">${report.jenis_kejadian || 'Insiden SAR'}</h4>
        ${report.tenant_name ? `<div style="font-size: 10px; font-weight: 800; color: #2563eb; margin-top: 4px; text-transform: uppercase;">${report.tenant_name}</div>` : ''}
        <p style="font-size: 10px; color: #64748b; margin: 4px 0 0 0; line-height: 1.4;">${report.lokasi_teks || ''}</p>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; background: #f8fafc; padding: 8px; border-radius: 8px; border: 1px solid #f1f5f9;">
        <div>
          <span style="font-size: 9px; color: #94a3b8; text-transform: uppercase; font-weight: 700; display: block;">Waktu</span>
          <span style="font-size: 10px; color: #334155; font-weight: 600;">${report.waktu || '-'}</span>
        </div>
        <div>
          <span style="font-size: 9px; color: #94a3b8; text-transform: uppercase; font-weight: 700; display: block;">Total Korban</span>
          <span style="font-size: 10px; color: #334155; font-weight: 600;">${report.korban_total || report.korban || 'N/A'}</span>
        </div>
        ${radiusHtml}
      </div>

      <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 8px; padding-top: 4px;">
        <span style="padding: 2px 8px; border-radius: 6px; font-size: 9px; font-weight: 700; letter-spacing: 0.05em; ${statusBg}">
          ${report.status || 'AKTIF'}
        </span>
        <a href="${gmapsUrl}" target="_blank" rel="noopener noreferrer" style="font-size: 10px; color: #ea580c; font-weight: 700; text-decoration: none;">
          Buka di Google Maps →
        </a>
      </div>
    </div>
  `;
};

export default function IncidentMarkerCluster({ reports = [], zoom = 3.5 }: IncidentMarkerClusterProps) {
  const map = useMap();
  const clusterGroupRef = useRef<any>(null);
  const rawMarkersRef = useRef<L.Marker[]>([]);
  const circlesRef = useRef<L.Circle[]>([]);

  useEffect(() => {
    if (!map) return;

    if (typeof window !== 'undefined') {
      (window as any).L = L;
      try {
        require('leaflet.markercluster');
      } catch (e) {
        console.warn('Failed to load leaflet.markercluster:', e);
      }
    }

    try {
      if (typeof (L as any).markerClusterGroup === 'function') {
        const clusterGroup = (L as any).markerClusterGroup({
          maxClusterRadius: 60,
          disableClusteringAtZoom: 13,
          spiderfyOnMaxZoom: true,
          showCoverageOnHover: true,
          chunkedLoading: true,
          iconCreateFunction: createCustomClusterIcon,
          polygonOptions: {
            fillColor: '#f97316',
            color: '#ea580c',
            weight: 2,
            opacity: 0.8,
            fillOpacity: 0.15,
            dashArray: '4, 4',
          },
        });

        clusterGroupRef.current = clusterGroup;
        map.addLayer(clusterGroup);
      } else {
        clusterGroupRef.current = null;
      }
    } catch (e) {
      console.warn('Failed to init markerClusterGroup:', e);
      clusterGroupRef.current = null;
    }

    return () => {
      if (clusterGroupRef.current && map) {
        try {
          map.removeLayer(clusterGroupRef.current);
        } catch (_) {}
        clusterGroupRef.current = null;
      }
    };
  }, [map]);

  // Update markers and circles when reports or zoom change
  useEffect(() => {
    if (!map) return;
    const clusterGroup = clusterGroupRef.current;

    // Clear existing markers & circles
    if (clusterGroup) {
      try { clusterGroup.clearLayers(); } catch (_) {}
    }
    rawMarkersRef.current.forEach((m) => {
      try { map.removeLayer(m); } catch (_) {}
    });
    rawMarkersRef.current = [];

    circlesRef.current.forEach((circle) => {
      try { map.removeLayer(circle); } catch (_) {}
    });
    circlesRef.current = [];

    const validReports = Array.isArray(reports) ? reports.filter(
      (r) => r.koordinat_lat && r.koordinat_lng && r.status !== 'TIDAK_AKTIF' && r.status !== 'SALAH_LAPORAN'
    ) : [];

    const newMarkers: L.Marker[] = [];

    validReports.forEach((report) => {
      const icon = createIncidentMarkerIcon(report.jenis_kejadian, report.status, zoom);
      const marker = L.marker([report.koordinat_lat, report.koordinat_lng], {
        icon,
        reportData: report,
      } as any);

      const popupHtml = createReportPopupHtml(report);
      marker.bindPopup(popupHtml, { className: 'premium-leaflet-popup' });
      newMarkers.push(marker);

      // Render search radius circle if specified
      if (report.radius_pencarian) {
        const circle = L.circle([report.koordinat_lat, report.koordinat_lng], {
          radius: report.radius_pencarian * 1000,
          color: report.status === 'PENDING' ? '#f97316' : '#ef4444',
          fillColor: report.status === 'PENDING' ? '#fed7aa' : '#fca5a5',
          fillOpacity: 0.2,
          weight: 2,
          dashArray: '5, 5',
        });
        circle.addTo(map);
        circlesRef.current.push(circle);
      }
    });

    if (clusterGroup) {
      try {
        clusterGroup.addLayers(newMarkers);
      } catch (e) {
        console.warn('Failed to add layers to clusterGroup, fallback to map:', e);
        newMarkers.forEach((m) => {
          m.addTo(map);
          rawMarkersRef.current.push(m);
        });
      }
    } else {
      newMarkers.forEach((m) => {
        m.addTo(map);
        rawMarkersRef.current.push(m);
      });
    }

    return () => {
      if (clusterGroup) {
        try { clusterGroup.clearLayers(); } catch (_) {}
      }
      rawMarkersRef.current.forEach((m) => {
        try { map.removeLayer(m); } catch (_) {}
      });
      rawMarkersRef.current = [];
      circlesRef.current.forEach((circle) => {
        try { map.removeLayer(circle); } catch (_) {}
      });
      circlesRef.current = [];
    };
  }, [reports, zoom, map]);

  return null;
}
