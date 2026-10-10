'use client';

import { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Search, MapPin, Loader2 } from 'lucide-react';

interface MapPickerInnerProps {
  initialLat?: number;
  initialLng?: number;
  onChange: (lat: number, lng: number, address?: string) => void;
}

// Custom Premium Pulse Marker Icon
const createCustomMarker = () => {
  if (typeof window === 'undefined') return null;
  return L.divIcon({
    className: 'custom-marker',
    html: `
      <div class="relative flex items-center justify-center">
        <span class="animate-ping absolute inline-flex h-8 w-8 rounded-full bg-slate-400 opacity-75"></span>
        <div class="relative w-7 h-7 bg-slate-900 border-2 border-white rounded-full flex items-center justify-center shadow-lg">
          <div class="w-2.5 h-2.5 bg-white rounded-full"></div>
        </div>
      </div>
    `,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
  });
};

export default function MapPickerInner({ initialLat = 3.945, initialLng = 108.384, onChange }: MapPickerInnerProps) {
  const [position, setPosition] = useState<[number, number]>([initialLat, initialLng]);
  const [latInput, setLatInput] = useState(initialLat.toString());
  const [lngInput, setLngInput] = useState(initialLng.toString());
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [map, setMap] = useState<L.Map | null>(null);

  // Sync inputs and positions when initial props change
  useEffect(() => {
    setPosition([initialLat, initialLng]);
    setLatInput(initialLat.toString());
    setLngInput(initialLng.toString());
  }, [initialLat, initialLng]);

  // Handle map clicks to update marker and inputs
  function LocationMarker() {
    useMapEvents({
      click(e) {
        const { lat, lng } = e.latlng;
        setPosition([lat, lng]);
        setLatInput(lat.toFixed(6));
        setLngInput(lng.toFixed(6));
        onChange(lat, lng);
      },
    });
    const markerIcon = createCustomMarker();
    return markerIcon ? <Marker position={position} icon={markerIcon} /> : null;
  }

  // Auto-pan map when position changes
  useEffect(() => {
    if (map) {
      map.setView(position, map.getZoom());
    }
  }, [position, map]);

  // Geocoding with Nominatim API
  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setIsSearching(true);
    setSearchError('');

    try {
      const response = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(searchQuery)}&limit=1`
      );
      const data = await response.json();

      if (data && data.length > 0) {
        const lat = parseFloat(data[0].lat);
        const lng = parseFloat(data[0].lon);
        const displayName = data[0].display_name;

        setPosition([lat, lng]);
        setLatInput(lat.toFixed(6));
        setLngInput(lng.toFixed(6));
        onChange(lat, lng, displayName);
      } else {
        setSearchError('Lokasi tidak ditemukan. Coba ketik secara manual.');
      }
    } catch (err) {
      setSearchError('Gagal menghubungi layanan peta. Coba koordinat manual.');
    } finally {
      setIsSearching(false);
    }
  };

  const handleLatChange = (val: string) => {
    setLatInput(val);
    const parsed = parseFloat(val);
    if (!isNaN(parsed)) {
      setPosition([parsed, position[1]]);
      onChange(parsed, position[1]);
    }
  };

  const handleLngChange = (val: string) => {
    setLngInput(val);
    const parsed = parseFloat(val);
    if (!isNaN(parsed)) {
      setPosition([position[0], parsed]);
      onChange(position[0], parsed);
    }
  };

  return (
    <div className="space-y-4">
      {/* Search Input */}
      <form onSubmit={handleSearch} className="relative flex gap-2">
        <div className="relative flex-grow">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Cari lokasi (cth: Pantai Piwang Natuna)..."
            className="w-full pl-9 pr-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
          />
        </div>
        <button
          type="submit"
          disabled={isSearching}
          className="px-4 py-2.5 bg-slate-900 hover:bg-slate-800 disabled:bg-slate-400 text-white text-sm font-medium rounded-xl flex items-center gap-2 transition-colors shadow-sm"
        >
          {isSearching ? <Loader2 className="w-4 h-4 animate-spin" /> : <MapPin className="w-4 h-4" />}
          Cari
        </button>
      </form>

      {searchError && <p className="text-xs text-red-500 font-medium">{searchError}</p>}

      {/* Map Container */}
      <div className="relative h-[250px] w-full rounded-2xl overflow-hidden border border-gray-100 shadow-sm z-0">
        <MapContainer
          center={position}
          zoom={12}
          scrollWheelZoom={true}
          style={{ height: '100%', width: '100%' }}
          ref={setMap}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <LocationMarker />
        </MapContainer>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 bg-gray-50 p-4 rounded-2xl border border-gray-100">
        <div>
          <label className="block text-xs font-bold text-gray-500 mb-1.5">Latitude (Lintang)</label>
          <input
            type="text"
            value={latInput}
            onChange={(e) => handleLatChange(e.target.value)}
            placeholder="Contoh: 3.945000"
            className="w-full px-3 py-2 bg-white border border-gray-200 focus:border-slate-400 focus:ring-2 focus:ring-slate-900/10 rounded-xl text-sm font-mono transition-all outline-none text-gray-800"
          />
        </div>
        <div>
          <label className="block text-xs font-bold text-gray-500 mb-1.5">Longitude (Bujur)</label>
          <input
            type="text"
            value={lngInput}
            onChange={(e) => handleLngChange(e.target.value)}
            placeholder="Contoh: 108.384000"
            className="w-full px-3 py-2 bg-white border border-gray-200 focus:border-slate-400 focus:ring-2 focus:ring-slate-900/10 rounded-xl text-sm font-mono transition-all outline-none text-gray-800"
          />
        </div>
        <div className="sm:col-span-2 text-[10px] text-gray-400 italic flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 mt-1">
          <span>*Klik peta untuk memindahkan pin secara presisi</span>
          <span className="font-semibold text-slate-800">Bisa diketik manual untuk akurasi tinggi</span>
        </div>
      </div>
    </div>
  );
}
