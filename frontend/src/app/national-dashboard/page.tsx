'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { getNationalReports, getNationalStats } from '@/lib/api';
import { 
  Activity, AlertTriangle, FileText, CheckCircle2, Navigation, MapPin, 
  Loader2, RefreshCw, Search, Filter, Globe, Calendar, Users, Heart,
  Anchor, Plane, User, ShieldAlert
} from 'lucide-react';
import { SkeletonLoader } from '@/components/ui/SkeletonLoader';
import { ErrorState } from '@/components/ui/ErrorState';
import { motion } from 'framer-motion';
import DashboardMap from '@/components/DashboardMap';

export default function NationalDashboardPage() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const router = useRouter();

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('token');
      if (token) {
        setIsAuthenticated(true);
      } else {
        setIsAuthenticated(false);
        router.push('/login');
      }
    }
  }, [router]);

  const [statusFilter, setStatusFilter] = useState('');
  const [jenisFilter, setJenisFilter] = useState('');
  const [tenantFilter, setTenantFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Debounce search query
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 400);
    return () => clearTimeout(handler);
  }, [searchQuery]);

  // Fetch National Stats
  const { 
    data: stats, 
    isLoading: isLoadingStats, 
    isError: isErrorStats, 
    refetch: refetchStats 
  } = useQuery({
    queryKey: ['nationalStats'],
    queryFn: getNationalStats,
    enabled: !!isAuthenticated,
    refetchInterval: 30000, // Refresh stats every 30 seconds
  });

  // Fetch National Reports with filters
  const { 
    data: reports = [], 
    isLoading: isLoadingReports, 
    isError: isErrorReports, 
    refetch: refetchReports 
  } = useQuery({
    queryKey: ['nationalReports', statusFilter, jenisFilter, tenantFilter, debouncedSearch],
    queryFn: () => getNationalReports({
      status: statusFilter || undefined,
      jenis_kejadian: jenisFilter || undefined,
      tenant_slug: tenantFilter || undefined,
      search: debouncedSearch || undefined,
      limit: 100
    }),
    enabled: !!isAuthenticated,
    refetchInterval: 30000, // Refresh reports list every 30 seconds
  });

  const handleRefreshAll = () => {
    refetchStats();
    refetchReports();
  };

  // Map reports to match what DashboardMap expects
  const mappedReports = (reports || []).map((r: any) => {
    const tenantName = stats?.tenant_names?.[r.tenant_slug] || r.tenant_slug?.toUpperCase();
    return {
      ...r,
      tenant_name: `SAR ${tenantName}`,
      waktu: r.waktu || (r.created_at ? new Date(r.created_at).toLocaleString('id-ID') : 'N/A')
    };
  });

  // Stats Card data
  const statCards = [
    { 
      label: 'Total Laporan Masuk', 
      value: stats?.total_reports ?? 0, 
      icon: FileText, 
      color: 'text-blue-600', 
      bg: 'bg-blue-50' 
    },
    { 
      label: 'Laporan Aktif (Operasi SAR)', 
      value: stats?.status_breakdown?.AKTIF ?? 0, 
      icon: Activity, 
      color: 'text-red-600', 
      bg: 'bg-red-50' 
    },
    { 
      label: 'Validasi Pending (Grup Chat)', 
      value: stats?.status_breakdown?.PENDING ?? 0, 
      icon: AlertTriangle, 
      color: 'text-slate-800', 
      bg: 'bg-amber-50' 
    },
    { 
      label: 'Operasi Selesai', 
      value: stats?.status_breakdown?.TIDAK_AKTIF ?? 0, 
      icon: CheckCircle2, 
      color: 'text-green-600', 
      bg: 'bg-green-50' 
    },
  ];

  if (isAuthenticated === null) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-gray-50">
        <Loader2 className="w-8 h-8 animate-spin text-slate-500" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return null; // Will redirect via useEffect
  }

  return (
    <div className="space-y-6 w-full pb-12">
      {/* HEADER */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight flex items-center gap-2">
            <Globe className="w-8 h-8 text-slate-800" />
            Dashboard Monitoring Nasional
          </h1>
          <p className="text-gray-500 mt-1">
            Basarnas Pusat Command Center — Pemantauan Kejadian dan Operasi SAR Terpusat Seluruh Indonesia.
          </p>
        </div>
        <button 
          onClick={handleRefreshAll}
          className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold rounded-xl transition-all border border-slate-200 flex items-center gap-2 w-fit shrink-0 active:scale-95 shadow-sm"
        >
          <RefreshCw className="w-4 h-4" /> Sinkronkan Data
        </button>
      </div>

      {/* STATS COUNT GRID */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {isLoadingStats ? (
          Array(4).fill(0).map((_, i) => <SkeletonLoader key={i} className="w-full h-24" />)
        ) : isErrorStats ? (
          <div className="col-span-full">
            <ErrorState message="Gagal memuat rekap statistik nasional." onRetry={refetchStats} />
          </div>
        ) : (
          statCards.map((card, index) => (
            <motion.div
              key={card.label}
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.08 }}
              className="bg-white rounded-2xl p-5 border border-gray-150 shadow-sm flex items-center gap-4"
            >
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0 ${card.bg}`}>
                <card.icon className={`w-6 h-6 ${card.color}`} />
              </div>
              <div>
                <p className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">{card.label}</p>
                <p className="text-2xl font-black text-gray-900 mt-0.5">{card.value}</p>
              </div>
            </motion.div>
          ))
        )}
      </div>

      {/* FILTER PANEL */}
      <div className="bg-white rounded-3xl border border-gray-155 p-5 shadow-sm space-y-4">
        <div className="flex items-center gap-2 pb-3 border-b border-gray-100">
          <Filter className="w-5 h-5 text-slate-500" />
          <h3 className="font-bold text-gray-800 text-sm">Filter Pemantauan Nasional</h3>
        </div>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          {/* Search Box */}
          <div className="space-y-1">
            <label className="block text-[10px] font-bold text-gray-500 uppercase tracking-wider">Pencarian Laporan</label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="No Laporan / Pelapor..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-4 py-2 bg-gray-50 border border-gray-250 rounded-xl text-xs focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 focus:bg-white transition-all outline-none font-semibold text-gray-700"
              />
            </div>
          </div>

          {/* Status Filter */}
          <div className="space-y-1">
            <label className="block text-[10px] font-bold text-gray-500 uppercase tracking-wider">Status Kejadian</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full px-3 py-2 bg-gray-50 border border-gray-250 rounded-xl text-xs focus:ring-2 focus:ring-slate-900/10 focus:bg-white outline-none font-semibold text-gray-700"
            >
              <option value="">Semua Status</option>
              <option value="PENDING">Pending (Validasi)</option>
              <option value="AKTIF">Aktif (Operasi SAR)</option>
              <option value="TIDAK_AKTIF">Tidak Aktif / Selesai</option>
              <option value="SALAH_LAPORAN">Salah Laporan</option>
            </select>
          </div>

          {/* Jenis Kejadian Filter */}
          <div className="space-y-1">
            <label className="block text-[10px] font-bold text-gray-500 uppercase tracking-wider">Jenis Musibah</label>
            <select
              value={jenisFilter}
              onChange={(e) => setJenisFilter(e.target.value)}
              className="w-full px-3 py-2 bg-gray-50 border border-gray-250 rounded-xl text-xs focus:ring-2 focus:ring-slate-900/10 focus:bg-white outline-none font-semibold text-gray-700"
            >
              <option value="">Semua Jenis</option>
              {stats?.incident_breakdown && Object.keys(stats.incident_breakdown).map((inc) => (
                <option key={inc} value={inc}>{inc}</option>
              ))}
              <option value="Laka Kapal">Laka Kapal (Kecelakaan Laut)</option>
              <option value="KMM">KMM (Membahayakan Manusia)</option>
              <option value="Bencana Alam">Bencana Alam / Cuaca Ekstrem</option>
              <option value="Laka Pesawat">Laka Pesawat</option>
            </select>
          </div>

          {/* Tenant (UPT) Filter */}
          <div className="space-y-1">
            <label className="block text-[10px] font-bold text-gray-500 uppercase tracking-wider">Wilayah UPT SAR</label>
            <select
              value={tenantFilter}
              onChange={(e) => setTenantFilter(e.target.value)}
              className="w-full px-3 py-2 bg-gray-50 border border-gray-250 rounded-xl text-xs focus:ring-2 focus:ring-slate-900/10 focus:bg-white outline-none font-semibold text-gray-700"
            >
              <option value="">Semua Wilayah UPT</option>
              {stats?.tenant_names && Object.entries(stats.tenant_names).map(([slug, name]) => (
                <option key={slug} value={slug}>SAR {name as string}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* LIVE MAP */}
      <div className="bg-white rounded-3xl border border-gray-150 p-5 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-gray-50 pb-3">
          <div>
            <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
              Peta Sebaran Laporan Nasional (Live Aggregate Incident Map)
            </h2>
            <p className="text-xs text-gray-500 mt-0.5">Memantau marker musibah aktif/pending di seluruh wilayah Indonesia dari database pusat.</p>
          </div>
          
          <div className="flex items-center gap-4 text-[10px] sm:text-xs font-bold shrink-0">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-red-500 block animate-pulse" />
              <span className="text-gray-600">Laporan Aktif</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-slate-900 block animate-pulse" />
              <span className="text-gray-600">Pending Validasi</span>
            </div>
          </div>
        </div>

        <div className="h-[480px] w-full rounded-2xl overflow-hidden relative border border-gray-100 z-0">
          {isLoadingReports ? (
            <div className="h-full w-full bg-gray-50 flex flex-col items-center justify-center gap-3">
              <Loader2 className="w-8 h-8 animate-spin text-slate-500" />
              <p className="text-sm font-medium text-gray-400 animate-pulse">Memetakan Insiden Nasional...</p>
            </div>
          ) : isErrorReports ? (
            <div className="h-full w-full flex items-center justify-center"><ErrorState message="Gagal memuat peta insiden." onRetry={refetchReports} /></div>
          ) : (
            <DashboardMap reports={mappedReports} />
          )}
        </div>
      </div>

      {/* TWO COLUMNS DATA GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* FEED LAPORAN DAERAH (LEFT COLUMN) */}
        <div className="bg-white rounded-3xl border border-gray-150 p-6 shadow-sm lg:col-span-2 flex flex-col h-[520px]">
          <div className="border-b border-gray-100 pb-4 mb-4 flex items-center justify-between">
            <div>
              <h3 className="font-bold text-gray-900 text-base">Aliran Laporan Musibah Nasional</h3>
              <p className="text-xs text-gray-500 mt-0.5">Daftar laporan masuk yang te-mirror secara real-time dari seluruh UPT daerah.</p>
            </div>
            <span className="px-2.5 py-1 bg-slate-100 text-slate-800 text-xs font-bold rounded-xl border border-slate-200 shadow-sm shrink-0">
              Total Feed: {mappedReports.length}
            </span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-3 pr-2 custom-scrollbar">
            {isLoadingReports ? (
              Array(4).fill(0).map((_, i) => <SkeletonLoader key={i} className="w-full h-16" />)
            ) : mappedReports.length > 0 ? (
              mappedReports.map((report: any) => {
                let CategoryIcon = AlertTriangle;
                let iconColor = "text-amber-600 bg-amber-50 border-amber-200";
                const lowerJenis = (report.jenis_kejadian || '').toLowerCase();
                if (lowerJenis.includes("kapal") || lowerJenis.includes("laut") || lowerJenis.includes("tenggelam")) {
                  CategoryIcon = Anchor;
                  iconColor = "text-blue-600 bg-blue-50 border-blue-200";
                } else if (lowerJenis.includes("manusia") || lowerJenis.includes("hilang") || lowerJenis.includes("kmm")) {
                  CategoryIcon = User;
                  iconColor = "text-slate-800 bg-slate-100 border-slate-200";
                } else if (lowerJenis.includes("pesawat") || lowerJenis.includes("udara")) {
                  CategoryIcon = Plane;
                  iconColor = "text-sky-600 bg-sky-50 border-sky-200";
                } else if (lowerJenis.includes("bencana") || lowerJenis.includes("alam") || lowerJenis.includes("banjir")) {
                  CategoryIcon = ShieldAlert;
                  iconColor = "text-emerald-600 bg-emerald-50 border-emerald-200";
                }

                return (
                  <div 
                    key={report.id}
                    className="p-4 border border-gray-100 hover:border-gray-250 hover:bg-gray-50/10 rounded-2xl transition-all space-y-2 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3"
                  >
                    <div className="space-y-1.5 flex-1 min-w-0">
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <div className={`w-7 h-7 rounded-lg flex items-center justify-center border shrink-0 ${iconColor}`}>
                          <CategoryIcon className="w-3.5 h-3.5" />
                        </div>
                        <h4 className="font-bold text-gray-950 text-sm leading-snug truncate max-w-[200px]" title={report.jenis_kejadian}>
                          {report.jenis_kejadian}
                        </h4>
                        <span className="px-2 py-0.5 bg-blue-50 border border-blue-100 text-blue-700 text-[10px] font-bold rounded-md">
                          {report.tenant_name}
                        </span>
                        <span className="text-[10px] text-gray-400 font-mono tracking-wider">
                          {report.no_laporan}
                        </span>
                      </div>
                      
                      <div className="flex items-center gap-4 text-xs text-gray-500 font-medium">
                        <span className="flex items-center gap-1">
                          <MapPin className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                          <span className="truncate max-w-[200px] sm:max-w-[300px]" title={report.lokasi_teks}>{report.lokasi_teks || 'Lokasi Belum Teridentifikasi'}</span>
                        </span>
                        <span className="flex items-center gap-1 font-bold text-slate-700">
                          <Users className="w-3.5 h-3.5 text-gray-400" />
                          {report.korban_total || 0} Korban
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between sm:justify-end gap-3 shrink-0">
                      <div className="text-right sm:block hidden">
                        <p className="text-[9px] text-gray-400 font-bold uppercase tracking-wider">Waktu Kejadian</p>
                        <p className="text-xs font-semibold text-gray-700 mt-0.5">{report.waktu?.split(',')[0]}</p>
                      </div>

                      <span className={`px-2.5 py-1 rounded-xl text-[10px] font-bold border shadow-sm ${
                        report.status === 'PENDING' ? 'bg-slate-100 text-slate-800 border-slate-200' :
                        report.status === 'AKTIF' ? 'bg-blue-50 text-blue-700 border-blue-100' :
                        report.status === 'TIDAK_AKTIF' ? 'bg-green-50 text-green-700 border-green-100' :
                        'bg-gray-50 text-gray-500 border-gray-150'
                      }`}>
                        {report.status === 'PENDING' ? 'Pending' :
                         report.status === 'AKTIF' ? 'Aktif' :
                         report.status === 'TIDAK_AKTIF' ? 'Selesai' : 'Salah Lapor'}
                      </span>
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center p-8">
                <Globe className="w-12 h-12 text-gray-300 mb-3" />
                <p className="text-sm font-bold text-gray-500">Tidak ada laporan yang cocok</p>
                <p className="text-xs text-gray-400 mt-1">Coba sesuaikan kata pencarian atau pilihan filter Anda.</p>
              </div>
            )}
          </div>
        </div>

        {/* UPT SAR BREAKDOWN (RIGHT COLUMN) */}
        <div className="bg-white rounded-3xl border border-gray-155 p-6 shadow-sm flex flex-col h-[520px]">
          <div className="border-b border-gray-100 pb-4 mb-4">
            <h3 className="font-bold text-gray-900 text-base">Distribusi Kasus per UPT</h3>
            <p className="text-xs text-gray-500 mt-0.5">Daftar beban kerja kejadian aktif yang ditangani masing-masing kantor UPT.</p>
          </div>

          <div className="flex-1 overflow-y-auto pr-1 space-y-3 custom-scrollbar">
            {isLoadingStats ? (
              Array(5).fill(0).map((_, i) => <SkeletonLoader key={i} className="w-full h-10" />)
            ) : stats?.tenant_breakdown && Object.keys(stats.tenant_breakdown).length > 0 ? (
              Object.entries(stats.tenant_breakdown).map(([slug, count]) => {
                const name = stats.tenant_names?.[slug] || slug.toUpperCase();
                return (
                  <div key={slug} className="p-3 bg-gray-50/50 border border-gray-100 rounded-xl flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg bg-slate-100 text-slate-800 flex items-center justify-center font-bold text-xs shrink-0">
                        {slug.substring(0, 2).toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-bold text-gray-900 truncate max-w-[140px]">SAR {name as string}</p>
                        <p className="text-[10px] text-gray-400 font-medium tracking-wider uppercase mt-0.5">{slug}</p>
                      </div>
                    </div>
                    <span className="px-3 py-1 bg-white border border-gray-200 text-xs font-black text-gray-800 rounded-xl shadow-sm shrink-0">
                      {count as number} Kasus
                    </span>
                  </div>
                );
              })
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center p-4 text-gray-400">
                <Users className="w-10 h-10 text-gray-300 mb-2" />
                <p className="text-xs font-semibold">Belum ada sebaran UPT SAR</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
