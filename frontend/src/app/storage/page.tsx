'use client';

import { useState, useEffect } from 'react';
import { 
  HardDrive, 
  Mic, 
  Image as ImageIcon, 
  FileText, 
  Trash2, 
  RefreshCw, 
  AlertTriangle, 
  CheckCircle2, 
  Loader2,
  FolderOpen,
  Volume2,
  Download,
  Eye,
  X
} from 'lucide-react';
import { getStorageStats, listStorageFiles, deleteStorageFile, cleanupStorageFiles } from '@/lib/api';

interface StorageStats {
  storage_type: string;
  storage_path: string;
  total_files: number;
  total_size_bytes: number;
  total_size_mb: number;
  disk_free_gb: number;
  categories: {
    photos: { count: number; size_bytes: number };
    audios: { count: number; size_bytes: number };
    videos: { count: number; size_bytes: number };
    documents: { count: number; size_bytes: number };
    others: { count: number; size_bytes: number };
  };
}

interface StorageItem {
  key: string;
  filename: string;
  category: string;
  size_bytes: number;
  size_formatted: string;
  modified_at: string;
  url: string;
}

export default function StorageManagerPage() {
  const [stats, setStats] = useState<StorageStats | null>(null);
  const [files, setFiles] = useState<StorageItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [deletingKey, setDeletingKey] = useState<string | null>(null);
  const [showCleanupModal, setShowCleanupModal] = useState(false);
  const [cleaningUp, setCleaningUp] = useState(false);
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [statsData, filesData] = await Promise.all([
        getStorageStats().catch(() => null),
        listStorageFiles({ category: categoryFilter, limit: 150 }).catch(() => ({ items: [] })),
      ]);
      if (statsData) setStats(statsData);
      if (filesData && filesData.items) setFiles(filesData.items);
    } catch (err: any) {
      console.error('Failed to fetch storage data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [categoryFilter]);

  const handleDelete = async (key: string) => {
    if (!confirm(`Hapus berkas "${key}" dari disk server?`)) return;
    try {
      setDeletingKey(key);
      await deleteStorageFile(key);
      setNotification({ type: 'success', message: 'Berkas berhasil dihapus.' });
      fetchData();
    } catch (err: any) {
      setNotification({ type: 'error', message: 'Gagal menghapus berkas.' });
    } finally {
      setDeletingKey(null);
    }
  };

  const handleCleanup = async () => {
    try {
      setCleaningUp(true);
      await cleanupStorageFiles();
      setNotification({ type: 'success', message: 'Seluruh berkas uji coba berhasil dibersihkan.' });
      setShowCleanupModal(false);
      fetchData();
    } catch (err: any) {
      setNotification({ type: 'error', message: 'Gagal membersihkan berkas.' });
    } finally {
      setCleaningUp(false);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-slate-200">
          <div>
            <div className="flex items-center gap-2">
              <span className="p-2 bg-orange-100 text-orange-600 rounded-lg">
                <HardDrive className="w-6 h-6" />
              </span>
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Manajemen Berkas & Media</h1>
            </div>
            <p className="text-sm text-slate-500 mt-1">
              Pengelolaan media lokal Lapor SAR: Voice Note, foto dokumentasi musibah, dan lampiran darurat.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={fetchData}
              disabled={loading}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition shadow-sm"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Segarkan
            </button>
            <button
              onClick={() => setShowCleanupModal(true)}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 text-sm font-medium text-red-600 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100 transition"
            >
              <Trash2 className="w-4 h-4" />
              Reset Berkas Demo
            </button>
          </div>
        </div>

        {/* Alerts */}
        {notification && (
          <div className={`p-4 rounded-lg flex items-center justify-between ${
            notification.type === 'success' ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' : 'bg-red-50 text-red-800 border border-red-200'
          }`}>
            <div className="flex items-center gap-2 text-sm font-medium">
              {notification.type === 'success' ? <CheckCircle2 className="w-5 h-5 text-emerald-600" /> : <AlertTriangle className="w-5 h-5 text-red-600" />}
              {notification.message}
            </div>
            <button onClick={() => setNotification(null)} className="text-slate-400 hover:text-slate-600">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Metrics Overview */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-5 bg-white rounded-xl border border-slate-200 shadow-sm">
            <div className="flex items-center justify-between text-slate-500">
              <span className="text-xs font-semibold uppercase tracking-wider">Ruang Terpakai</span>
              <HardDrive className="w-5 h-5 text-orange-600" />
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-slate-900">{stats?.total_size_mb ?? 0} MB</span>
              <span className="text-xs text-slate-500">({stats?.total_files ?? 0} berkas)</span>
            </div>
            <div className="mt-3 text-xs text-slate-500 flex items-center gap-1">
              Sisa disk lokal: <span className="font-semibold text-slate-700">{stats?.disk_free_gb ?? 0} GB</span>
            </div>
          </div>

          <div className="p-5 bg-white rounded-xl border border-slate-200 shadow-sm">
            <div className="flex items-center justify-between text-slate-500">
              <span className="text-xs font-semibold uppercase tracking-wider">Voice Note (Audio)</span>
              <Mic className="w-5 h-5 text-blue-600" />
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-slate-900">{stats?.categories?.audios?.count ?? 0}</span>
              <span className="text-xs text-slate-500">rekaman suara</span>
            </div>
            <div className="mt-3 text-xs text-slate-500">
              Transkripsi Suara Otomatis
            </div>
          </div>

          <div className="p-5 bg-white rounded-xl border border-slate-200 shadow-sm">
            <div className="flex items-center justify-between text-slate-500">
              <span className="text-xs font-semibold uppercase tracking-wider">Foto Musibah</span>
              <ImageIcon className="w-5 h-5 text-emerald-600" />
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-slate-900">{stats?.categories?.photos?.count ?? 0}</span>
              <span className="text-xs text-slate-500">gambar bukti</span>
            </div>
            <div className="mt-3 text-xs text-slate-500">
              Lampiran Pelapor & Operator
            </div>
          </div>

          <div className="p-5 bg-white rounded-xl border border-slate-200 shadow-sm">
            <div className="flex items-center justify-between text-slate-500">
              <span className="text-xs font-semibold uppercase tracking-wider">Dokumen / Lainnya</span>
              <FileText className="w-5 h-5 text-purple-600" />
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-slate-900">
                {(stats?.categories?.documents?.count ?? 0) + (stats?.categories?.others?.count ?? 0)}
              </span>
              <span className="text-xs text-slate-500">dokumen</span>
            </div>
            <div className="mt-3 text-xs text-slate-500">
              Format KML / PDF / Arsip
            </div>
          </div>
        </div>

        {/* Filter Tabs */}
        <div className="flex items-center gap-2 border-b border-slate-200">
          {[
            { id: 'all', label: 'Semua Berkas' },
            { id: 'audio', label: 'Rekaman Suara (Audio)' },
            { id: 'photo', label: 'Foto Dokumentasi' },
            { id: 'document', label: 'Dokumen' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setCategoryFilter(tab.id)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition -mb-px ${
                categoryFilter === tab.id
                  ? 'border-orange-600 text-orange-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content Section */}
        {loading ? (
          <div className="py-20 flex flex-col items-center justify-center text-slate-400">
            <Loader2 className="w-8 h-8 animate-spin text-orange-600 mb-2" />
            <span className="text-sm font-medium">Memindai media penyimpanan server...</span>
          </div>
        ) : files.length === 0 ? (
          <div className="py-16 text-center bg-white rounded-xl border border-slate-200">
            <FolderOpen className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <h3 className="text-base font-semibold text-slate-800">Belum ada berkas tersimpan</h3>
            <p className="text-sm text-slate-500 mt-1 max-w-md mx-auto">
              Berkas foto dan voice note yang dikirimkan oleh pelapor akan otomatis tersimpan dan dapat diputar di sini.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {files.map((file) => (
              <div
                key={file.key}
                className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm hover:border-slate-300 transition flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className={`p-2 rounded-lg ${
                        file.category === 'audio' ? 'bg-blue-50 text-blue-600' :
                        file.category === 'photo' ? 'bg-emerald-50 text-emerald-600' : 'bg-purple-50 text-purple-600'
                      }`}>
                        {file.category === 'audio' ? <Mic className="w-4 h-4" /> :
                         file.category === 'photo' ? <ImageIcon className="w-4 h-4" /> : <FileText className="w-4 h-4" />}
                      </span>
                      <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                        {file.category}
                      </span>
                    </div>

                    <button
                      onClick={() => handleDelete(file.key)}
                      disabled={deletingKey === file.key}
                      className="text-slate-400 hover:text-red-600 p-1 rounded hover:bg-red-50 transition"
                      title="Hapus berkas"
                    >
                      {deletingKey === file.key ? (
                        <Loader2 className="w-4 h-4 animate-spin text-red-600" />
                      ) : (
                        <Trash2 className="w-4 h-4" />
                      )}
                    </button>
                  </div>

                  <p className="text-sm font-semibold text-slate-800 mt-3 truncate" title={file.filename}>
                    {file.filename}
                  </p>
                  <p className="text-xs text-slate-400 truncate mt-0.5" title={file.key}>
                    {file.key}
                  </p>

                  {/* Media Previews */}
                  {file.category === 'audio' && (
                    <div className="mt-3 bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                      <div className="flex items-center gap-1.5 text-xs text-slate-600 mb-1.5 font-medium">
                        <Volume2 className="w-3.5 h-3.5 text-blue-600" />
                        Pemutar Rekaman Suara:
                      </div>
                      <audio controls src={file.url} className="w-full h-8" preload="none" />
                    </div>
                  )}

                  {file.category === 'photo' && (
                    <div 
                      onClick={() => setPreviewImage(file.url)}
                      className="mt-3 relative h-36 bg-slate-100 rounded-lg overflow-hidden border border-slate-200 cursor-pointer group"
                    >
                      <img 
                        src={file.url} 
                        alt={file.filename} 
                        className="w-full h-full object-cover group-hover:scale-105 transition duration-300"
                        loading="lazy" 
                      />
                      <div className="absolute inset-0 bg-black/30 opacity-0 group-hover:opacity-100 transition flex items-center justify-center text-white">
                        <Eye className="w-5 h-5" />
                      </div>
                    </div>
                  )}
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
                  <span>{file.size_formatted}</span>
                  <a
                    href={file.url}
                    download={file.filename}
                    className="inline-flex items-center gap-1 text-orange-600 hover:text-orange-700 font-medium"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Unduh
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Photo Lightbox Modal */}
        {previewImage && (
          <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="relative max-w-4xl max-h-[90vh] bg-slate-900 rounded-2xl overflow-hidden p-2">
              <button
                onClick={() => setPreviewImage(null)}
                className="absolute top-4 right-4 z-10 p-2 bg-black/60 text-white rounded-full hover:bg-black/80 transition"
              >
                <X className="w-5 h-5" />
              </button>
              <img src={previewImage} alt="Preview" className="max-w-full max-h-[85vh] object-contain rounded-xl" />
            </div>
          </div>
        )}

        {/* Cleanup Confirmation Modal */}
        {showCleanupModal && (
          <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
              <div className="w-12 h-12 rounded-full bg-red-100 text-red-600 flex items-center justify-center mx-auto">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div className="text-center">
                <h3 className="text-lg font-bold text-slate-900">Reset Semua Berkas Demo?</h3>
                <p className="text-sm text-slate-500 mt-2">
                  Tindakan ini akan menghapus seluruh rekaman suara dan foto yang tersimpan di direktori server lokal. Sangat berguna untuk membersihkan data setelah simulasi pitch selesai.
                </p>
              </div>
              <div className="flex items-center gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCleanupModal(false)}
                  className="flex-1 px-4 py-2.5 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition"
                >
                  Batal
                </button>
                <button
                  type="button"
                  onClick={handleCleanup}
                  disabled={cleaningUp}
                  className="flex-1 px-4 py-2.5 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition inline-flex items-center justify-center gap-2"
                >
                  {cleaningUp && <Loader2 className="w-4 h-4 animate-spin" />}
                  Ya, Bersihkan
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
  );
}
