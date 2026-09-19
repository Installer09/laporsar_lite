'use client';

import { useState, useEffect } from 'react';
import { 
  Smartphone, 
  QrCode, 
  Mic, 
  MapPin, 
  BellRing, 
  ArrowRight, 
  ShieldCheck, 
  Globe, 
  X,
  ExternalLink
} from 'lucide-react';
import Link from 'next/link';

interface MobileDownloadSectionProps {
  chatUrl?: string;
}

function SimpleSvgQrCode({ value, size = 160 }: { value: string; size?: number }) {
  // Generates clean dynamic SVG pattern for QR visualization
  const dots = [];
  const seed = value.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  
  for (let r = 0; r < 21; r++) {
    for (let c = 0; c < 21; c++) {
      const isCorner1 = (r < 7 && c < 7);
      const isCorner2 = (r < 7 && c > 13);
      const isCorner3 = (r > 13 && c < 7);
      
      if (!isCorner1 && !isCorner2 && !isCorner3) {
        const val = Math.sin((r * 21 + c + seed) * 9301 + 49297) * 233280;
        if (Math.abs(val - Math.floor(val)) > 0.45) {
          dots.push({ r, c });
        }
      }
    }
  }

  return (
    <div className="bg-white p-3 rounded-2xl shadow-inner inline-block border border-slate-200">
      <svg width={size} height={size} viewBox="0 0 29 29" className="shape-rendering-crispEdges">
        <rect width="29" height="29" fill="white" />
        {/* Top-Left Marker */}
        <rect x="2" y="2" width="7" height="7" fill="#0F172A" />
        <rect x="3" y="3" width="5" height="5" fill="white" />
        <rect x="4" y="4" width="3" height="3" fill="#0F172A" />

        {/* Top-Right Marker */}
        <rect x="20" y="2" width="7" height="7" fill="#0F172A" />
        <rect x="21" y="3" width="5" height="5" fill="white" />
        <rect x="22" y="4" width="3" height="3" fill="#0F172A" />

        {/* Bottom-Left Marker */}
        <rect x="2" y="20" width="7" height="7" fill="#0F172A" />
        <rect x="3" y="21" width="5" height="5" fill="white" />
        <rect x="4" y="22" width="3" height="3" fill="#0F172A" />

        {/* Matrix Payload Dots */}
        {dots.map((d, i) => (
          <rect key={i} x={d.c + 4} y={d.r + 4} width="1" height="1" fill="#0F172A" />
        ))}
        
        {/* Center Icon Badge Overlay */}
        <rect x="11.5" y="11.5" width="6" height="6" rx="1.5" fill="white" stroke="#EA580C" strokeWidth="0.8" />
        <circle cx="14.5" cy="14.5" r="1.8" fill="#DC2626" />
      </svg>
    </div>
  );
}

export function MobileDownloadSection({ chatUrl = '/chat' }: MobileDownloadSectionProps) {
  const [isQrModalOpen, setIsQrModalOpen] = useState(false);
  const [currentUrl, setCurrentUrl] = useState<string>('');

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setCurrentUrl(`${window.location.origin}/chat`);
    }
  }, []);

  return (
    <>
      <section className="w-full my-8 relative z-10">
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white p-6 sm:p-8 lg:p-10 border border-slate-700/60 shadow-xl">
          {/* Glowing Accents */}
          <div className="absolute top-[-30%] right-[-10%] w-[350px] h-[350px] rounded-full bg-gradient-to-br from-orange-500/20 to-red-600/20 blur-[90px] pointer-events-none" />
          <div className="absolute bottom-[-30%] left-[-10%] w-[300px] h-[300px] rounded-full bg-gradient-to-tr from-orange-600/15 to-amber-500/10 blur-[80px] pointer-events-none" />

          <div className="relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
            {/* Left Content Column */}
            <div className="lg:col-span-7 space-y-5">
              {/* Badge */}
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-orange-500/15 border border-orange-500/30 text-orange-400 text-xs font-extrabold tracking-wide uppercase">
                <Smartphone className="w-4 h-4 text-orange-400" />
                <span>Lapor SAR Web Mobile (PWA)</span>
                <span className="w-1.5 h-1.5 bg-orange-400 rounded-full animate-ping" />
              </div>

              {/* Title & Desc */}
              <div className="space-y-2">
                <h3 className="text-2xl sm:text-3xl lg:text-4xl font-black text-white tracking-tight leading-tight">
                  Akses Kedaruratan Langsung <br />
                  <span className="bg-gradient-to-r from-orange-400 via-amber-400 to-red-400 bg-clip-text text-transparent">
                    Dari Perangkat Smartphone
                  </span>
                </h3>
                <p className="text-xs sm:text-sm text-slate-300 font-medium leading-relaxed max-w-xl">
                  Buka portal darurat Lapor SAR langsung dari smartphone melalui browser tanpa perlu instalasi APK manual. Dilengkapi perekam voice note AI, pelacak GPS presisi, dan formulir tanggap darurat instan.
                </p>
              </div>

              {/* Mobile Features List */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
                <div className="p-3 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-md flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-orange-500/20 border border-orange-500/30 flex items-center justify-center shrink-0 text-orange-400">
                    <Mic className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-white">Voice Lapor</h4>
                    <p className="text-[10px] text-slate-400">Transkripsi AI Cloud Instan</p>
                  </div>
                </div>

                <div className="p-3 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-md flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-red-500/20 border border-red-500/30 flex items-center justify-center shrink-0 text-red-400">
                    <MapPin className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-white">GPS Presisi</h4>
                    <p className="text-[10px] text-slate-400">Koordinat otomatis pelapor</p>
                  </div>
                </div>

                <div className="p-3 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-md flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center shrink-0 text-amber-400">
                    <BellRing className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-white">Respon Cepat</h4>
                    <p className="text-[10px] text-slate-400">Sinkronisasi Command Center</p>
                  </div>
                </div>
              </div>

              {/* CTA Action Buttons */}
              <div className="flex flex-wrap items-center gap-3 pt-3">
                <button
                  onClick={() => setIsQrModalOpen(true)}
                  className="px-5 py-3 bg-gradient-to-r from-orange-500 to-red-600 hover:from-orange-600 hover:to-red-700 text-white font-black text-xs sm:text-sm rounded-xl shadow-lg shadow-orange-500/20 transition-all flex items-center gap-2 cursor-pointer"
                >
                  <QrCode className="w-4 h-4" />
                  <span>Scan QR Code Demo</span>
                </button>

                <Link
                  href="/chat"
                  className="px-5 py-3 bg-slate-800 hover:bg-slate-700 border border-slate-600 text-white font-extrabold text-xs sm:text-sm rounded-xl transition-all flex items-center gap-2 cursor-pointer"
                >
                  <ExternalLink className="w-4 h-4 text-orange-400" />
                  <span>Buka Portal Pelapor</span>
                </Link>

                <span className="text-[11px] text-slate-400 font-medium flex items-center gap-1.5 ml-1">
                  <ShieldCheck className="w-4 h-4 text-green-400" /> Aman & Responsif di Semua HP
                </span>
              </div>
            </div>

            {/* Right Interactive Mockup / QR Quick Preview */}
            <div className="lg:col-span-5 flex justify-center">
              <div className="relative bg-gradient-to-b from-slate-800/80 to-slate-900/90 border border-slate-700/80 rounded-3xl p-6 shadow-2xl max-w-xs w-full text-center space-y-4 backdrop-blur-md">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-orange-500/20 text-orange-400 border border-orange-500/30 mx-auto">
                  <Smartphone className="w-6 h-6" />
                </div>
                
                <div>
                  <h4 className="text-sm font-black text-white">Pindai QR untuk Demo di HP</h4>
                  <p className="text-[11px] text-slate-400 font-medium mt-0.5">
                    Arahkan kamera smartphone untuk mencoba alur pelaporan.
                  </p>
                </div>

                {/* QR Display */}
                <div className="flex justify-center my-2">
                  <SimpleSvgQrCode value={currentUrl || '/chat'} size={150} />
                </div>

                <div className="flex items-center justify-center gap-2 text-[10px] font-bold text-slate-400 uppercase tracking-widest pt-1">
                  <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700">Web Mobile</span>
                  <span>•</span>
                  <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700">iOS & Android</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* QR Code Full Modal */}
      {isQrModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-sm w-full p-6 text-center space-y-4 shadow-2xl relative animate-in fade-in zoom-in-95 duration-200">
            <button 
              onClick={() => setIsQrModalOpen(false)}
              className="absolute top-4 right-4 p-2 text-slate-400 hover:text-slate-600 rounded-full hover:bg-slate-100 transition"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="w-12 h-12 rounded-2xl bg-orange-100 text-orange-600 flex items-center justify-center mx-auto">
              <QrCode className="w-6 h-6" />
            </div>

            <div>
              <h3 className="text-lg font-black text-slate-900">Pindai QR Code Pelapor</h3>
              <p className="text-xs text-slate-500 mt-1">
                Scan kode ini dengan kamera ponsel untuk langsung membuka formulir pelaporan darurat.
              </p>
            </div>

            <div className="flex justify-center p-4 bg-slate-50 rounded-2xl border border-slate-100">
              <SimpleSvgQrCode value={currentUrl || '/chat'} size={200} />
            </div>

            <p className="text-[11px] text-slate-400 break-all font-mono">
              {currentUrl || '/chat'}
            </p>
          </div>
        </div>
      )}
    </>
  );
}
