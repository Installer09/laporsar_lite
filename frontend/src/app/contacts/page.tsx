'use client';

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { updateContact, deleteContact, exportContacts, importContacts } from '@/lib/api';
import { Search, User, Filter, Phone, Pencil, Trash2, X, Loader2, Download, Upload, CheckCircle2, AlertTriangle } from 'lucide-react';
import { useDashboardData } from '@/hooks/useDashboardData';
import { SkeletonLoader } from '@/components/ui/SkeletonLoader';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { motion, AnimatePresence } from 'framer-motion';

export default function ContactsPage() {
  const queryClient = useQueryClient();
  const { useContactsQuery } = useDashboardData();
  const { data: contacts = [], isLoading, isError, refetch } = useContactsQuery();

  const [searchQuery, setSearchQuery] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedContact, setSelectedContact] = useState<any>(null);
  
  // Import/Export States
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importResult, setImportResult] = useState<any>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [importError, setImportError] = useState('');

  const handleExport = async () => {
    try {
      setIsExporting(true);
      const data = await exportContacts();
      const url = window.URL.createObjectURL(new Blob([data], { type: 'text/csv;charset=utf-8;' }));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `laporsar_kontak_${new Date().toISOString().slice(0,10)}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error("Gagal mengekspor kontak:", err);
      alert("Gagal mengekspor data kontak.");
    } finally {
      setIsExporting(false);
    }
  };

  const handleTemplateDownload = () => {
    const headers = "Nama;Nomor Telepon;Sumber;Catatan;Lokasi Terakhir\n";
    const blob = new Blob(['\ufeff' + headers], { type: 'text/csv;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'template_kontak.csv');
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  const handleImportSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!importFile) {
      setImportError('Silakan pilih file CSV terlebih dahulu.');
      return;
    }

    try {
      setIsImporting(true);
      setImportError('');
      setImportResult(null);
      const res = await importContacts(importFile);
      setImportResult(res);
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    } catch (err: any) {
      console.error("Gagal mengimpor kontak:", err);
      setImportError(err.response?.data?.detail || 'Gagal mengimpor file CSV. Pastikan format kolom sesuai.');
    } finally {
      setIsImporting(false);
    }
  };
  
  const [formData, setFormData] = useState({
    name: '',
    phone_number: '',
    source: 'manual',
    notes: '',
    last_location: ''
  });

  // Mutations
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) => updateContact(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
      setIsModalOpen(false);
      setSelectedContact(null);
    }
  });

  const deleteMutation = useMutation({
    mutationFn: deleteContact,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    }
  });

  const handleOpenEdit = (contact: any) => {
    setSelectedContact(contact);
    setFormData({
      name: contact.name || '',
      phone_number: contact.phone_number || '',
      source: contact.source || 'manual',
      notes: contact.notes || '',
      last_location: contact.last_location || ''
    });
    setIsModalOpen(true);
  };

  const handleDelete = (id: number, identifier: string) => {
    if (window.confirm(`Apakah Anda yakin ingin menghapus kontak "${identifier}"? Tindakan ini tidak dapat dibatalkan.`)) {
      deleteMutation.mutate(id);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedContact) {
      updateMutation.mutate({ id: selectedContact.id, data: formData });
    }
  };

  // Filter contacts locally
  const filteredContacts = (contacts || []).filter((contact: any) => {
    const searchLower = searchQuery.toLowerCase();
    return (
      (contact.name || '').toLowerCase().includes(searchLower) ||
      (contact.phone_number || '').toLowerCase().includes(searchLower) ||
      (contact.notes || '').toLowerCase().includes(searchLower) ||
      (contact.last_location || '').toLowerCase().includes(searchLower)
    );
  });

  return (
    <div className="space-y-6 w-full">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Database Kontak</h1>
          <p className="text-gray-500 mt-1">Daftar pelapor dan potensi SAR yang pernah berinteraksi.</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleExport}
            disabled={isExporting}
            className="px-3.5 py-2 bg-white hover:bg-gray-50 text-gray-700 font-semibold text-xs rounded-xl border border-gray-200 transition-all flex items-center gap-1.5 shadow-sm active:scale-95 disabled:opacity-55 cursor-pointer"
          >
            {isExporting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
            Ekspor
          </button>
          <button
            onClick={() => {
              setImportFile(null);
              setImportResult(null);
              setImportError('');
              setIsImportModalOpen(true);
            }}
            className="px-3.5 py-2 bg-orange-600 hover:bg-orange-700 text-white font-semibold text-xs rounded-xl transition-all flex items-center gap-1.5 shadow-sm active:scale-95 cursor-pointer"
          >
            <Upload className="w-3.5 h-3.5" />
            Impor Kolektif
          </button>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-gray-100 flex items-center gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input 
              type="text" 
              placeholder="Cari nama atau nomor telepon..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-gray-50 border-none rounded-lg text-sm focus:ring-2 focus:ring-orange-500/20 focus:bg-white transition-all outline-none"
            />
          </div>
          <button className="px-3 py-2 bg-gray-50 hover:bg-gray-100 text-gray-600 rounded-lg flex items-center gap-2 text-sm font-medium transition-colors border border-gray-200">
            <Filter className="w-4 h-4" />
            Filter
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-50/50">
                <th className="py-3 px-6 text-xs font-semibold text-gray-500 uppercase tracking-wider border-b border-gray-100">Profil</th>
                <th className="py-3 px-6 text-xs font-semibold text-gray-500 uppercase tracking-wider border-b border-gray-100">Platform</th>
                <th className="py-3 px-6 text-xs font-semibold text-gray-500 uppercase tracking-wider border-b border-gray-100 text-center">Jml Laporan</th>
                <th className="py-3 px-6 text-xs font-semibold text-gray-500 uppercase tracking-wider border-b border-gray-100">Indikator Spam</th>
                <th className="py-3 px-6 text-xs font-semibold text-gray-500 uppercase tracking-wider border-b border-gray-100 text-right">Aksi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {isLoading ? (
                Array(5).fill(0).map((_, i) => (
                  <tr key={i}>
                    <td colSpan={5} className="py-4 px-6">
                      <SkeletonLoader className="w-full h-12" />
                    </td>
                  </tr>
                ))
              ) : isError ? (
                <tr>
                  <td colSpan={5} className="py-8">
                    <ErrorState message="Gagal memuat data kontak." onRetry={refetch} />
                  </td>
                </tr>
              ) : filteredContacts?.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8">
                    <EmptyState message="Tidak ada kontak yang cocok dengan pencarian Anda." />
                  </td>
                </tr>
              ) : (
                filteredContacts?.map((contact: any) => (
                  <tr key={contact.id} className="hover:bg-gray-50/50 transition-colors">
                    <td className="py-4 px-6">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center shrink-0">
                          <User className="w-5 h-5 text-gray-500" />
                        </div>
                        <div>
                          <div className="font-semibold text-gray-900">{contact.name || 'Kontak Anonim'}</div>
                          <div className="text-xs text-gray-500 mt-0.5 font-mono">{contact.phone_number}</div>
                        </div>
                      </div>
                    </td>
                    <td className="py-4 px-6">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border ${
                        contact.source?.toLowerCase() === 'whatsapp' ? 'bg-green-50 text-green-700 border-green-100' : 'bg-blue-50 text-blue-700 border-blue-100'
                      }`}>
                        <Phone className="w-3.5 h-3.5" /> {contact.source || 'manual'}
                      </span>
                    </td>
                    <td className="py-4 px-6 text-center">
                      <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-gray-100 text-sm font-semibold text-gray-700">
                        {contact.reports_count ?? 1}
                      </span>
                    </td>
                    <td className="py-4 px-6">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 max-w-[100px] h-2 bg-gray-100 rounded-full overflow-hidden">
                          <div 
                            className="h-full rounded-full bg-green-500" 
                            style={{ width: '0%' }}
                          />
                        </div>
                        <span className="text-xs font-medium text-green-600">
                          0%
                        </span>
                      </div>
                    </td>
                    <td className="py-4 px-6 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button 
                          onClick={() => handleOpenEdit(contact)}
                          className="p-2 text-gray-400 hover:text-amber-600 hover:bg-amber-50 rounded-xl transition-all border border-transparent hover:border-amber-100"
                          title="Sunting Kontak"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button 
                          onClick={() => handleDelete(contact.id, contact.name || contact.phone_number)}
                          className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-xl transition-all border border-transparent hover:border-red-100"
                          title="Hapus Kontak"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* POPUP MODAL: EDIT CONTACT */}
      <AnimatePresence>
        {isModalOpen && selectedContact && (
          <>
            {/* Backdrop */}
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.5 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsModalOpen(false)}
              className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
            />
            
            {/* Modal Dialog */}
            <motion.div 
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="fixed inset-0 m-auto w-[480px] h-fit bg-white rounded-3xl shadow-2xl border border-gray-100 z-50 overflow-hidden flex flex-col"
            >
              {/* Modal Header */}
              <div className="p-5 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-10 h-10 rounded-xl bg-orange-50 border border-orange-100 flex items-center justify-center text-orange-600">
                    <User className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-gray-800 text-base">Sunting Informasi Kontak</h3>
                    <p className="text-[11px] text-gray-500 mt-0.5">Perbarui nama, nomor, atau catatan operasional kontak.</p>
                  </div>
                </div>
                <button 
                  onClick={() => setIsModalOpen(false)}
                  className="p-1.5 text-gray-400 hover:text-gray-800 hover:bg-gray-100 rounded-xl transition-all"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Modal Body */}
              <div className="p-6 space-y-4">
                <form id="contactForm" onSubmit={handleSubmit} className="space-y-4 text-xs">
                  <div className="space-y-1.5">
                    <label className="block font-bold text-gray-700">Nama Lengkap / Instansi</label>
                    <input
                      type="text"
                      required
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      placeholder="Contoh: Nurul Huda"
                      className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none text-gray-800"
                    />
                  </div>
                  
                  <div className="space-y-1.5">
                    <label className="block font-bold text-gray-700">Nomor Telepon / Handphone</label>
                    <input
                      type="text"
                      required
                      value={formData.phone_number}
                      onChange={(e) => setFormData({ ...formData, phone_number: e.target.value })}
                      placeholder="Contoh: 08127639215"
                      className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none text-gray-800 font-mono"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="block font-bold text-gray-700">Sumber Platform</label>
                      <select
                        value={formData.source}
                        onChange={(e) => setFormData({ ...formData, source: e.target.value })}
                        className="w-full px-2.5 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none text-gray-800"
                      >
                        <option value="manual">Manual</option>
                        <option value="whatsapp">WhatsApp</option>
                        <option value="telegram">Telegram</option>
                        <option value="web">Web Chat</option>
                      </select>
                    </div>
                    <div className="space-y-1.5">
                      <label className="block font-bold text-gray-700">Lokasi Terakhir</label>
                      <input
                        type="text"
                        value={formData.last_location}
                        onChange={(e) => setFormData({ ...formData, last_location: e.target.value })}
                        placeholder="Contoh: Pantai Piwang"
                        className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none text-gray-800"
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="block font-bold text-gray-700">Catatan / Keterangan Kontak</label>
                    <textarea
                      rows={3}
                      value={formData.notes}
                      onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                      placeholder="Contoh: Nelayan lokal Pantai Piwang / Potensi SAR Anambas"
                      className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none text-gray-800 resize-none leading-normal"
                    />
                  </div>
                </form>
              </div>

              {/* Modal Footer */}
              <div className="p-4 border-t border-gray-100 bg-gray-50 flex items-center justify-end gap-2.5">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 border border-gray-200 hover:bg-gray-100 text-gray-600 font-semibold text-xs rounded-xl transition-all"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  form="contactForm"
                  disabled={updateMutation.isPending}
                  className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white font-semibold text-xs rounded-xl shadow transition-all flex items-center gap-1.5 disabled:bg-gray-200 disabled:cursor-not-allowed"
                >
                  {updateMutation.isPending ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" /> Menyimpan...
                    </>
                  ) : (
                    'Simpan Perubahan'
                  )}
                </button>
              </div>
            </motion.div>
          </>
        )}

        {/* POPUP MODAL: IMPORT CONTACTS */}
        {isImportModalOpen && (
          <>
            {/* Backdrop */}
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.5 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsImportModalOpen(false)}
              className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
            />
            
            {/* Modal Dialog */}
            <motion.div 
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="fixed inset-0 m-auto w-[520px] h-fit max-h-[85vh] bg-white rounded-3xl shadow-2xl border border-gray-100 z-50 overflow-hidden flex flex-col"
            >
              {/* Modal Header */}
              <div className="p-5 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-10 h-10 rounded-xl bg-orange-50 border border-orange-100 flex items-center justify-center text-orange-600">
                    <Upload className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-gray-800 text-base">Impor Kontak Kolektif</h3>
                    <p className="text-[11px] text-gray-500 mt-0.5">Unggah spreadsheet (.csv) untuk menambahkan kontak secara massal.</p>
                  </div>
                </div>
                <button 
                  onClick={() => setIsImportModalOpen(false)}
                  className="p-1.5 text-gray-400 hover:text-gray-800 hover:bg-gray-100 rounded-xl transition-all"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Modal Body */}
              <div className="p-6 space-y-4 overflow-y-auto">
                {/* Format Instructions */}
                <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100 text-xs space-y-2">
                  <div className="font-bold text-gray-800">Petunjuk Format File:</div>
                  <p className="text-gray-600 leading-relaxed">
                    File harus berupa spreadsheet berformat <strong>.csv</strong>. Pemisah kolom otomatis mendeteksi titik koma (<code>;</code>) atau koma (<code>,</code>). Kolom yang didukung:
                  </p>
                  <ul className="list-disc pl-4 space-y-1 text-gray-600">
                    <li><strong>Nama</strong>: Nama kontak/instansi (opsional).</li>
                    <li><strong>Nomor Telepon</strong>: Nomor handphone (<strong>wajib & unik</strong>).</li>
                    <li><strong>Sumber</strong>: Platform asal (<code>manual</code>, <code>whatsapp</code>, <code>telegram</code>) (opsional).</li>
                    <li><strong>Catatan</strong>: Keterangan tambahan kontak (opsional).</li>
                    <li><strong>Lokasi Terakhir</strong>: Lokasi geografis/teks terakhir (opsional).</li>
                  </ul>
                  <button
                    type="button"
                    onClick={handleTemplateDownload}
                    className="mt-2 text-xs font-bold text-orange-600 hover:text-orange-700 flex items-center gap-1 hover:underline cursor-pointer"
                  >
                    <Download className="w-3.5 h-3.5" /> Unduh Template CSV Contoh
                  </button>
                </div>

                <form id="importForm" onSubmit={handleImportSubmit} className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="block text-xs font-bold text-gray-700">Pilih File CSV</label>
                    <div className="border-2 border-dashed border-gray-200 hover:border-orange-500/50 rounded-2xl p-6 transition-all flex flex-col items-center justify-center gap-2 bg-gray-50/50 hover:bg-white relative">
                      <input
                        type="file"
                        accept=".csv"
                        required
                        onChange={(e) => {
                          const file = e.target.files?.[0] || null;
                          setImportFile(file);
                          setImportResult(null);
                          setImportError('');
                        }}
                        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                      />
                      <Upload className="w-8 h-8 text-gray-400" />
                      <div className="text-xs font-semibold text-gray-700 text-center">
                        {importFile ? importFile.name : "Seret file ke sini atau klik untuk memilih file"}
                      </div>
                      <div className="text-[10px] text-gray-400">Hanya mendukung format .csv (Max 5MB)</div>
                    </div>
                  </div>
                </form>

                {/* Feedback Error / Success */}
                {importError && (
                  <div className="bg-red-50 text-red-700 p-3.5 rounded-xl border border-red-100 flex items-start gap-2 text-xs">
                    <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                    <div>{importError}</div>
                  </div>
                )}

                {importResult && (
                  <div className="bg-emerald-50 text-emerald-800 p-4 rounded-2xl border border-emerald-100 text-xs space-y-2">
                    <div className="flex items-center gap-1.5 font-bold text-emerald-900">
                      <CheckCircle2 className="w-4.5 h-4.5" /> Impor Berhasil Diproses
                    </div>
                    <div className="grid grid-cols-2 gap-2 mt-1">
                      <div className="bg-white/80 p-2.5 rounded-xl border border-emerald-100/50">
                        <div className="text-gray-500 text-[10px] uppercase font-bold">Kontak Baru</div>
                        <div className="text-lg font-extrabold text-emerald-700 mt-0.5">{importResult.created} data</div>
                      </div>
                      <div className="bg-white/80 p-2.5 rounded-xl border border-emerald-100/50">
                        <div className="text-gray-500 text-[10px] uppercase font-bold">Kontak Diperbarui</div>
                        <div className="text-lg font-extrabold text-amber-700 mt-0.5">{importResult.updated} data</div>
                      </div>
                    </div>
                    
                    {importResult.failed_count > 0 && (
                      <div className="mt-3 space-y-1 bg-white/60 p-3 rounded-xl border border-emerald-100/20">
                        <div className="font-bold text-red-800 flex items-center gap-1">
                          <AlertTriangle className="w-3.5 h-3.5" /> Ada {importResult.failed_count} baris yang dilewati:
                        </div>
                        <div className="max-h-24 overflow-y-auto text-[10px] space-y-1 font-mono text-gray-600 mt-1 font-semibold">
                          {importResult.failed_details.map((fail: any, idx: number) => (
                            <div key={idx}>Baris {fail.row}: {fail.reason}</div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Modal Footer */}
              <div className="p-4 border-t border-gray-100 bg-gray-50 flex items-center justify-end gap-2.5">
                <button
                  type="button"
                  onClick={() => setIsImportModalOpen(false)}
                  className="px-4 py-2 border border-gray-200 hover:bg-gray-100 text-gray-600 font-semibold text-xs rounded-xl transition-all cursor-pointer"
                >
                  {importResult ? 'Selesai' : 'Batal'}
                </button>
                {!importResult && (
                  <button
                    type="submit"
                    form="importForm"
                    disabled={isImporting || !importFile}
                    className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white font-semibold text-xs rounded-xl shadow transition-all flex items-center gap-1.5 disabled:bg-gray-200 disabled:cursor-not-allowed cursor-pointer"
                  >
                    {isImporting ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" /> Memproses...
                      </>
                    ) : (
                      'Unggah & Impor'
                    )}
                  </button>
                )}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
