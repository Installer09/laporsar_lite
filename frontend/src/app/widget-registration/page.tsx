'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation } from '@tanstack/react-query';
import { createWidgetRequest, getBackendUrl } from '@/lib/api';
import { Building2, Globe, Mail, Phone, ArrowRight, ArrowLeft, CheckCircle2, AlertCircle, Loader2, Info } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function WidgetRegistrationPage() {
  const router = useRouter();
  const [partnerName, setPartnerName] = useState('');
  const [websiteUrl, setWebsiteUrl] = useState('');
  const [officialEmail, setOfficialEmail] = useState('');
  const [officialPhone, setOfficialPhone] = useState('');
  
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const submitMutation = useMutation({
    mutationFn: createWidgetRequest,
    onSuccess: () => {
      setIsSubmitted(true);
      setErrorMsg('');
    },
    onError: (err: any) => {
      setErrorMsg(err.response?.data?.detail || 'Gagal mengirimkan permohonan. Silakan coba beberapa saat lagi.');
    }
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!partnerName.trim() || !websiteUrl.trim() || !officialEmail.trim() || !officialPhone.trim()) {
      setErrorMsg('Semua kolom formulir wajib diisi.');
      return;
    }
    
    // Simple URL domain validation/cleanup
    let cleanedUrl = websiteUrl.trim().toLowerCase();
    cleanedUrl = cleanedUrl.replace(/^(https?:\/\/)?(www\.)?/, ''); // remove protocol/www
    cleanedUrl = cleanedUrl.split('/')[0]; // take only domain

    submitMutation.mutate({
      partner_name: partnerName.trim(),
      website_url: cleanedUrl,
      official_email: officialEmail.trim(),
      official_phone: officialPhone.trim()
    });
  };

  return (
    <div className="min-h-screen w-screen relative overflow-x-hidden bg-gradient-to-br from-slate-50 via-white to-slate-50/50 font-sans flex flex-col justify-between">
      {/* Background Glowing Blobs */}
      <div className="absolute top-[-10%] left-[-10%] w-[600px] h-[600px] rounded-full bg-gradient-to-tr from-orange-400/5 to-red-500/5 blur-[130px] pointer-events-none z-0" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[700px] h-[700px] rounded-full bg-gradient-to-tr from-blue-500/5 to-orange-400/5 blur-[150px] pointer-events-none z-0" />

      {/* 1. Top Navigation Header */}
      <header className="w-full z-10 bg-white/80 backdrop-blur-md border-b border-slate-200/80 py-4 px-6 sm:px-8 flex items-center justify-between shadow-sm sticky top-0 shrink-0">
        <button 
          onClick={() => router.push('/')}
          className="flex items-center gap-2 text-slate-700 hover:text-orange-600 transition-colors font-extrabold text-xs cursor-pointer group"
        >
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
          Kembali ke Portal
        </button>
        <div className="flex items-center gap-2">
          <img src="/logo.png" alt="Lapor SAR Logo" className="w-6 h-6 object-contain" />
          <span className="font-extrabold text-sm text-slate-800">Registrasi Widget Lapor SAR</span>
        </div>
      </header>

      {/* 2. Main Page Content */}
      <main className="flex-1 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8 z-10">
        <div className="sm:mx-auto sm:w-full sm:max-w-md text-center space-y-4">
          {/* LOGO */}
          <div className="mx-auto h-16 w-16 bg-white rounded-3xl flex items-center justify-center shadow-lg shadow-orange-500/10 border border-slate-100 overflow-hidden">
            <img src="/logo.png" alt="Lapor SAR Logo" className="w-12 h-12 object-contain" />
          </div>
          <div>
            <h2 className="text-3xl font-extrabold text-slate-800 tracking-tight">
              Integrasi Widget Lapor SAR
            </h2>
            <p className="mt-2 text-sm text-slate-500 max-w-xs mx-auto">
              Daftarkan website instansi Anda untuk mendapatkan API Key resmi obrolan darurat BASARNAS.
            </p>
          </div>
        </div>

        <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-lg">
          <div className="bg-white py-8 px-6 shadow-xl rounded-3xl sm:px-10 border border-slate-200/50">
            <AnimatePresence mode="wait">
              {!isSubmitted ? (
                <motion.form 
                  key="form"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  onSubmit={handleSubmit} 
                  className="space-y-6"
                >
                  {errorMsg && (
                    <div className="bg-rose-50 border border-rose-100 p-4 rounded-2xl flex items-start gap-3 text-xs text-rose-800 font-semibold">
                      <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                      <span>{errorMsg}</span>
                    </div>
                  )}

                  <div className="space-y-4">
                    <div>
                      <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1.5 pl-0.5">Nama Instansi / Website</label>
                      <div className="relative">
                        <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
                          <Building2 className="h-4.5 w-4.5" />
                        </div>
                        <input
                          type="text"
                          required
                          value={partnerName}
                          onChange={(e) => setPartnerName(e.target.value)}
                          placeholder="Contoh: BPBD Kabupaten Natuna"
                          className="block w-full pl-10 pr-4 py-3 bg-gray-50 border border-gray-200 rounded-2xl text-sm focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none transition-all text-gray-900 font-semibold"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1.5 pl-0.5">Domain Website</label>
                      <div className="relative">
                        <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
                          <Globe className="h-4.5 w-4.5" />
                        </div>
                        <input
                          type="text"
                          required
                          value={websiteUrl}
                          onChange={(e) => setWebsiteUrl(e.target.value)}
                          placeholder="Contoh: bpbd.natunakab.go.id"
                          className="block w-full pl-10 pr-4 py-3 bg-gray-50 border border-gray-200 rounded-2xl text-sm focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none transition-all text-gray-900 font-semibold"
                        />
                      </div>
                      <p className="text-[10px] text-gray-400 mt-1.5 italic pl-0.5">Catatan: Masukkan domain tanpa http/https (misalnya bpbd.natunakab.go.id).</p>
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1.5 pl-0.5">Email Resmi Instansi</label>
                      <div className="relative">
                        <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
                          <Mail className="h-4.5 w-4.5" />
                        </div>
                        <input
                          type="email"
                          required
                          value={officialEmail}
                          onChange={(e) => setOfficialEmail(e.target.value)}
                          placeholder="Contoh: info@bpbd.natunakab.go.id"
                          className="block w-full pl-10 pr-4 py-3 bg-gray-50 border border-gray-200 rounded-2xl text-sm focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none transition-all text-gray-900 font-semibold"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1.5 pl-0.5">Nomor WhatsApp Resmi / Kontak</label>
                      <div className="relative">
                        <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
                          <Phone className="h-4.5 w-4.5" />
                        </div>
                        <input
                          type="text"
                          required
                          value={officialPhone}
                          onChange={(e) => setOfficialPhone(e.target.value)}
                          placeholder="Contoh: 081234567890"
                          className="block w-full pl-10 pr-4 py-3 bg-gray-50 border border-gray-200 rounded-2xl text-sm focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none transition-all text-gray-900 font-semibold"
                        />
                      </div>
                    </div>
                  </div>

                  <div className="pt-2">
                    <button
                      type="submit"
                      disabled={submitMutation.isPending}
                      className="w-full flex justify-center items-center gap-2 py-3.5 px-4 bg-gradient-to-r from-orange-500 to-red-650 hover:opacity-90 active:scale-98 text-white font-extrabold text-sm rounded-2xl shadow-md shadow-orange-500/10 transition-all disabled:opacity-50 cursor-pointer"
                    >
                      {submitMutation.isPending ? (
                        <Loader2 className="w-5 h-5 animate-spin" />
                      ) : (
                        <>
                          Kirim Permohonan
                          <ArrowRight className="w-4 h-4" />
                        </>
                      )}
                    </button>
                  </div>
                </motion.form>
              ) : (
                <motion.div 
                  key="success"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="text-center py-6 space-y-4"
                >
                  <div className="mx-auto w-16 h-16 bg-emerald-50 rounded-full flex items-center justify-center text-emerald-600 border border-emerald-100">
                    <CheckCircle2 className="w-10 h-10 animate-bounce" />
                  </div>
                  <div className="space-y-2">
                    <h3 className="text-xl font-bold text-gray-900">Permohonan Berhasil Dikirim</h3>
                    <p className="text-xs text-gray-500 leading-relaxed max-w-sm mx-auto">
                      Terima kasih, permohonan integrasi widget **Lapor SAR** untuk website <code className="bg-gray-100 px-1.5 py-0.5 rounded text-gray-700 font-semibold">{websiteUrl}</code> telah masuk ke sistem kami.
                    </p>
                    <p className="text-xs text-gray-500 leading-relaxed max-w-sm mx-auto">
                      Permohonan Anda saat ini bersatus **Menunggu Verifikasi** (`PENDING`). Silakan hubungi pihak operator BASARNAS terkait untuk mempercepat verifikasi dan penerbitan API Key resmi Anda.
                    </p>
                  </div>
                  <div className="pt-4">
                    <button
                      onClick={() => {
                        setIsSubmitted(false);
                        setPartnerName('');
                        setWebsiteUrl('');
                        setOfficialEmail('');
                        setOfficialPhone('');
                      }}
                      className="px-6 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs rounded-xl shadow-sm transition-colors active:scale-95 cursor-pointer"
                    >
                      Buat Pengajuan Baru
                    </button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Panduan Pemasangan Widget Lapor SAR */}
          <div className="mt-8 bg-white/80 backdrop-blur-sm border border-slate-200/80 p-6 rounded-3xl space-y-3 shadow-md max-w-lg mx-auto w-full">
            <h3 className="text-sm font-bold text-orange-600 flex items-center gap-2">
              <Info className="w-5 h-5 text-orange-500" /> Panduan Pemasangan Widget Lapor SAR
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              Untuk menempelkan widget <strong className="text-slate-800">Lapor SAR</strong> pada website pihak ketiga (misalnya website BPBD, Pemerintah Daerah, atau Kantor SAR Daerah), salin potongan kode di bawah ini dan letakkan sebelum tag penutup <code className="text-orange-650 font-mono font-bold">&lt;/body&gt;</code> pada halaman web yang bersangkutan.
            </p>
            <div className="bg-slate-50 text-orange-650 p-4 rounded-2xl font-mono text-xs overflow-x-auto relative group shadow-inner border border-slate-200/60">
              <pre>{`<script
  src="${getBackendUrl()}/uploads/widget.js"
  data-api-key="sar_MASUKKAN_API_KEY_DI_SINI"
></script>`}</pre>
            </div>
            <p className="text-[10px] text-slate-400 italic">
              Catatan: Widget memerlukan API Key resmi dan hanya akan merespons request yang berasal dari domain website yang telah didaftarkan dan disetujui oleh Administrator BASARNAS.
            </p>
          </div>
        </div>
      </main>

      {/* 3. Footer */}
      <footer className="w-full z-10 bg-slate-50 border-t border-slate-200/60 py-4 px-8 flex justify-center mt-8 shrink-0">
        <p className="text-[10px] text-slate-450 font-semibold font-sans">
          © {new Date().getFullYear()} BASARNAS. All rights reserved.
        </p>
      </footer>
    </div>
  );
}
