'use client';

import { Activity, AlertTriangle, FileText, FileX, Navigation, MapPin, Loader2, Sparkles, Building, ChevronRight, ArrowRight, ShieldAlert, Globe, User, MessageSquare, LogIn, UserPlus, X, Smartphone } from 'lucide-react';
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
import { MobileDownloadSection } from '@/components/ui/MobileDownloadSection';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

// Code-splitting heavy dashboard and drawer components for low-end devices
const NationalDashboardPage = dynamic(() => import('./national-dashboard/page'), {
  ssr: false,
  loading: () => (
    <div className="min-h-screen w-full flex items-center justify-center bg-[#090d1a]">
      <Loader2 className="w-8 h-8 animate-spin text-orange-500" />
    </div>
  ),
});

const LaporSarDrawer = dynamic(
  () => import('@/components/layout/LaporSarDrawer').then((m) => m.LaporSarDrawer),
  { ssr: false }
);

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

  const filteredTenants = publicTenants.filter((tenant: any) => tenant.slug !== 'pusat');

  const mapLocations = filteredTenants
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

  return (
    <div className="min-h-screen w-screen relative overflow-x-hidden bg-gradient-to-br from-slate-50 via-white to-slate-50/50 font-sans flex flex-col justify-between">
      {/* Dynamic Background Glowing Blobs for Premium Light Theme */}
      <div className="absolute top-[-10%] left-[-10%] w-[600px] h-[600px] rounded-full bg-gradient-to-tr from-orange-400/5 to-red-500/5 blur-[130px] pointer-events-none z-0" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[700px] h-[700px] rounded-full bg-gradient-to-tr from-blue-500/5 to-orange-400/5 blur-[150px] pointer-events-none z-0" />

      {/* 1. Header Bar */}
      <header className="w-full z-10 bg-white/80 backdrop-blur-md border-b border-slate-200/80 py-4 px-6 sm:px-8 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-3">
          <div className="inline-flex items-center justify-center shrink-0">
            <img 
              src="/logo.png" 
              alt="Logo BASARNAS" 
              className="w-10 h-10 object-contain" 
            />
          </div>
          <div>
            <span className="text-[9px] uppercase font-black tracking-[0.2em] text-orange-550 block leading-none font-sans">Badan Nasional Pencarian dan Pertolongan</span>
            <h1 className="text-sm font-black text-slate-800 tracking-tight mt-1 font-sans">
              Portal <span className="bg-gradient-to-r from-orange-500 to-red-600 bg-clip-text text-transparent">Lapor SAR</span>
            </h1>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <span className="hidden md:flex items-center gap-1.5 px-3 py-1 bg-green-50 border border-green-150 rounded-full text-[10px] font-extrabold text-green-600">
            <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
            Sistem Siaga Aktif
          </span>

          <button
            onClick={() => {
              const el = document.getElementById('mobile-download-section');
              if (el) el.scrollIntoView({ behavior: 'smooth' });
            }}
            className="hidden sm:flex items-center gap-1.5 px-3.5 py-1.5 bg-orange-50 hover:bg-orange-100 border border-orange-200 rounded-xl text-[11px] font-extrabold text-orange-700 transition-all cursor-pointer"
          >
            <Smartphone className="w-3.5 h-3.5 text-orange-600" />
            <span>App Mobile</span>
          </button>

          <button
            onClick={() => setIsAuthModalOpen(true)}
            className="px-5 py-1.5 bg-gradient-to-r from-orange-500 to-red-600 hover:from-orange-600 hover:to-red-700 text-white font-extrabold text-[11px] sm:text-xs rounded-xl shadow-md shadow-orange-500/10 transition-all cursor-pointer flex items-center gap-1"
          >
            Masuk
          </button>
        </div>
      </header>

      {/* 2. Main Content Area */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-6 sm:px-8 py-10 lg:py-16 flex flex-col justify-center gap-12 z-10">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-14 items-stretch w-full">
          {/* Left Column: Widget Promotion Copy & CTA */}
          <div className="lg:col-span-6 space-y-6 text-left flex flex-col justify-center">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-orange-50 border border-orange-100 text-[10px] sm:text-xs font-bold text-orange-600">
                <Globe className="w-3.5 h-3.5" /> Integrasi Widget Lapor SAR
              </div>
            </div>
            
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-black text-slate-900 tracking-tight leading-tight font-sans">
              Hadirkan Tombol Darurat <br />
              <span className="bg-gradient-to-r from-orange-500 via-orange-600 to-red-600 bg-clip-text text-transparent">
                Lapor SAR di Web Anda
              </span>
            </h2>
            
            <p className="text-sm sm:text-base text-slate-500 font-medium leading-relaxed max-w-xl">
              Bantu tingkatkan keselamatan warga di lingkungan Anda. Instansi pemerintah, desa, pengelola wisata, media online, atau komunitas kini dapat mengintegrasikan widget resmi Lapor SAR secara gratis. Laporan darurat warga akan langsung terhubung ke Command Center BASARNAS setempat.
            </p>

            <div className="p-6 bg-white/80 backdrop-blur-sm border border-slate-200/80 rounded-2xl shadow-sm space-y-4 max-w-xl">
              <h3 className="text-sm font-extrabold text-slate-800 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-orange-500" /> Benefit Integrasi Widget:
              </h3>
              <ul className="text-xs text-slate-500 space-y-2.5 font-medium">
                <li className="flex items-start gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-orange-500 mt-1.5 shrink-0" />
                  <span><strong>Respons Cepat 24/7</strong>: Laporan langsung terdistribusi ke unit SAR terdekat berdasarkan deteksi lokasi otomatis.</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-orange-500 mt-1.5 shrink-0" />
                  <span><strong>Tanpa Instalasi Rumit</strong>: Cukup salin dan tempel sebaris kode iframe ke dalam platform CMS/website Anda.</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-orange-500 mt-1.5 shrink-0" />
                  <span><strong>Dashboard Pelapor</strong>: Kelola status widget Anda, lihat statistik laporan masuk, dan unduh panduan operasional.</span>
                </li>
              </ul>

              <div className="pt-3">
                <button
                  onClick={() => router.push('/widget-registration')}
                  className="w-full sm:w-auto px-6 py-3 bg-gradient-to-r from-orange-500 to-red-600 hover:from-orange-600 hover:to-red-700 text-white font-extrabold text-xs rounded-xl flex items-center justify-center gap-2 shadow-md shadow-orange-500/10 transition-all cursor-pointer font-sans"
                >
                  Daftar & Dapatkan Widget Gratis <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          {/* Right Column: Incident Map & UPT Tabs */}
          <div className="lg:col-span-6 space-y-6 flex flex-col justify-between">
            {/* Incident Map Box */}
            <div className="bg-white rounded-3xl border border-slate-200/80 p-3 shadow-md relative group flex-1 flex flex-col">
              <div className="h-[300px] min-h-[300px] w-full rounded-2xl overflow-hidden relative z-0 flex-1">
                <DashboardMap 
                  reports={publicReports} 
                  locations={mapLocations}
                  isPublic={true}
                />
              </div>
            </div>

            {/* Tabbed Info Panel */}
            <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden flex flex-col h-[280px]">
              {/* Tabs Selector */}
              <div className="flex border-b border-slate-100 bg-slate-50/50 p-1">
                <button
                  onClick={() => setActiveTab('reports')}
                  className={`flex-1 py-2 text-xs font-extrabold rounded-xl transition-all cursor-pointer flex items-center justify-center gap-2 ${
                    activeTab === 'reports'
                      ? 'bg-white text-slate-800 shadow-sm border border-slate-200/40'
                      : 'text-slate-400 hover:text-slate-600'
                  }`}
                >
                  <Activity className="w-3.5 h-3.5" /> Laporan Aktif ({publicReports.length})
                </button>
                <button
                  onClick={() => setActiveTab('tenants')}
                  className={`flex-1 py-2 text-xs font-extrabold rounded-xl transition-all cursor-pointer flex items-center justify-center gap-2 ${
                    activeTab === 'tenants'
                      ? 'bg-white text-slate-800 shadow-sm border border-slate-200/40'
                      : 'text-slate-400 hover:text-slate-600'
                  }`}
                >
                  <Building className="w-3.5 h-3.5" /> Kantor UPT / SAR ({filteredTenants.length})
                </button>
              </div>

              {/* Tab Contents */}
              <div className="p-4 flex-1 overflow-y-auto">
                {activeTab === 'reports' ? (
                  <div className="space-y-3">
                    {isLoadingReports ? (
                      Array(3).fill(0).map((_, i) => (
                        <div key={i} className="w-full h-14 bg-slate-50 animate-pulse rounded-xl" />
                      ))
                    ) : isErrorReports ? (
                      <div className="text-center py-8 text-xs font-bold text-red-500">
                        Gagal memuat data laporan aktif.
                      </div>
                    ) : publicReports.length > 0 ? (
                      publicReports.map((report: any) => (
                        <div 
                          key={report.id} 
                          className="p-3 border border-slate-100 rounded-xl bg-slate-50/20 flex items-center justify-between gap-3 text-left"
                        >
                          <div className="space-y-1">
                            <h4 className="font-extrabold text-slate-800 text-xs">
                              {report.jenis_kejadian}
                            </h4>
                            <p className="text-[10px] text-slate-550 font-mono">
                              No: {report.no_laporan}
                            </p>
                            <div className="flex flex-wrap items-center gap-2 text-[10px] text-slate-450 mt-1">
                              <span className="flex items-center gap-1">
                                <MapPin className="w-3 h-3 text-slate-400" /> {report.lokasi_teks || 'Lokasi tidak diketahui'}
                              </span>
                              <span>•</span>
                              <span className="text-orange-600 font-bold">
                                {report.tenant_name}
                              </span>
                            </div>
                          </div>
                          <span className={`inline-flex px-2 py-0.5 rounded-md text-[9px] font-extrabold tracking-wider uppercase ${
                            report.status === 'PENDING'
                              ? 'bg-orange-50 text-orange-700 border border-orange-100'
                              : 'bg-red-50 text-red-750 border border-red-100'
                          }`}>
                            {report.status}
                          </span>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-12 text-xs font-bold text-slate-450">
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

        {/* 2.5 Mobile App Download Hero Section */}
        <div id="mobile-download-section">
          <MobileDownloadSection />
        </div>
      </main>

      {/* 3. Footer */}
      <footer className="w-full z-10 bg-slate-50 border-t border-slate-200/60 py-6 px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-4 text-[10px] font-bold text-slate-450">
          <a href="/widget-registration" className="hover:text-orange-550 transition-colors flex items-center gap-1">
            <Globe className="w-3.5 h-3.5 text-slate-400" /> Pendaftaran Widget
          </a>
          <span>•</span>
          <a href="/help-center" className="hover:text-orange-550 transition-colors">
            Pusat Bantuan
          </a>
        </div>
        <p className="text-[10px] text-slate-450 font-semibold font-sans">
          © {new Date().getFullYear()} BASARNAS. All rights reserved.
        </p>
      </footer>

      {/* Auth Selector Modal */}
      {isAuthModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
          {/* Animated Modal Container */}
          <div className="bg-white rounded-3xl border border-slate-200/80 shadow-2xl w-full max-w-sm overflow-hidden relative p-6 space-y-6">
            
            {/* Header / Close button */}
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-black text-slate-800 uppercase tracking-wider">Akses Portal</h3>
              <button 
                onClick={() => setIsAuthModalOpen(false)}
                className="p-1.5 hover:bg-slate-100 rounded-xl text-slate-400 hover:text-slate-650 transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Title & Desc */}
            <div className="text-center space-y-1">
              <h2 className="text-xl font-black text-slate-900">Selamat Datang</h2>
              <p className="text-xs text-slate-500 font-medium">Pilih langkah yang ingin Anda lakukan untuk melanjutkan ke portal Lapor SAR.</p>
            </div>

            {/* Option Cards */}
            <div className="grid grid-cols-2 gap-4">
              {/* Option 1: Masuk (Login) */}
              <button
                onClick={() => {
                  setIsAuthModalOpen(false);
                  window.open('/login', '_blank');
                }}
                className="p-5 border border-slate-100 rounded-2xl bg-slate-50/40 hover:border-orange-200 hover:bg-orange-50/20 text-center flex flex-col items-center justify-center gap-3 transition-all hover:scale-[1.02] shadow-sm group cursor-pointer"
              >
                <div className="w-12 h-12 rounded-xl bg-orange-50 text-orange-600 flex items-center justify-center group-hover:bg-orange-100 transition-colors">
                  <LogIn className="w-6 h-6" />
                </div>
                <span className="font-extrabold text-slate-800 text-sm">Masuk</span>
              </button>

              {/* Option 2: Daftar (Register) */}
              <button
                onClick={() => {
                  setIsAuthModalOpen(false);
                  window.open('/register', '_blank');
                }}
                className="p-5 border border-slate-100 rounded-2xl bg-slate-50/40 hover:border-red-200 hover:bg-red-50/20 text-center flex flex-col items-center justify-center gap-3 transition-all hover:scale-[1.02] shadow-sm group cursor-pointer"
              >
                <div className="w-12 h-12 rounded-xl bg-red-50 text-red-655 flex items-center justify-center group-hover:bg-red-100 transition-colors">
                  <UserPlus className="w-6 h-6" />
                </div>
                <span className="font-extrabold text-slate-800 text-sm">Daftar</span>
              </button>
            </div>
          </div>
        </div>
      )}
      <LaporSarDrawer />
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
    { label: 'Kejadian Menunggu Validasi', value: statsData?.pending_validation ?? '0', icon: AlertTriangle, color: 'text-orange-500', bg: 'bg-orange-50' },
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
                        ? 'bg-orange-50 text-orange-700 border border-orange-100'
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
  const router = useRouter();

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const urlParams = new URLSearchParams(window.location.search);
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
              setTenantSlug(payload.tenant_slug || null);
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

  if (isTenant === null) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-[#090d1a]">
        <Loader2 className="w-8 h-8 animate-spin text-orange-500" />
      </div>
    );
  }

  // Root domain (SaaS Landing Page) when not logged in
  if (!isTenant && !isAuthenticated) {
    return <SaasPortalLandingPage />;
  }

  if (isAuthenticated === null) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-[#090d1a]">
        <Loader2 className="w-8 h-8 animate-spin text-orange-500" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return null; // Will redirect via useEffect if isTenant is true
  }

  // If authenticated, determine which dashboard to show
  if (tenantSlug === 'pusat' || tenantSlug === null) {
    return <NationalDashboardPage />;
  }

  return <CommandCenterDashboard />;
}


