'use client';

import { Activity, AlertTriangle, FileText, FileX, Navigation, MapPin, Loader2, Building, ChevronRight, ArrowRight, ShieldAlert, Globe, User, MessageSquare, LogIn, UserPlus, X, Phone } from 'lucide-react';
import { motion } from 'framer-motion';
import { useDashboardData } from '@/hooks/useDashboardData';
import { SkeletonLoader } from '@/components/ui/SkeletonLoader';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { useQuery } from '@tanstack/react-query';
import dynamic from 'next/dynamic';
import { getLocations, getIdentity, getPublicMapReports, getTenantSlug, getPublicTenants, getBackendUrl } from '@/lib/api';
import { decodeJwt } from '@/lib/utils';
import DashboardMap from '@/components/DashboardMap';
import { useLaporSar } from '@/providers/LaporSarProvider';
import { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';

// Code-splitting heavy dashboard and drawer components for low-end devices
const NationalDashboardPage = dynamic(() => import('./national-dashboard/page'), {
  ssr: false,
  loading: () => (
    <div className="min-h-screen w-full flex items-center justify-center bg-gray-50">
      <Loader2 className="w-8 h-8 animate-spin text-slate-500" />
    </div>
  ),
});

// --- Helper Cookie Reader ---
const getCookie = (name: string) => {
  if (typeof document === 'undefined') return null;
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(';').shift() || null;
  return null;
};


// --- Portal Landing Page (Root Domain) ---
function SaasPortalLandingPage() {
  const router = useRouter();
  const [isEmergencyModalOpen, setIsEmergencyModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'reports' | 'tenants'>('reports');
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);

  const { data: publicReports = [], isLoading: isLoadingReports, isError: isErrorReports } = useQuery({
    queryKey: ['publicMapReports'],
    queryFn: getPublicMapReports,
    refetchInterval: 30000, // refresh every 30s
  });

  const { data: publicTenants = [], isLoading: isLoadingTenants, isError: isErrorTenants } = useQuery({
    queryKey: ['publicTenants'],
    queryFn: getPublicTenants,
  });

  const filteredTenants = useMemo(() => {
    return Array.isArray(publicTenants)
      ? publicTenants.filter((tenant: any) => tenant.slug !== 'pusat')
      : [];
  }, [publicTenants]);

  const mapLocations = useMemo(() => {
    return filteredTenants
      .filter((t: any) => t.lat !== null && t.lng !== null && !isNaN(parseFloat(t.lat)) && !isNaN(parseFloat(t.lng)))
      .map((t: any, index: number) => ({
        id: t.slug || index,
        name: t.name,
        type: 'Kantor SAR',
        lat: parseFloat(t.lat),
        lng: parseFloat(t.lng),
        address: t.address,
        icon: t.logo_path || '🏢'
      }));
  }, [filteredTenants]);

  return (
    <div className="min-h-screen w-screen relative overflow-x-hidden bg-slate-50/60 font-sans flex flex-col justify-between">
      {/* 1. Header Bar */}
      <header className="w-full z-10 bg-white/95 backdrop-blur-md border-b border-slate-200 py-3.5 px-6 sm:px-8 flex items-center justify-between shadow-xs">
        <div className="flex items-center gap-3">
          <div className="inline-flex items-center justify-center shrink-0">
            <img 
              src="/logo.png" 
              alt="Logo BASARNAS" 
              className="w-10 h-10 object-contain" 
            />
          </div>
          <div>
            <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500 block leading-tight">
              Badan Nasional Pencarian dan Pertolongan
            </span>
            <h1 className="text-sm font-bold text-slate-900 tracking-tight flex items-center gap-1.5 mt-0.5">
              <span>Portal Terpadu</span>
              <span className="text-slate-900 font-extrabold">Lapor SAR</span>
            </h1>
          </div>
        </div>
        
        <div className="flex items-center gap-2.5">
          <span className="hidden md:flex items-center gap-1.5 px-3 py-1 bg-emerald-50 border border-emerald-200 rounded-full text-[11px] font-semibold text-emerald-700">
            <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
            Siaga 24/7
          </span>

          <button
            onClick={() => setIsAuthModalOpen(true)}
            className="px-4 py-1.5 bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs rounded-xl shadow-xs transition-colors cursor-pointer flex items-center gap-1.5"
          >
            <LogIn className="w-3.5 h-3.5" />
            <span>Masuk Petugas</span>
          </button>
        </div>
      </header>

      {/* 2. Main Content Area */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-6 sm:px-8 py-8 lg:py-12 flex flex-col justify-center gap-10 z-10">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-stretch w-full">
          {/* Left Column: Mission Statement, Emergency Action & Key Pillars */}
          <div className="lg:col-span-6 space-y-6 text-left flex flex-col justify-center">
            <div className="space-y-3">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-100 border border-slate-200 text-xs font-semibold text-slate-700">
                <ShieldAlert className="w-3.5 h-3.5 text-slate-700" /> Pusat Pengendalian & Komando Operasi SAR
              </div>
              
              <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-slate-900 tracking-tight leading-tight">
                Sistem Pelaporan Terpadu <br />
                <span className="text-slate-900">
                  Pencarian & Pertolongan
                </span>
              </h2>
              
              <p className="text-sm sm:text-base text-slate-600 font-normal leading-relaxed max-w-xl">
                Kanal resmi Badan Nasional Pencarian dan Pertolongan (BASARNAS) untuk penerimaan laporan marabahaya dari masyarakat, koordinasi SAR terpadu, dan pemantauan situasi insiden di seluruh Indonesia.
              </p>
            </div>

            {/* Quick Action Buttons */}
            <div className="flex flex-wrap items-center gap-3 pt-1">
              <button
                onClick={() => setIsEmergencyModalOpen(true)}
                className="px-6 py-3.5 bg-rose-600 hover:bg-rose-700 text-white font-semibold text-sm rounded-xl flex items-center justify-center gap-2 shadow-sm transition-all cursor-pointer"
              >
                <AlertTriangle className="w-4 h-4 text-white" />
                <span>Laporkan Musibah (SOS)</span>
              </button>
              <button
                onClick={() => router.push('/widget-registration')}
                className="px-5 py-3.5 bg-white hover:bg-slate-100 border border-slate-200 text-slate-700 font-semibold text-sm rounded-xl flex items-center justify-center gap-2 transition-all cursor-pointer shadow-xs"
              >
                <Globe className="w-4 h-4 text-slate-500" />
                <span>Integrasi Widget Web</span>
              </button>
            </div>

            {/* Service Pillars Card */}
            <div className="p-5 bg-white border border-slate-200 rounded-2xl shadow-xs space-y-3 max-w-xl">
              <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
                <Activity className="w-4 h-4 text-slate-700" /> Kapabilitas Sistem Lapor SAR
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs">
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                  <p className="font-semibold text-slate-800">Pelaporan Cepat</p>
                  <p className="text-[11px] text-slate-500 mt-1 leading-normal">Deteksi koordinat GPS otomatis tanpa hambatan registrasi yang rumit.</p>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                  <p className="font-semibold text-slate-800">Ekstraksi Otomatis</p>
                  <p className="text-[11px] text-slate-500 mt-1 leading-normal">Penerjemahan teks insiden ke format PDTW standar Basarnas.</p>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                  <p className="font-semibold text-slate-800">Multi-Channel Terpadu</p>
                  <p className="text-[11px] text-slate-500 mt-1 leading-normal">Tersedia melalui Web Drawer, WhatsApp Bot, dan Telegram Bot.</p>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                  <p className="font-semibold text-slate-800">Disposisi Instan</p>
                  <p className="text-[11px] text-slate-500 mt-1 leading-normal">Distribusi langsung ke Kantor SAR dan Pos SAR penanggung jawab terdekat.</p>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Incident Map & UPT Tabs */}
          <div className="lg:col-span-6 space-y-5 flex flex-col justify-between">
            {/* Incident Map Box */}
            <div className="bg-white rounded-2xl border border-slate-200 p-2.5 shadow-xs relative flex-1 flex flex-col">
              <div className="h-[300px] min-h-[300px] w-full rounded-xl overflow-hidden relative z-0 flex-1">
                <DashboardMap 
                  reports={publicReports} 
                  locations={mapLocations}
                  isPublic={true}
                />
              </div>
            </div>

            {/* Tabbed Info Panel */}
            <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden flex flex-col h-[280px]">
              {/* Tabs Selector */}
              <div className="flex border-b border-slate-200 bg-slate-50 p-1">
                <button
                  onClick={() => setActiveTab('reports')}
                  className={`flex-1 py-2 text-xs font-semibold rounded-xl transition-all cursor-pointer flex items-center justify-center gap-2 ${
                    activeTab === 'reports'
                      ? 'bg-white text-slate-900 shadow-xs border border-slate-200/80 font-bold'
                      : 'text-slate-500 hover:text-slate-800'
                  }`}
                >
                  <Activity className="w-3.5 h-3.5 text-slate-700" /> Laporan Aktif ({publicReports.length})
                </button>
                <button
                  onClick={() => setActiveTab('tenants')}
                  className={`flex-1 py-2 text-xs font-semibold rounded-xl transition-all cursor-pointer flex items-center justify-center gap-2 ${
                    activeTab === 'tenants'
                      ? 'bg-white text-slate-900 shadow-xs border border-slate-200/80 font-bold'
                      : 'text-slate-500 hover:text-slate-800'
                  }`}
                >
                  <Building className="w-3.5 h-3.5 text-slate-600" /> Kantor UPT / SAR ({filteredTenants.length})
                </button>
              </div>

              {/* Tab Contents */}
              <div className="p-4 flex-1 overflow-y-auto">
                {activeTab === 'reports' ? (
                  <div className="space-y-2.5">
                    {isLoadingReports ? (
                      Array(3).fill(0).map((_, i) => (
                        <div key={i} className="w-full h-14 bg-slate-50 animate-pulse rounded-xl" />
                      ))
                    ) : isErrorReports ? (
                      <div className="text-center py-8 text-xs font-semibold text-rose-600">
                        Gagal memuat data laporan aktif.
                      </div>
                    ) : publicReports.length > 0 ? (
                      publicReports.map((report: any) => (
                        <div 
                          key={report.id} 
                          className="p-3 border border-slate-100 rounded-xl bg-slate-50/50 flex items-center justify-between gap-3 text-left hover:border-slate-200 transition-colors"
                        >
                          <div className="space-y-0.5">
                            <h4 className="font-bold text-slate-800 text-xs">
                              {report.jenis_kejadian}
                            </h4>
                            <p className="text-[10px] text-slate-500 font-mono">
                              No: {report.no_laporan}
                            </p>
                            <div className="flex flex-wrap items-center gap-2 text-[10px] text-slate-500 mt-1">
                              <span className="flex items-center gap-1">
                                <MapPin className="w-3 h-3 text-slate-400" /> {report.lokasi_teks || 'Lokasi tidak diketahui'}
                              </span>
                              <span>•</span>
                              <span className="text-slate-700 font-semibold">
                                {report.tenant_name}
                              </span>
                            </div>
                          </div>
                          <span className={`inline-flex px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase ${
                            report.status === 'PENDING'
                              ? 'bg-amber-50 text-amber-800 border border-amber-200'
                              : 'bg-rose-50 text-rose-800 border border-rose-200'
                          }`}>
                            {report.status}
                          </span>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-12 text-xs font-medium text-slate-400">
                        Tidak ada laporan aktif saat ini.
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="space-y-3">
                    {isLoadingTenants ? (
                      Array(3).fill(0).map((_, i) => (
                        <div key={i} className="w-full h-16 bg-slate-50 animate-pulse rounded-xl" />
                      ))
                    ) : isErrorTenants ? (
                      <div className="text-center py-8 text-xs font-bold text-red-500 col-span-full">
                        Gagal memuat data kantor UPT.
                      </div>
                    ) : filteredTenants.length > 0 ? (
                      filteredTenants.map((tenant: any) => (
                        <div 
                          key={tenant.slug} 
                          className="p-4 border border-slate-100 rounded-2xl bg-slate-50/20 flex gap-4 text-left hover:border-slate-200 hover:bg-slate-50/50 transition-all shadow-sm"
                        >
                          <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center shrink-0 overflow-hidden border border-slate-200">
                            <img 
                              src={tenant.logo_path ? `${getBackendUrl().replace(/\/api\/?$/, '')}/${tenant.logo_path}` : '/logo.png'} 
                              alt={`Logo ${tenant.name}`} 
                              className="w-10 h-10 object-contain"
                              onError={(e) => {
                                (e.target as HTMLImageElement).src = '/logo.png';
                              }}
                            />
                          </div>
                          <div className="flex-1 min-w-0 space-y-1">
                            <h4 className="font-extrabold text-slate-800 text-xs truncate">
                              {tenant.name}
                            </h4>
                            <p className="text-[10px] text-slate-550 flex items-start gap-1 font-medium leading-relaxed">
                              <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0 mt-0.5" />
                              <span className="line-clamp-2">{tenant.address || 'Wilayah Operasional'}</span>
                            </p>
                            {tenant.wa_link && (
                              <div className="pt-1">
                                <a
                                  href={tenant.wa_link}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-green-50 hover:bg-green-100 border border-green-150 rounded-lg text-[10px] font-extrabold text-green-600 transition-colors"
                                >
                                  <MessageSquare className="w-3 h-3 text-green-500" />
                                  Hubungi WA ({tenant.wa_phone})
                                </a>
                              </div>
                            )}
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-12 text-xs font-bold text-slate-450 col-span-full">
                        Belum ada kantor SAR terdaftar.
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

      </main>

      {/* 3. Footer */}
      <footer className="w-full z-10 bg-slate-50 border-t border-slate-200/60 py-6 px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-4 text-[10px] font-bold text-slate-450">
          <a href="/widget-registration" className="hover:text-slate-900 transition-colors flex items-center gap-1">
            <Globe className="w-3.5 h-3.5 text-slate-400" /> Pendaftaran Widget
          </a>
          <span>•</span>
          <a href="/help-center" className="hover:text-slate-900 transition-colors">
            Pusat Bantuan
          </a>
        </div>
        <p className="text-[10px] text-slate-450 font-semibold font-sans">
          © {new Date().getFullYear()} BASARNAS. All rights reserved.
        </p>
      </footer>

      {/* Auth Selector Modal */}
      {isAuthModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xl w-full max-w-sm overflow-hidden relative p-6 space-y-5">
            {/* Header / Close button */}
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Akses Portal</span>
              <button 
                onClick={() => setIsAuthModalOpen(false)}
                className="p-1 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Title & Desc */}
            <div className="space-y-1 text-center">
              <h3 className="text-lg font-bold text-slate-900">Portal Petugas & Mitra</h3>
              <p className="text-xs text-slate-500 leading-normal">Pilih jenis akses untuk melanjutkan ke Command Center atau pendaftaran mitra.</p>
            </div>

            {/* Option Cards */}
            <div className="grid grid-cols-2 gap-3 pt-1">
              {/* Option 1: Masuk (Login) */}
              <button
                onClick={() => {
                  setIsAuthModalOpen(false);
                  router.push('/login');
                }}
                className="p-4 border border-slate-200 rounded-xl bg-slate-50 hover:border-slate-300 hover:bg-slate-100/60 text-center flex flex-col items-center justify-center gap-2.5 transition-colors group cursor-pointer shadow-xs"
              >
                <div className="w-10 h-10 rounded-lg bg-white border border-slate-200 text-slate-750 flex items-center justify-center group-hover:border-slate-300 group-hover:bg-slate-50 transition-colors">
                  <LogIn className="w-5 h-5" />
                </div>
                <span className="font-bold text-slate-800 text-xs">Masuk Akun</span>
              </button>

              {/* Option 2: Daftar (Register) */}
              <button
                onClick={() => {
                  setIsAuthModalOpen(false);
                  router.push('/register');
                }}
                className="p-4 border border-slate-200 rounded-xl bg-slate-50 hover:border-slate-300 hover:bg-slate-100/60 text-center flex flex-col items-center justify-center gap-2.5 transition-colors group cursor-pointer shadow-xs"
              >
                <div className="w-10 h-10 rounded-lg bg-white border border-slate-200 text-slate-700 flex items-center justify-center group-hover:border-slate-300 group-hover:bg-slate-50 transition-colors">
                  <UserPlus className="w-5 h-5" />
                </div>
                <span className="font-bold text-slate-800 text-xs">Registrasi</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Emergency Hotline Modal (SOS) */}
      {isEmergencyModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-xs animate-in fade-in duration-200">
          <div 
            className="fixed inset-0" 
            onClick={() => setIsEmergencyModalOpen(false)} 
          />
          <div className="relative w-full max-w-md bg-white border border-slate-200 rounded-2xl shadow-2xl p-6 z-10 space-y-5 animate-in zoom-in-95 duration-200">
            {/* Header */}
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-red-50 border border-red-200 rounded-xl text-red-600">
                  <AlertTriangle className="w-5 h-5 animate-pulse" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-900 text-base">Saluran Siaga Darurat SAR</h3>
                  <p className="text-xs text-slate-500 font-medium mt-0.5">Badan Nasional Pencarian & Pertolongan</p>
                </div>
              </div>
              <button 
                onClick={() => setIsEmergencyModalOpen(false)}
                className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Description */}
            <p className="text-xs text-slate-600 leading-relaxed">
              Untuk kondisi musibah marabahaya yang mengancam keselamatan jiwa manusia (kecelakaan laut, penerbangan, bencana, atau evakuasi darurat), segera hubungi pos siaga SAR melalui:
            </p>

            {/* Emergency Hotline 115 Card */}
            <a
              href="tel:115"
              className="w-full p-4 rounded-xl bg-gradient-to-r from-rose-600 to-red-600 text-white flex items-center justify-between shadow-md hover:from-rose-700 hover:to-red-700 transition-all group cursor-pointer"
            >
              <div className="flex items-center gap-3.5">
                <div className="p-3 bg-white/20 rounded-xl">
                  <Phone className="w-6 h-6 text-white animate-bounce" />
                </div>
                <div className="text-left">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-red-100 block">Call Center Bebas Pulsa (24 Jam)</span>
                  <span className="text-2xl font-extrabold tracking-tight">115</span>
                </div>
              </div>
              <ArrowRight className="w-5 h-5 text-white/80 group-hover:translate-x-1 transition-transform" />
            </a>

            {/* Additional Info Box */}
            <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200/80 text-[11px] text-slate-600 space-y-1">
              <p className="font-semibold text-slate-800">Pelaporan Berbasis Digital / Web:</p>
              <p className="text-slate-500">
                Layanan pelaporan daring interaktif dapat diakses melalui website resmi mitra (Pemda/Instansi Terkait) yang telah terintegrasi dengan Widget Lapor SAR.
              </p>
            </div>

            {/* Close Button */}
            <button
              onClick={() => setIsEmergencyModalOpen(false)}
              className="w-full py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs rounded-xl transition-colors cursor-pointer"
            >
              Tutup
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// --- Dashboard Component (Subdomain resolved) ---
function CommandCenterDashboard() {
  const { useStatsQuery, useReportsQuery } = useDashboardData();
  const { setSelectedGlobalReport, setIsGlobalReportDetailOpen } = useLaporSar();
  
  const { data: statsData, isLoading: isLoadingStats, isError: isErrorStats, refetch: refetchStats } = useStatsQuery();
  const { data: reportsData = [], isLoading: isLoadingReports, isError: isErrorReports, refetch: refetchReports } = useReportsQuery();
  
  const { data: locationsData = [], isLoading: isLoadingLocations } = useQuery({
    queryKey: ['locations'],
    queryFn: getLocations,
  });

  const { data: identityData } = useQuery({
    queryKey: ['identity'],
    queryFn: getIdentity,
  });

  const stats = [
    { label: 'Total Laporan Hari Ini', value: statsData?.total_today ?? '0', icon: Activity, color: 'text-blue-500', bg: 'bg-blue-50' },
    { label: 'Kejadian Menunggu Validasi', value: statsData?.pending_validation ?? '0', icon: AlertTriangle, color: 'text-amber-600', bg: 'bg-amber-50' },
    { label: 'Laporan Aktif', value: statsData?.laporan_aktif ?? '0', icon: FileText, color: 'text-red-500', bg: 'bg-red-50' },
    { label: 'Laporan tidak aktif/salah lapor', value: statsData?.inactive_or_false_reports ?? '0', icon: FileX, color: 'text-slate-500', bg: 'bg-slate-50' },
  ];

  return (
    <div className="space-y-6 w-full">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
          Selamat Datang di Lapor SAR {identityData?.identitas_nama_instansi ? `- ${identityData.identitas_nama_instansi}` : ''}
        </h1>
        <p className="text-gray-500 mt-1">Ringkasan aktivitas command center hari ini.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {isErrorStats ? (
          <div className="col-span-full">
            <ErrorState message="Gagal memuat statistik." onRetry={refetchStats} />
          </div>
        ) : (
          stats.map((stat, index) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
              className="bg-white rounded-2xl p-6 border border-gray-100 shadow-sm"
            >
              <div className="flex items-center gap-4">
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${stat.bg}`}>
                  <stat.icon className={`w-6 h-6 ${stat.color}`} />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-500">{stat.label}</p>
                  {isLoadingStats ? (
                    <SkeletonLoader className="w-16 h-8 mt-1" />
                  ) : (
                    <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
                  )}
                </div>
              </div>
            </motion.div>
          ))
        )}
      </div>

      <div className="bg-white rounded-2xl border border-gray-150 p-5 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-gray-50 pb-3">
          <div>
            <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
              Peta Pemantauan Operasi SAR (Live Incident Map)
            </h2>
            <p className="text-xs text-gray-500 mt-0.5">Memantau sebaran lokasi musibah darurat dan kesiapan Pos/Unit Siaga SAR di wilayah kerja.</p>
          </div>
          <div className="flex items-center gap-4 text-[10px] sm:text-xs font-bold shrink-0">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-red-500 block animate-pulse" />
              <span className="text-gray-600">Musibah Aktif</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-500 block" />
              <span className="text-gray-600">Pos / Kantor SAR</span>
            </div>
          </div>
        </div>
        <div className="h-[400px] w-full rounded-2xl overflow-hidden relative border border-gray-100 z-0">
          <DashboardMap 
            reports={reportsData} 
            locations={locationsData} 
            kmlPath={identityData?.identitas_kml_path} 
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6">
        <div className="bg-white rounded-2xl border border-gray-150 p-6 shadow-sm min-h-[400px] flex flex-col">
          <h2 className="text-lg font-bold text-gray-900 mb-6">Laporan Masuk Terkini</h2>
          
          <div className="space-y-4 flex-1">
            {isLoadingReports ? (
              Array(3).fill(0).map((_, i) => <SkeletonLoader key={i} className="w-full h-16" />)
            ) : isErrorReports ? (
              <ErrorState message="Gagal memuat laporan terkini." onRetry={refetchReports} />
            ) : reportsData?.length > 0 ? (
              reportsData.slice(0, 5).map((report: any) => (
                  <div 
                    key={report.id} 
                    onClick={() => {
                      setSelectedGlobalReport(report);
                      setIsGlobalReportDetailOpen(true);
                    }}
                    className="p-4 border border-gray-100 rounded-2xl hover:bg-gray-50/50 transition-colors flex items-center justify-between gap-4 cursor-pointer"
                  >
                    <div className="space-y-1">
                      <h3 className="font-bold text-gray-900 text-sm leading-snug">
                        {report.jenis_kejadian} - {report.no_laporan}
                      </h3>
                      <p className="text-xs text-gray-550 flex items-center gap-1">
                        <MapPin className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                        {report.lokasi_teks}
                      </p>
                    </div>
                    <span className={`inline-flex px-2.5 py-1 rounded-lg text-xs font-bold tracking-wider ${
                      report.status === 'PENDING'
                        ? 'bg-amber-50 text-amber-800 border border-amber-200'
                        : report.status === 'AKTIF'
                        ? 'bg-red-50 text-red-700 border border-red-100'
                        : 'bg-green-50 text-green-700 border border-green-100'
                    }`}>
                      {report.status}
                    </span>
                  </div>
                ))
            ) : (
              <EmptyState message="Belum ada laporan masuk hari ini." />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// --- Main Conditionally Routed Home Component ---
export default function Home() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [isTenant, setIsTenant] = useState<boolean | null>(null);
  const [tenantSlug, setTenantSlug] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const urlParams = new URLSearchParams(window.location.search);
      const tokenFromUrl = urlParams.get('token');
      if (tokenFromUrl) {
        localStorage.setItem('token', tokenFromUrl);
        sessionStorage.removeItem('logging_out');
        const params = new URLSearchParams(window.location.search);
        params.delete('token');
        const searchStr = params.toString();
        const newUrl = window.location.pathname + (searchStr ? `?${searchStr}` : '');
        window.history.replaceState({}, document.title, newUrl);
      }

      const isLogout = urlParams.get('logout') === 'true';
      if (isLogout) {
        localStorage.removeItem('token');
        sessionStorage.removeItem('logging_out');
        const params = new URLSearchParams(window.location.search);
        params.delete('logout');
        const searchStr = params.toString();
        const newUrl = window.location.pathname + (searchStr ? `?${searchStr}` : '');
        window.history.replaceState({}, document.title, newUrl);
      }

      const tenant = getTenantSlug();
      setIsTenant(!!tenant);

      const token = localStorage.getItem('token');
      if (token) {
        setIsAuthenticated(true);
        try {
            const payload = decodeJwt(token);
            if (payload) {
              setUserRole(payload.role || null);
              setTenantSlug(tenant || payload.tenant_slug || null);
            }
        } catch (e) {
          console.error('Failed to parse token in Home component:', e);
        }
      } else {
        setIsAuthenticated(false);
        if (sessionStorage.getItem('logging_out') !== 'true') {
          if (tenant) {
            router.push('/login');
          }
        }
      }
    }
  }, [router]);

  // 1. Wait until authentication and tenant status are resolved from client/localStorage
  if (isAuthenticated === null || isTenant === null) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-gray-50">
        <Loader2 className="w-8 h-8 animate-spin text-slate-500" />
      </div>
    );
  }

  // 2. Unauthenticated state
  if (!isAuthenticated) {
    if (!isTenant) {
      return <SaasPortalLandingPage />;
    }
    return null; // Will redirect via useEffect if isTenant is true
  }

  // 3. Authenticated state:
  const cleanRole = userRole ? String(userRole).toLowerCase().replace(/[\s_-]/g, '') : '';
  const isSuperAdmin = cleanRole === 'superadmin';
  const isPusatOrGlobal = !tenantSlug || tenantSlug === 'pusat';

  // If Super Admin visits root path, automatically redirect to Administrator Panel (/admin)
  if (isSuperAdmin && isPusatOrGlobal) {
    router.replace('/admin');
    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-gray-50">
        <Loader2 className="w-8 h-8 animate-spin text-slate-500" />
      </div>
    );
  }

  // If Pusat Command Center, show National Monitoring Dashboard
  if (tenantSlug === 'pusat' || tenantSlug === null) {
    return <NationalDashboardPage />;
  }

  return <CommandCenterDashboard />;
}


