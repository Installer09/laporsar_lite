'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { getTenants, createTenant, updateTenantStatus, testTenantConnection, updateTenant, deleteTenant, getGlobalReports } from '@/lib/api';
import { decodeJwt } from '@/lib/utils';
import { 
  ShieldAlert, 
  Loader2, 
  Plus, 
  Search, 
  Database, 
  HardDrive, 
  Globe, 
  CheckCircle2, 
  XCircle,
  Building,
  ArrowLeft,
  Pencil,
  Trash2,
  Filter,
  FileText,
  MapPin
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import DashboardMap from '@/components/DashboardMap';

interface Tenant {
  id: number;
  name: string;
  slug: string;
  db_url: string;
  s3_bucket: string;
  is_active: boolean;
  admin_name?: string;
  admin_email?: string;
  admin_phone?: string;
}

export default function AdminDashboardPage() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);
  
  // Registration form states
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [dbUrl, setDbUrl] = useState('');
  const [s3Bucket, setS3Bucket] = useState('');
  const [adminName, setAdminName] = useState('');
  const [adminEmail, setAdminEmail] = useState('');
  const [adminPassword, setAdminPassword] = useState('');
  const [adminPhone, setAdminPhone] = useState('');
  
  const [isRegistering, setIsRegistering] = useState(false);
  const [formError, setFormError] = useState('');
  const [formSuccess, setFormSuccess] = useState('');
  const [isFormOpen, setIsFormOpen] = useState(false);

  // Edit Form states
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editingTenant, setEditingTenant] = useState<Tenant | null>(null);
  const [editName, setEditName] = useState('');
  const [editDbUrl, setEditDbUrl] = useState('');
  const [editS3Bucket, setEditS3Bucket] = useState('');
  const [editAdminName, setEditAdminName] = useState('');
  const [editAdminEmail, setEditAdminEmail] = useState('');
  const [editAdminPassword, setEditAdminPassword] = useState('');
  const [editAdminPhone, setEditAdminPhone] = useState('');
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  const [editError, setEditError] = useState('');
  const [editSuccess, setEditSuccess] = useState('');

  // Delete modal states
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [deletingTenant, setDeletingTenant] = useState<Tenant | null>(null);
  const [deleteConfirmSlug, setDeleteConfirmSlug] = useState('');
  const [isDeletingLoading, setIsDeletingLoading] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  // Status updating states
  const [updatingId, setUpdatingId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Connection diagnostic states
  const [checkingTenantId, setCheckingTenantId] = useState<number | null>(null);
  const [diagnosticResults, setDiagnosticResults] = useState<Record<number, {
    db_status: string;
    db_latency_ms: number | null;
    db_error: string | null;
    s3_status: string;
    s3_latency_ms: number | null;
    s3_error: string | null;
  }>>({});

  // Tab states
  const [activeTab, setActiveTab] = useState<'tenants' | 'reports'>('tenants');

  // National reports states
  const [globalReports, setGlobalReports] = useState<any[]>([]);
  const [isLoadingReports, setIsLoadingReports] = useState(false);
  const [reportSearchQuery, setReportSearchQuery] = useState('');
  const [selectedTenantFilter, setSelectedTenantFilter] = useState('');

  const fetchTenantsData = async () => {
    setIsLoading(true);
    try {
      const data = await getTenants();
      setTenants(data);
    } catch (err) {
      console.error('Failed to fetch tenants:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchGlobalReports = async () => {
    setIsLoadingReports(true);
    try {
      const data = await getGlobalReports();
      setGlobalReports(data);
    } catch (err) {
      console.error('Failed to fetch global reports:', err);
    } finally {
      setIsLoadingReports(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'reports') {
      fetchGlobalReports();
    }
  }, [activeTab]);

  const handleCheckConnection = async (tenantId: number) => {
    setCheckingTenantId(tenantId);
    try {
      const res = await testTenantConnection(tenantId);
      setDiagnosticResults(prev => ({
        ...prev,
        [tenantId]: res
      }));
    } catch (err) {
      console.error(err);
      alert('Gagal melakukan tes koneksi database/S3.');
    } finally {
      setCheckingTenantId(null);
    }
  };

  const router = useRouter();

  /* eslint-disable react-hooks/set-state-in-effect */
  // JWT Verification on Mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('token');
      if (!token) {
        setIsAdmin(false);
        router.push('/login');
        return;
      }

        const payload = decodeJwt(token);
        const cleanRole = payload?.role ? String(payload.role).toLowerCase().replace(/[\s_-]/g, '') : '';
        const isSuperAdmin = cleanRole === 'superadmin' || payload?.role === 'Super Admin';
        const tokenTenant = payload?.tenant_slug ? payload.tenant_slug.toLowerCase().trim() : null;
        const isPusatOrGlobal = !tokenTenant || tokenTenant === 'pusat';

        if (isSuperAdmin && isPusatOrGlobal) {
          setIsAdmin(true);
          fetchTenantsData();
        } else {
          setIsAdmin(false);
        }
    }
  }, [router]);
  /* eslint-enable react-hooks/set-state-in-effect */

  // Filter tenants based on search query computed inline
  const cleanQuery = searchQuery.toLowerCase().trim();
  const filteredTenants = cleanQuery === ''
    ? tenants
    : tenants.filter(
        (t) =>
          t.name.toLowerCase().includes(cleanQuery) ||
          t.slug.toLowerCase().includes(cleanQuery)
      );

  // Filter global reports based on search and tenant filter computed inline
  const cleanReportQuery = reportSearchQuery.toLowerCase().trim();
  const filteredReports = globalReports.filter(report => {
    const matchesSearch = cleanReportQuery === '' ||
      (report.no_laporan || '').toLowerCase().includes(cleanReportQuery) ||
      (report.pelapor_nama || '').toLowerCase().includes(cleanReportQuery) ||
      (report.jenis_kejadian || '').toLowerCase().includes(cleanReportQuery) ||
      (report.lokasi_teks || '').toLowerCase().includes(cleanReportQuery);
    
    const matchesTenant = selectedTenantFilter === '' || report.tenant_slug === selectedTenantFilter;
    
    return matchesSearch && matchesTenant;
  });

  const totalNationalReports = globalReports.length;
  const activeNationalReports = globalReports.filter(r => r.status === 'AKTIF').length;
  const pendingNationalReports = globalReports.filter(r => r.status === 'PENDING').length;

  const handleCreateTenant = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');
    setFormSuccess('');
    setIsRegistering(true);

    // Dynamic slug validation
    const slugRegex = /^[a-z0-9-]+$/;
    if (!slugRegex.test(slug)) {
      setFormError('Slug workspace hanya boleh huruf kecil, angka, dan tanda hubung (-).');
      setIsRegistering(false);
      return;
    }

    if (!adminName.trim() || !adminEmail.trim() || !adminPassword.trim()) {
      setFormError('Nama, Email/Username, dan Password Administrator wajib diisi.');
      setIsRegistering(false);
      return;
    }

    try {
      const newTenant = await createTenant({
        name,
        slug: slug.trim(),
        db_url: dbUrl.trim(),
        s3_bucket: s3Bucket.trim(),
        admin_name: adminName.trim(),
        admin_email: adminEmail.trim(),
        admin_password: adminPassword,
        admin_phone: adminPhone.trim()
      });

      setFormSuccess(`Instansi "${newTenant.name}" berhasil terdaftar! Database privat sedang disiapkan.`);
      setName('');
      setSlug('');
      setDbUrl('');
      setS3Bucket('');
      setAdminName('');
      setAdminEmail('');
      setAdminPassword('');
      setAdminPhone('');
      
      // Refresh list
      await fetchTenantsData();
      
      // Close form after delay
      setTimeout(() => {
        setIsFormOpen(false);
        setFormSuccess('');
      }, 3000);
    } catch (err) {
      console.error(err);
      const error = err as { response?: { data?: { detail?: string } } };
      const msg = error.response?.data?.detail || 'Gagal mendaftarkan instansi baru.';
      setFormError(msg);
    } finally {
      setIsRegistering(false);
    }
  };

  const handleToggleStatus = async (tenantId: number, currentStatus: boolean) => {
    const nextStatus = !currentStatus;
    const confirmMsg = nextStatus 
      ? 'Apakah Anda yakin ingin mengaktifkan instansi ini kembali?' 
      : 'PERINGATAN: Menonaktifkan instansi akan memutus seluruh akses operator, menonaktifkan bot chat WhatsApp/Telegram, dan menghentikan pengiriman laporan dari klien ini secara instan!\n\nApakah Anda yakin ingin menonaktifkannya?';
    
    if (!window.confirm(confirmMsg)) return;

    setUpdatingId(tenantId);
    try {
      await updateTenantStatus(tenantId, nextStatus);
      setTenants(prev => prev.map(t => t.id === tenantId ? { ...t, is_active: nextStatus } : t));
    } catch (err) {
      console.error(err);
      const error = err as { response?: { data?: { detail?: string } } };
      alert(error.response?.data?.detail || 'Gagal merubah status instansi.');
    } finally {
      setUpdatingId(null);
    }
  };

  const openEditModal = (tenant: Tenant) => {
    setEditingTenant(tenant);
    setEditName(tenant.name);
    setEditDbUrl(tenant.db_url);
    setEditS3Bucket(tenant.s3_bucket);
    setEditAdminName(tenant.admin_name || '');
    setEditAdminEmail(tenant.admin_email || '');
    setEditAdminPassword('');
    setEditAdminPhone(tenant.admin_phone || '');
    setEditError('');
    setEditSuccess('');
    setIsEditOpen(true);
  };

  const handleUpdateTenant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingTenant) return;
    setEditError('');
    setEditSuccess('');
    setIsSavingEdit(true);

    try {
      const updated = await updateTenant(editingTenant.id, {
        name: editName,
        db_url: editDbUrl,
        s3_bucket: editS3Bucket,
        admin_name: editAdminName.trim(),
        admin_email: editAdminEmail.trim(),
        admin_password: editAdminPassword || undefined,
        admin_phone: editAdminPhone.trim()
      });
      setEditSuccess(`Instansi "${updated.name}" berhasil diperbarui!`);
      
      // Refresh list
      await fetchTenantsData();
      
      setTimeout(() => {
        setIsEditOpen(false);
        setEditSuccess('');
        setEditingTenant(null);
      }, 2000);
    } catch (err) {
      console.error(err);
      const error = err as { response?: { data?: { detail?: string } } };
      const msg = error.response?.data?.detail || 'Gagal memperbarui instansi.';
      setEditError(msg);
    } finally {
      setIsSavingEdit(false);
    }
  };

  const openDeleteModal = (tenant: Tenant) => {
    setDeletingTenant(tenant);
    setDeleteConfirmSlug('');
    setDeleteError('');
    setIsDeleteOpen(true);
  };

  const handleDeleteTenant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!deletingTenant) return;
    if (deleteConfirmSlug.toLowerCase().trim() !== deletingTenant.slug.toLowerCase().trim()) {
      setDeleteError('Slug yang Anda masukkan tidak cocok.');
      return;
    }

    setDeleteError('');
    setIsDeletingLoading(true);
    try {
      await deleteTenant(deletingTenant.id);
      
      // Refresh list
      await fetchTenantsData();
      
      setIsDeleteOpen(false);
      setDeletingTenant(null);
    } catch (err) {
      console.error(err);
      const error = err as { response?: { data?: { detail?: string } } };
      const msg = error.response?.data?.detail || 'Gagal menghapus instansi.';
      setDeleteError(msg);
    } finally {
      setIsDeletingLoading(false);
    }
  };

  // Mask database password for visual safety
  const maskDbUrl = (url: string) => {
    try {
      const parsed = new URL(url.replace('postgresql+asyncpg://', 'http://').replace('postgresql://', 'http://'));
      return `${parsed.protocol.replace('http', 'postgresql')}//${parsed.username}:****@${parsed.host}${parsed.pathname}`;
    } catch {
      // Fallback fallback if url cannot be parsed
      return url.replace(/:([^:@]+)@/, ':****@');
    }
  };

  if (isAdmin === false) {
    return (
      <div className="min-h-full w-full bg-[#090d1a] flex items-center justify-center font-sans antialiased text-white p-6 rounded-3xl">
        <div className="text-center space-y-4 max-w-md p-8 bg-red-950/20 border border-red-500/20 rounded-3xl backdrop-blur-xl">
          <ShieldAlert className="w-16 h-16 text-red-500 mx-auto" />
          <h1 className="text-xl font-black">Akses Ditolak</h1>
          <p className="text-sm text-gray-400 font-medium leading-relaxed">
            Halaman ini hanya dapat diakses oleh akun Super Admin Pusat. Akun Anda tidak memiliki hak istimewa untuk melihat modul ini.
          </p>
          <button 
            onClick={() => router.push('/')}
            className="px-6 py-2.5 bg-white/5 hover:bg-white/10 rounded-2xl text-sm font-bold border border-white/10 transition-all"
          >
            Kembali ke Dasbor Utama
          </button>
        </div>
      </div>
    );
  }

  if (isAdmin === null || isLoading && tenants.length === 0) {
    return (
      <div className="min-h-full w-full bg-[#090d1a] flex items-center justify-center text-white py-12 rounded-3xl">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-10 h-10 text-slate-700 animate-spin" />
          <span className="text-xs font-black tracking-widest text-gray-500 uppercase">Memuat Sistem Master...</span>
        </div>
      </div>
    );
  }

  const activeCount = tenants.filter(t => t.is_active).length;
  const inactiveCount = tenants.length - activeCount;

  return (
    <div className="min-h-full w-full relative bg-[#f8fafc] text-slate-800 font-sans antialiased pb-20 rounded-3xl border border-slate-200">
      {/* Top Navigation */}
      <header className="sticky top-0 z-40 bg-white/80 backdrop-blur-md border-b border-slate-200 py-4 px-6 md:px-12">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push('/')}
              className="p-2 hover:bg-slate-100 rounded-xl border border-transparent hover:border-slate-200 text-slate-500 hover:text-slate-800 transition-all cursor-pointer"
              title="Kembali ke Dashboard Utama"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-3">
              <span className="p-2.5 bg-slate-900 rounded-xl">
                <Building className="w-5 h-5 text-white" />
              </span>
              <div>
                <h1 className="text-base font-black leading-tight tracking-tight text-slate-900">Administrator Panel</h1>
                <span className="text-[10px] font-black uppercase tracking-wider text-slate-700 leading-none">
                  Manajemen Instansi Lapor SAR
                </span>
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-2 text-xs font-bold text-slate-600 bg-slate-100 px-4 py-2 rounded-2xl border border-slate-200">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span>Master Server Connect</span>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 md:px-12 mt-8 space-y-8">
        
        {/* Tab Navigation Switcher */}
        <div className="flex border-b border-slate-200 pb-1 gap-2">
          <button
            onClick={() => setActiveTab('tenants')}
            className={`px-5 py-3 font-extrabold text-sm transition-all flex items-center gap-2 border-b-2 -mb-[5px] cursor-pointer rounded-t-xl ${
              activeTab === 'tenants'
                ? 'border-slate-900 text-slate-900 bg-slate-100 font-bold'
                : 'border-transparent text-slate-500 hover:text-slate-800 hover:bg-slate-50'
            }`}
          >
            <Database className="w-4 h-4" />
            Manajemen Instansi
          </button>
          <button
            onClick={() => setActiveTab('reports')}
            className={`px-5 py-3 font-extrabold text-sm transition-all flex items-center gap-2 border-b-2 -mb-[5px] cursor-pointer rounded-t-xl ${
              activeTab === 'reports'
                ? 'border-slate-900 text-slate-900 bg-slate-100 font-bold'
                : 'border-transparent text-slate-500 hover:text-slate-800 hover:bg-slate-50'
            }`}
          >
            <Globe className="w-4 h-4" />
            Peta & Laporan Nasional
          </button>
        </div>

        {activeTab === 'tenants' && (
          <>
            {/* Statistics Widgets */}
            <section className="grid grid-cols-1 sm:grid-cols-3 gap-6">
              {/* Total Client Card */}
              <div className="bg-white border border-slate-200/80 p-6 rounded-3xl relative overflow-hidden shadow-sm">
                <div className="absolute top-6 right-6 p-3 bg-blue-50 rounded-2xl text-blue-600">
                  <Globe className="w-5 h-5" />
                </div>
                <span className="text-xs font-bold text-slate-500">Total Kantor/Klien</span>
                <h3 className="text-3xl font-black mt-2 text-slate-800">{tenants.length}</h3>
                <p className="text-[10px] text-slate-400 font-bold mt-1 uppercase">Instansi Terdaftar Master</p>
              </div>

              {/* Active Client Card */}
              <div className="bg-white border border-slate-200/80 p-6 rounded-3xl relative overflow-hidden shadow-sm">
                <div className="absolute top-6 right-6 p-3 bg-green-50 rounded-2xl text-green-600">
                  <CheckCircle2 className="w-5 h-5" />
                </div>
                <span className="text-xs font-bold text-slate-500">Instansi Pembayar/Aktif</span>
                <h3 className="text-3xl font-black mt-2 text-green-600">{activeCount}</h3>
                <p className="text-[10px] text-slate-400 font-bold mt-1 uppercase">Melayani Laporan SAR</p>
              </div>

              {/* Inactive Client Card */}
              <div className="bg-white border border-slate-200/80 p-6 rounded-3xl relative overflow-hidden shadow-sm">
                <div className="absolute top-6 right-6 p-3 bg-red-50 rounded-2xl text-red-600">
                  <XCircle className="w-5 h-5" />
                </div>
                <span className="text-xs font-bold text-slate-500">Instansi Nonaktif</span>
                <h3 className="text-3xl font-black mt-2 text-red-650">{inactiveCount}</h3>
                <p className="text-[10px] text-slate-400 font-bold mt-1 uppercase">Layanan Ditangguhkan</p>
              </div>
            </section>

             {/* Action Bar (Search & Register button) */}
            <section className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              {/* Search bar */}
              <div className="relative max-w-md w-full">
                <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">
                  <Search className="w-4 h-4" />
                </span>
                <input
                  type="text"
                  placeholder="Cari instansi berdasarkan nama atau slug..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-white border border-slate-200 hover:border-slate-300 focus:border-slate-400 focus:ring-2 focus:ring-slate-900/10 rounded-2xl py-3.5 pl-11 pr-4 text-sm text-slate-800 focus:outline-none focus:ring-4 focus:ring-slate-900/10 transition-all font-semibold shadow-sm placeholder-slate-400"
                />
              </div>

              {/* Register button */}
              <button
                onClick={() => {
                  setIsFormOpen(true);
                  setFormError('');
                  setFormSuccess('');
                }}
                className="flex items-center justify-center gap-2 px-5 py-2.5 bg-slate-900 hover:bg-slate-800 text-white text-white font-semibold text-sm rounded-xl transition-colors shadow-sm cursor-pointer"
              >
                <Plus className="w-4 h-4" /> Daftar Instansi Baru
              </button>
            </section>

            {/* Form Modal (Create Tenant) */}
            <AnimatePresence>
              {isFormOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                  {/* Blur backdrop overlay */}
                  <motion.div 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    onClick={() => {
                      if (!isRegistering) setIsFormOpen(false);
                    }}
                    className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm"
                  />

                  {/* Form Card */}
                  <motion.div
                    initial={{ scale: 0.95, opacity: 0, y: 20 }}
                    animate={{ scale: 1, opacity: 1, y: 0 }}
                    exit={{ scale: 0.95, opacity: 0, y: 20 }}
                    className="bg-white border border-slate-200 p-8 rounded-3xl shadow-2xl w-full max-w-xl relative overflow-hidden z-10 text-slate-800 max-h-[90vh] overflow-y-auto"
                  >
                    {/* Highlight line */}
                    <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-slate-300 to-transparent" />
                    
                    <h3 className="text-lg font-black mb-1 text-slate-900">Registrasi Instansi Baru</h3>
                    <p className="text-xs text-slate-500 font-semibold mb-6">
                      Sistem akan otomatis memicu penyediaan database Postgres privat, migrasi tabel, dan bucket penyimpanan berkas S3.
                    </p>

                    <form onSubmit={handleCreateTenant} className="space-y-4">
                      {/* Name field */}
                      <div className="space-y-1">
                        <label className="text-[10px] font-black uppercase tracking-wider text-slate-500">Nama Instansi</label>
                        <input
                          type="text"
                          required
                          placeholder="e.g. Kantor Pencarian dan Pertolongan Natuna"
                          value={name}
                          onChange={(e) => setName(e.target.value)}
                          className="w-full bg-slate-50 border border-slate-200 focus:border-slate-400 focus:ring-2 focus:ring-slate-900/10 rounded-xl px-4 py-3 text-sm focus:outline-none transition-all font-semibold text-slate-800 focus:bg-white"
                        />
                      </div>

                      {/* Slug field */}
                      <div className="space-y-1">
                        <label className="text-[10px] font-black uppercase tracking-wider text-slate-500">Slug Workspace / Subdomain</label>
                        <input
                          type="text"
                          required
                          placeholder="e.g. natuna"
                          value={slug}
                          onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/\s+/g, '-'))}
                          className="w-full bg-slate-50 border border-slate-200 focus:border-slate-400 focus:ring-2 focus:ring-slate-900/10 rounded-xl px-4 py-3 text-sm focus:outline-none transition-all font-semibold text-slate-800 focus:bg-white"
                        />
                        <span className="text-[9px] text-slate-400 font-semibold leading-none block mt-1">
                          Hanya huruf kecil, angka, dan tanda hubung (-). Karakter spasi diganti otomatis.
                        </span>
                      </div>

                      {/* Database URL field */}
                      <div className="space-y-1">
                        <label className="text-[10px] font-black uppercase tracking-wider text-slate-500">PostgreSQL Connection String</label>
                        <input
                          type="text"
                          required
                          placeholder="e.g. postgresql://user:pass@host:5432/laporsar_natuna"
                          value={dbUrl}
                          onChange={(e) => setDbUrl(e.target.value)}
                          className="w-full bg-slate-50 border border-slate-200 focus:border-slate-400 focus:ring-2 focus:ring-slate-900/10 rounded-xl px-4 py-3 text-sm focus:outline-none transition-all font-mono text-xs text-slate-800 focus:bg-white"
                        />
                      </div>

                      {/* S3 Bucket Name field */}
                      <div className="space-y-1">
                        <label className="text-[10px] font-black uppercase tracking-wider text-slate-500">S3 / MinIO Bucket Name</label>
                        <input
                          type="text"
                          required
                          placeholder="e.g. laporsar-attachments-natuna"
                          value={s3Bucket}
                          onChange={(e) => setS3Bucket(e.target.value.toLowerCase().replace(/\s+/g, '-'))}
                          className="w-full bg-slate-50 border border-slate-200 focus:border-slate-400 focus:ring-2 focus:ring-slate-900/10 rounded-xl px-4 py-3 text-sm focus:outline-none transition-all font-semibold text-slate-800 focus:bg-white"
                        />
                      </div>

                      {/* Divider for Admin Account */}
                      <div className="pt-2 border-t border-slate-100 mt-4">
                        <h4 className="text-xs font-black uppercase tracking-wider text-slate-700 mb-3">Akun Administrator Instansi</h4>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-1">
                          <label className="text-[10px] font-black uppercase tracking-wider text-slate-500">Nama Lengkap</label>
                          <input
                            type="text"
                            required={isFormOpen}
                            placeholder="e.g. Ahmad Operator"
                            value={adminName}
                            onChange={(e) => setAdminName(e.target.value)}
                            className="w-full bg-slate-50 border border-slate-200 focus:border-slate-400 focus:ring-2 focus:ring-slate-900/10 rounded-xl px-4 py-3 text-sm focus:outline-none transition-all font-semibold text-slate-800 focus:bg-white"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-[10px] font-black uppercase tracking-wider text-slate-500">Email / Username</label>
                          <input
                            type="email"
                            required={isFormOpen}
                            placeholder="e.g. admin.natuna@sar.go.id"
                            value={adminEmail}
                            onChange={(e) => setAdminEmail(e.target.value)}
                            className="w-full bg-slate-50 border border-slate-200 focus:border-slate-400 focus:ring-2 focus:ring-slate-900/10 rounded-xl px-4 py-3 text-sm focus:outline-none transition-all font-semibold text-slate-800 focus:bg-white"
                          />
                        </div>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-1">
                          <label className="text-[10px] font-black uppercase tracking-wider text-slate-500">Kata Sandi (Password)</label>
                          <input
                            type="password"
                            required={isFormOpen}
                            placeholder="Min. 6 karakter"
                            value={adminPassword}
                            onChange={(e) => setAdminPassword(e.target.value)}
                            className="w-full bg-slate-50 border border-slate-200 focus:border-slate-400 focus:ring-2 focus:ring-slate-900/10 rounded-xl px-4 py-3 text-sm focus:outline-none transition-all font-semibold text-slate-800 focus:bg-white"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-[10px] font-black uppercase tracking-wider text-slate-500">Nomor Telepon</label>
                          <input
                            type="text"
                            placeholder="e.g. 08123456789"
                            value={adminPhone}
                            onChange={(e) => setAdminPhone(e.target.value)}
                            className="w-full bg-slate-50 border border-slate-200 focus:border-slate-400 focus:ring-2 focus:ring-slate-900/10 rounded-xl px-4 py-3 text-sm focus:outline-none transition-all font-semibold text-slate-800 focus:bg-white"
                          />
                        </div>
                      </div>

                      {/* Success / Error Alerts */}
                      {formError && (
                        <div className="p-3.5 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-650 font-semibold flex items-center gap-2">
                          <ShieldAlert className="w-4 h-4 shrink-0" />
                          <span>{formError}</span>
                        </div>
                      )}

                      {formSuccess && (
                        <div className="p-3.5 bg-green-500/10 border border-green-500/20 rounded-xl text-xs text-green-650 font-semibold flex items-center gap-2">
                          <CheckCircle2 className="w-4 h-4 shrink-0" />
                          <span>{formSuccess}</span>
                        </div>
                      )}

                      {/* Footer buttons */}
                      <div className="flex justify-end gap-3 pt-4 border-t border-slate-100 mt-6">
                        <button
                          type="button"
                          disabled={isRegistering}
                          onClick={() => setIsFormOpen(false)}
                          className="px-5 py-3 bg-slate-100 hover:bg-slate-200 border border-slate-200 text-slate-700 rounded-xl text-sm font-bold transition-all disabled:opacity-50 cursor-pointer"
                        >
                          Batal
                        </button>
                        <button
                          type="submit"
                          disabled={isRegistering}
                          className="px-6 py-3 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-sm font-semibold transition-colors disabled:opacity-50 flex items-center gap-2 cursor-pointer text-white shadow-sm"
                        >
                          {isRegistering ? (
                            <>
                              <Loader2 className="w-4 h-4 animate-spin" /> Sedang Menyiapkan...
                            </>
                          ) : (
                            'Daftarkan Instansi'
                          )}
                        </button>
                      </div>
                    </form>
                  </motion.div>
                </div>
              )}
            </AnimatePresence>

            {/* Edit Modal (Update Tenant) */}
            <AnimatePresence>
              {isEditOpen && editingTenant && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                  {/* Blur backdrop overlay */}
                  <motion.div 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    onClick={() => {
                      if (!isSavingEdit) setIsEditOpen(false);
                    }}
                    className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm"
                  />

                  {/* Form Card */}
                  <motion.div
                    initial={{ scale: 0.95, opacity: 0, y: 20 }}
                    animate={{ scale: 1, opacity: 1, y: 0 }}
                    exit={{ scale: 0.95, opacity: 0, y: 20 }}
                    className="bg-white border border-slate-200 p-8 rounded-3xl shadow-2xl w-full max-w-xl relative overflow-hidden z-10 text-slate-800 max-h-[90vh] overflow-y-auto"
                  >
                    {/* Highlight line */}
                    <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-blue-500/30 to-transparent" />
                    
                    <h3 className="text-lg font-black mb-1 text-slate-900">Edit Detail Instansi</h3>
                    <p className="text-xs text-slate-500 font-semibold mb-6">
                      Perbaharui informasi instansi/klien Lapor SAR. Slug workspace tidak dapat diubah demi konsistensi data.
                    </p>

                    <form onSubmit={handleUpdateTenant} className="space-y-4">
                      {/* Name field */}
                      <div className="space-y-1">
                        <label className="text-[10px] font-black uppercase tracking-wider text-slate-500">Nama Instansi</label>
                        <input
                          type="text"
                          required
                          placeholder="e.g. Kantor Pencarian dan Pertolongan Natuna"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          className="w-full bg-slate-50 border border-slate-200 focus:border-blue-500/50 rounded-xl px-4 py-3 text-sm focus:outline-none transition-all font-semibold text-slate-800 focus:bg-white"
                        />
                      </div>

                      {/* Slug field (Disabled) */}
                      <div className="space-y-1">
                        <label className="text-[10px] font-black uppercase tracking-wider text-slate-500">Slug Workspace (Kunci)</label>
                        <input
                          type="text"
                          disabled
                          value={editingTenant.slug}
                          className="w-full bg-slate-100 border border-slate-200 opacity-60 rounded-xl px-4 py-3 text-sm focus:outline-none font-mono text-xs cursor-not-allowed text-slate-500"
                        />
                      </div>

                      {/* Database URL field */}
                      <div className="space-y-1">
                        <label className="text-[10px] font-black uppercase tracking-wider text-slate-500">PostgreSQL Connection String</label>
                        <input
                          type="text"
                          required
                          placeholder="e.g. postgresql://user:pass@host:5432/laporsar_natuna"
                          value={editDbUrl}
                          onChange={(e) => setEditDbUrl(e.target.value)}
                          className="w-full bg-slate-50 border border-slate-200 focus:border-blue-500/50 rounded-xl px-4 py-3 text-sm focus:outline-none transition-all font-mono text-xs text-slate-800 focus:bg-white"
                        />
                      </div>

                      {/* S3 Bucket Name field */}
                      <div className="space-y-1">
                        <label className="text-[10px] font-black uppercase tracking-wider text-slate-500">S3 / MinIO Bucket Name</label>
                        <input
                          type="text"
                          required
                          placeholder="e.g. laporsar-attachments-natuna"
                          value={editS3Bucket}
                          onChange={(e) => setEditS3Bucket(e.target.value.toLowerCase().replace(/\s+/g, '-'))}
                          className="w-full bg-slate-50 border border-slate-200 focus:border-blue-500/50 rounded-xl px-4 py-3 text-sm focus:outline-none transition-all font-semibold text-slate-800 focus:bg-white"
                        />
                      </div>

                      {/* Divider for Admin Account */}
                      <div className="pt-2 border-t border-slate-100 mt-4">
                        <h4 className="text-xs font-black uppercase tracking-wider text-blue-500 mb-3">Akun Administrator Instansi</h4>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-1">
                          <label className="text-[10px] font-black uppercase tracking-wider text-slate-500">Nama Lengkap</label>
                          <input
                            type="text"
                            required
                            placeholder="e.g. Ahmad Operator"
                            value={editAdminName}
                            onChange={(e) => setEditAdminName(e.target.value)}
                            className="w-full bg-slate-50 border border-slate-200 focus:border-blue-500/50 rounded-xl px-4 py-3 text-sm focus:outline-none transition-all font-semibold text-slate-800 focus:bg-white"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-[10px] font-black uppercase tracking-wider text-slate-500">Email / Username</label>
                          <input
                            type="email"
                            required
                            placeholder="e.g. admin.natuna@sar.go.id"
                            value={editAdminEmail}
                            onChange={(e) => setEditAdminEmail(e.target.value)}
                            className="w-full bg-slate-50 border border-slate-200 focus:border-blue-500/50 rounded-xl px-4 py-3 text-sm focus:outline-none transition-all font-semibold text-slate-800 focus:bg-white"
                          />
                        </div>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-1">
                          <label className="text-[10px] font-black uppercase tracking-wider text-slate-500">Kata Sandi Baru (Opsional)</label>
                          <input
                            type="password"
                            placeholder="Kosongkan jika tidak diubah"
                            value={editAdminPassword}
                            onChange={(e) => setEditAdminPassword(e.target.value)}
                            className="w-full bg-slate-50 border border-slate-200 focus:border-blue-500/50 rounded-xl px-4 py-3 text-sm focus:outline-none transition-all font-semibold text-slate-800 focus:bg-white"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-[10px] font-black uppercase tracking-wider text-slate-500">Nomor Telepon</label>
                          <input
                            type="text"
                            placeholder="e.g. 08123456789"
                            value={editAdminPhone}
                            onChange={(e) => setEditAdminPhone(e.target.value)}
                            className="w-full bg-slate-50 border border-slate-200 focus:border-blue-500/50 rounded-xl px-4 py-3 text-sm focus:outline-none transition-all font-semibold text-slate-800 focus:bg-white"
                          />
                        </div>
                      </div>

                      {/* Success / Error Alerts */}
                      {editError && (
                        <div className="p-3.5 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-655 font-semibold flex items-center gap-2">
                          <ShieldAlert className="w-4 h-4 shrink-0" />
                          <span>{editError}</span>
                        </div>
                      )}

                      {editSuccess && (
                        <div className="p-3.5 bg-green-500/10 border border-green-500/20 rounded-xl text-xs text-green-655 font-semibold flex items-center gap-2">
                          <CheckCircle2 className="w-4 h-4 shrink-0" />
                          <span>{editSuccess}</span>
                        </div>
                      )}

                      {/* Footer buttons */}
                      <div className="flex justify-end gap-3 pt-4 border-t border-slate-100 mt-6">
                        <button
                          type="button"
                          disabled={isSavingEdit}
                          onClick={() => setIsEditOpen(false)}
                          className="px-5 py-3 bg-slate-100 hover:bg-slate-200 border border-slate-200 text-slate-700 rounded-xl text-sm font-bold transition-all disabled:opacity-50 cursor-pointer"
                        >
                          Batal
                        </button>
                        <button
                          type="submit"
                          disabled={isSavingEdit}
                          className="px-6 py-3 bg-gradient-to-r from-blue-500 to-indigo-650 hover:from-blue-600 hover:to-indigo-700 rounded-xl text-sm font-bold transition-all disabled:opacity-50 flex items-center gap-2 cursor-pointer text-white"
                        >
                          {isSavingEdit ? (
                            <>
                              <Loader2 className="w-4 h-4 animate-spin" /> Menyimpan...
                            </>
                          ) : (
                            'Simpan Perubahan'
                          )}
                        </button>
                      </div>
                    </form>
                  </motion.div>
                </div>
              )}
            </AnimatePresence>

            {/* Delete Modal (Unregister Tenant) */}
            <AnimatePresence>
              {isDeleteOpen && deletingTenant && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                  {/* Blur backdrop overlay */}
                  <motion.div 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    onClick={() => {
                      if (!isDeletingLoading) setIsDeleteOpen(false);
                    }}
                    className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                  />

                  {/* Glassmorphic Form Card */}
                  <motion.div
                    initial={{ scale: 0.95, opacity: 0, y: 20 }}
                    animate={{ scale: 1, opacity: 1, y: 0 }}
                    exit={{ scale: 0.95, opacity: 0, y: 20 }}
                    className="bg-[#0b1022] border border-red-500/20 p-8 rounded-3xl shadow-2xl w-full max-w-md relative overflow-hidden z-10"
                  >
                    {/* Highlight line */}
                    <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-red-500/40 to-transparent" />
                    
                    <h3 className="text-lg font-black mb-1 text-red-500 flex items-center gap-2">
                      <ShieldAlert className="w-5 h-5 shrink-0" /> Hapus Registrasi Instansi
                    </h3>
                    <div className="text-xs text-gray-400 font-semibold mb-6 space-y-2 mt-2 leading-relaxed">
                      <p>
                        Aksi ini akan menghapus instansi <strong className="text-white">&quot;{deletingTenant.name}&quot;</strong> beserta seluruh pemetaan akun pengguna terkait dari Database Master secara permanen.
                      </p>
                      <p className="bg-red-500/10 border border-red-500/20 p-3 rounded-2xl text-red-400">
                        <strong>PENTING:</strong> Database fisik PostgreSQL dan file lampiran di S3 **TIDAK AKAN** dihapus secara fisik demi mencegah kehilangan data darurat nasional.
                      </p>
                      <p>
                        Untuk mengonfirmasi penghapusan, silakan ketik ulang slug instansi ini: <strong className="text-slate-700 select-all">&quot;{deletingTenant.slug}&quot;</strong> di bawah.
                      </p>
                    </div>

                    <form onSubmit={handleDeleteTenant} className="space-y-4">
                      {/* Slug confirmation field */}
                      <div className="space-y-1">
                        <input
                          type="text"
                          required
                          placeholder="Masukkan slug untuk mengonfirmasi..."
                          value={deleteConfirmSlug}
                          onChange={(e) => {
                            setDeleteConfirmSlug(e.target.value);
                            setDeleteError('');
                          }}
                          className="w-full bg-white/5 border border-white/10 focus:border-red-500/50 rounded-xl px-4 py-3 text-sm focus:outline-none transition-all font-mono text-center text-xs"
                        />
                      </div>

                      {/* Error Alert */}
                      {deleteError && (
                        <div className="p-3.5 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-400 font-semibold flex items-center gap-2">
                          <ShieldAlert className="w-4 h-4 shrink-0" />
                          <span>{deleteError}</span>
                        </div>
                      )}

                      {/* Footer buttons */}
                      <div className="flex justify-end gap-3 pt-4 border-t border-white/[0.06] mt-6">
                        <button
                          type="button"
                          disabled={isDeletingLoading}
                          onClick={() => setIsDeleteOpen(false)}
                          className="px-5 py-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-sm font-bold transition-all disabled:opacity-50"
                        >
                          Batal
                        </button>
                        <button
                          type="submit"
                          disabled={isDeletingLoading || deleteConfirmSlug.trim() !== deletingTenant.slug}
                          className="px-6 py-3 bg-red-650 hover:bg-red-700 disabled:bg-red-950/25 disabled:text-gray-550 rounded-xl text-sm font-bold transition-all disabled:opacity-50 flex items-center gap-2"
                        >
                          {isDeletingLoading ? (
                            <>
                              <Loader2 className="w-4 h-4 animate-spin" /> Menghapus...
                            </>
                          ) : (
                            'Hapus Instansi'
                          )}
                        </button>
                      </div>
                    </form>
                  </motion.div>
                </div>
              )}
            </AnimatePresence>

            {/* Tenant Table Section */}
            <section className="bg-white border border-slate-200/80 rounded-3xl overflow-hidden shadow-sm">
              {isLoading && tenants.length === 0 ? (
                <div className="p-12 text-center text-slate-500">
                  <Loader2 className="w-8 h-8 animate-spin mx-auto text-slate-700 mb-2" />
                  <span className="text-xs font-bold uppercase tracking-widest text-slate-400">Sinkronisasi Database Master...</span>
                </div>
              ) : filteredTenants.length === 0 ? (
                <div className="p-16 text-center text-slate-500">
                  <ShieldAlert className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                  <h4 className="text-sm font-bold text-slate-700">Tidak Ada Instansi Ditemukan</h4>
                  <p className="text-xs text-slate-450 mt-1">Coba sesuaikan kata kunci pencarian Anda.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-left text-slate-800">
                    <thead>
                      <tr className="border-b border-slate-200 bg-slate-50 text-[10px] font-black uppercase tracking-wider text-slate-500">
                        <th className="py-4.5 px-6">Instansi / Kantor SAR</th>
                        <th className="py-4.5 px-6">Slug Workspace</th>
                        <th className="py-4.5 px-6">
                          <div className="flex items-center gap-1.5">
                            <Database className="w-3.5 h-3.5 text-slate-400" /> PostgreSQL Connection Link
                          </div>
                        </th>
                        <th className="py-4.5 px-6">
                          <div className="flex items-center gap-1.5">
                            <HardDrive className="w-3.5 h-3.5 text-slate-400" /> S3 Bucket
                          </div>
                        </th>
                        <th className="py-4.5 px-6 text-center">Status & Diagnostik Koneksi</th>
                        <th className="py-4.5 px-6 text-center">Aksi (Kill-Switch)</th>
                        <th className="py-4.5 px-6 text-center">Pengaturan</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {filteredTenants.map((tenant) => (
                        <tr 
                          key={tenant.id}
                          className="hover:bg-slate-50/50 transition-all text-sm font-semibold"
                        >
                          {/* Name column */}
                          <td className="py-4 px-6">
                            <div className="font-bold text-slate-850">{tenant.name}</div>
                            <span className="text-[10px] text-slate-400 font-bold block">ID: #{tenant.id}</span>
                          </td>

                          {/* Slug column */}
                          <td className="py-4 px-6 text-slate-700 font-mono text-xs">{tenant.slug}</td>

                          {/* Connection String column */}
                          <td className="py-4 px-6 font-mono text-xs text-slate-650 select-all max-w-xs truncate" title={tenant.db_url}>
                            {maskDbUrl(tenant.db_url)}
                          </td>

                          {/* S3 Bucket column */}
                          <td className="py-4 px-6 font-mono text-xs text-slate-450 select-all">{tenant.s3_bucket}</td>

                          {/* Connection Diagnostic column */}
                          <td className="py-4 px-6 text-center">
                            <div className="flex flex-col items-center gap-2">
                              {diagnosticResults[tenant.id] ? (
                                <div className="text-[10px] space-y-1 text-left w-full max-w-[200px] bg-slate-50 border border-slate-200/60 p-2 rounded-xl text-slate-600">
                                  <div className="flex items-center justify-between">
                                    <span className="text-slate-500">Database:</span>
                                    {diagnosticResults[tenant.id].db_status === 'success' ? (
                                      <span className="text-green-600 font-mono font-bold">
                                        ✓ {diagnosticResults[tenant.id].db_latency_ms?.toFixed(1)}ms
                                      </span>
                                    ) : (
                                      <span className="text-red-500 font-bold" title={diagnosticResults[tenant.id].db_error || 'Error'}>
                                        ✗ Gagal
                                      </span>
                                    )}
                                  </div>
                                  <div className="flex items-center justify-between">
                                    <span className="text-slate-500">S3 Storage:</span>
                                    {diagnosticResults[tenant.id].s3_status === 'success' ? (
                                      <span className="text-green-600 font-mono font-bold">
                                        ✓ {diagnosticResults[tenant.id].s3_latency_ms?.toFixed(1)}ms
                                      </span>
                                    ) : (
                                      <span className="text-red-500 font-bold" title={diagnosticResults[tenant.id].s3_error || 'Error'}>
                                        ✗ Gagal
                                      </span>
                                    )}
                                  </div>
                                </div>
                              ) : (
                                <span className="text-[10px] text-slate-400 italic">Belum diperiksa</span>
                              )}

                              <button
                                onClick={() => handleCheckConnection(tenant.id)}
                                disabled={checkingTenantId === tenant.id}
                                className="px-2.5 py-1 bg-slate-50 hover:bg-slate-100 border border-slate-200 hover:border-slate-300 rounded-lg text-[10px] font-bold transition-all text-slate-600 flex items-center gap-1 disabled:opacity-50 cursor-pointer"
                              >
                                {checkingTenantId === tenant.id ? (
                                  <>
                                    <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-700" />
                                    Memeriksa...
                                  </>
                                ) : (
                                  'Cek Koneksi'
                                )}
                              </button>
                            </div>
                          </td>

                          {/* Kill Switch status column */}
                          <td className="py-4 px-6 text-center">
                            <div className="flex items-center justify-center">
                              <button
                                onClick={() => handleToggleStatus(tenant.id, tenant.is_active)}
                                disabled={updatingId === tenant.id}
                                className={`px-4 py-2 rounded-2xl text-xs font-black tracking-wider uppercase transition-all flex items-center gap-1.5 border disabled:opacity-50 cursor-pointer ${
                                  tenant.is_active 
                                    ? 'bg-green-50 hover:bg-green-100/80 text-green-600 border-green-200' 
                                    : 'bg-red-50 hover:bg-red-100/80 text-red-600 border-red-200'
                                }`}
                              >
                                {updatingId === tenant.id ? (
                                  <>
                                    <Loader2 className="w-3.5 h-3.5 animate-spin" /> Memproses
                                  </>
                                ) : tenant.is_active ? (
                                  <>
                                    <CheckCircle2 className="w-3.5 h-3.5 text-green-650" /> Aktif
                                  </>
                                ) : (
                                  <>
                                    <XCircle className="w-3.5 h-3.5 text-red-650" /> Nonaktif
                                  </>
                                )}
                              </button>
                            </div>
                          </td>

                          {/* Settings actions (Edit & Delete) */}
                          <td className="py-4 px-6 text-center">
                            <div className="flex items-center justify-center gap-2">
                              <button
                                onClick={() => openEditModal(tenant)}
                                className="p-2 bg-blue-50 hover:bg-blue-100/80 text-blue-600 border border-blue-200 rounded-xl transition-all cursor-pointer"
                                title="Edit Instansi"
                              >
                                <Pencil className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => openDeleteModal(tenant)}
                                className="p-2 bg-red-50 hover:bg-red-100/80 text-red-655 border border-red-200 rounded-xl transition-all cursor-pointer"
                                title="Hapus Instansi"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </>
        )}

        {activeTab === 'reports' && (
          <>
            {/* National Reports Statistics */}
            <section className="grid grid-cols-1 sm:grid-cols-3 gap-6">
              {/* Total Reports Card */}
              <div className="bg-white border border-slate-200/80 p-6 rounded-3xl relative overflow-hidden shadow-sm">
                <div className="absolute top-6 right-6 p-3 bg-blue-50 rounded-2xl text-blue-600">
                  <FileText className="w-5 h-5" />
                </div>
                <span className="text-xs font-bold text-slate-500">Total Laporan Nasional</span>
                <h3 className="text-3xl font-black mt-2 text-slate-800">{totalNationalReports}</h3>
                <p className="text-[10px] text-slate-400 font-bold mt-1 uppercase">Seluruh Cabang Kantor SAR</p>
              </div>

              {/* Active Reports Card */}
              <div className="bg-white border border-slate-200/80 p-6 rounded-3xl relative overflow-hidden shadow-sm">
                <div className="absolute top-6 right-6 p-3 bg-red-50 rounded-2xl text-red-600">
                  <ShieldAlert className="w-5 h-5" />
                </div>
                <span className="text-xs font-bold text-slate-500">Laporan Aktif</span>
                <h3 className="text-3xl font-black mt-2 text-red-500">{activeNationalReports}</h3>
                <p className="text-[10px] text-slate-400 font-bold mt-1 uppercase">Operasi SAR Sedang Berjalan</p>
              </div>

              {/* Pending/Closed Reports Card */}
              <div className="bg-white border border-slate-200/80 p-6 rounded-3xl relative overflow-hidden shadow-sm">
                <div className="absolute top-6 right-6 p-3 bg-green-50 rounded-2xl text-green-600">
                  <CheckCircle2 className="w-5 h-5" />
                </div>
                <span className="text-xs font-bold text-slate-500">Laporan Pending / Selesai</span>
                <h3 className="text-3xl font-black mt-2 text-green-600">{pendingNationalReports}</h3>
                <p className="text-[10px] text-slate-400 font-bold mt-1 uppercase">Telah Ditangani / Ditangguhkan</p>
              </div>
            </section>

            {/* National Leaflet Map */}
            <section className="bg-white border border-slate-200/80 p-4 rounded-3xl shadow-sm overflow-hidden">
              <div className="flex items-center justify-between mb-4 px-2">
                <div>
                  <h3 className="text-sm font-black text-slate-800 flex items-center gap-2">
                    <Globe className="w-4 h-4 text-slate-700" />
                    Peta Pemantauan Nasional
                  </h3>
                  <p className="text-[10px] text-slate-450 font-medium">Visualisasi sebaran laporan kedaruratan dari seluruh instansi aktif secara real-time.</p>
                </div>
                {isLoadingReports && (
                  <div className="flex items-center gap-1 text-[10px] font-bold text-slate-700 bg-slate-100 px-3 py-1 rounded-full border border-slate-200">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Menyinkronkan...
                  </div>
                )}
              </div>
              
              <div className="h-[500px] w-full rounded-2xl overflow-hidden border border-slate-200 bg-slate-900">
                <DashboardMap reports={globalReports} />
              </div>
            </section>

            {/* Filter & Search Bar for National Reports */}
            <section className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white border border-slate-200/80 p-4 rounded-3xl shadow-sm">
              {/* Search input */}
              <div className="relative max-w-md w-full">
                <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">
                  <Search className="w-4 h-4" />
                </span>
                <input
                  type="text"
                  placeholder="Cari berdasarkan No Laporan, Pelapor, Lokasi..."
                  value={reportSearchQuery}
                  onChange={(e) => setReportSearchQuery(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 hover:border-slate-350 focus:border-slate-400 focus:ring-2 focus:ring-slate-900/10 rounded-2xl py-3 pl-11 pr-4 text-xs text-slate-800 focus:outline-none focus:ring-4 focus:ring-slate-900/10 transition-all font-semibold"
                />
              </div>

              {/* Office Filter Dropdown */}
              <div className="flex items-center gap-3">
                <span className="text-xs font-bold text-slate-550 flex items-center gap-1.5 whitespace-nowrap">
                  <Filter className="w-4 h-4 text-slate-400" />
                  Filter Kantor SAR:
                </span>
                <select
                  value={selectedTenantFilter}
                  onChange={(e) => setSelectedTenantFilter(e.target.value)}
                  className="bg-slate-50 border border-slate-200 hover:border-slate-350 focus:border-slate-400 focus:ring-2 focus:ring-slate-900/10 rounded-2xl py-3 px-4 text-xs text-slate-800 focus:outline-none transition-all font-semibold cursor-pointer min-w-[200px]"
                >
                  <option value="">Semua Kantor (Nasional)</option>
                  {tenants.map((t) => (
                    <option key={t.slug} value={t.slug}>
                      {t.name}
                    </option>
                  ))}
                </select>
              </div>
            </section>

            {/* National Reports Table */}
            <section className="bg-white border border-slate-200/80 rounded-3xl overflow-hidden shadow-sm">
              {isLoadingReports && globalReports.length === 0 ? (
                <div className="p-12 text-center text-slate-500">
                  <Loader2 className="w-8 h-8 animate-spin mx-auto text-slate-700 mb-2" />
                  <span className="text-xs font-bold uppercase tracking-widest text-slate-450">Memuat Laporan Terpadu Nasional...</span>
                </div>
              ) : filteredReports.length === 0 ? (
                <div className="p-16 text-center text-slate-500">
                  <FileText className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                  <h4 className="text-sm font-bold text-slate-700">Tidak Ada Laporan Ditemukan</h4>
                  <p className="text-xs text-slate-450 mt-1">Belum ada laporan dari instansi yang aktif atau coba sesuaikan kata kunci filter.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-left text-slate-800">
                    <thead>
                      <tr className="border-b border-slate-200 bg-slate-50 text-[10px] font-black uppercase tracking-wider text-slate-500">
                        <th className="py-4.5 px-6">No Laporan</th>
                        <th className="py-4.5 px-6">Kantor SAR Penanggung Jawab</th>
                        <th className="py-4.5 px-6">Pelapor</th>
                        <th className="py-4.5 px-6">Kejadian</th>
                        <th className="py-4.5 px-6">Waktu & Lokasi</th>
                        <th className="py-4.5 px-6 text-center">Status</th>
                        <th className="py-4.5 px-6 text-center">Navigasi</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {filteredReports.map((report) => (
                        <tr 
                          key={`${report.tenant_slug}-${report.id}`}
                          className="hover:bg-slate-50/50 transition-all text-xs font-semibold"
                        >
                          {/* Report No */}
                          <td className="py-4 px-6">
                            <span className="font-mono text-slate-800 bg-slate-100 border border-slate-200 px-2.5 py-1.5 rounded-lg select-all">
                              {report.no_laporan}
                            </span>
                          </td>

                          {/* Branch office name */}
                          <td className="py-4 px-6 text-blue-600">
                            <div className="font-bold">{report.tenant_name}</div>
                            <span className="text-[9px] text-slate-400 font-bold uppercase tracking-wider">slug: {report.tenant_slug}</span>
                          </td>

                          {/* Reporter */}
                          <td className="py-4 px-6">
                            <div className="font-bold text-slate-850">{report.pelapor_nama}</div>
                            <div className="text-[10px] text-slate-500 font-mono mt-0.5">{report.pelapor_nomor}</div>
                          </td>

                          {/* Occurrence */}
                          <td className="py-4 px-6">
                            <div className="font-bold text-slate-800 text-sm">{report.jenis_kejadian}</div>
                          </td>

                          {/* Time & Location */}
                          <td className="py-4 px-6 max-w-xs">
                            <div className="text-slate-650 font-medium">{report.waktu}</div>
                            <div className="text-[10px] text-slate-450 truncate mt-0.5" title={report.lokasi_teks}>
                              {report.lokasi_teks}
                            </div>
                          </td>

                          {/* Status */}
                          <td className="py-4 px-6 text-center">
                            <div className="flex items-center justify-center">
                              <span className={`px-3 py-1.5 rounded-xl text-[10px] font-black tracking-wider uppercase border ${
                                report.status === 'PENDING'
                                  ? 'bg-slate-100 text-slate-700 border-slate-200'
                                  : report.status === 'AKTIF'
                                  ? 'bg-blue-50 text-blue-600 border-blue-200'
                                  : 'bg-green-50 text-green-600 border-green-200'
                              }`}>
                                {report.status}
                              </span>
                            </div>
                          </td>

                          {/* Navigation */}
                          <td className="py-4 px-6 text-center">
                            <div className="flex items-center justify-center">
                              <a
                                href={report.gmaps_link || `https://www.google.com/maps?q=${report.koordinat_lat},${report.koordinat_lng}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="px-3 py-1.5 bg-slate-100 hover:bg-slate-100 text-slate-800 border border-slate-200 hover:border-slate-300 rounded-xl text-[10px] font-bold transition-all flex items-center gap-1 cursor-pointer"
                              >
                                <MapPin className="w-3.5 h-3.5" /> Buka Peta
                              </a>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </>
        )}
      </main>
    </div>
  );
}
