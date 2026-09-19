'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { getPublicTenants, registerUser } from '@/lib/api';
import { ShieldAlert, Lock, Mail, Phone, User, Building, Loader2, ArrowRight, Activity, CheckCircle2, X, MapPin } from 'lucide-react';
import { motion } from 'framer-motion';
import { getTenantRedirectUrl, resolveTenantFromCity } from '@/lib/utils';

export default function RegisterPage() {
  const router = useRouter();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [tenantSlug, setTenantSlug] = useState('pusat');
  const [userCity, setUserCity] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Fetch active tenants for the dropdown selection
  const { data: tenants = [], isLoading: isLoadingTenants, isError: isErrorTenants } = useQuery({
    queryKey: ['publicTenants'],
    queryFn: getPublicTenants,
  });

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);

    if (!userCity.trim()) {
      setError('Silakan isi Kota/Kabupaten asal Anda.');
      setIsSubmitting(false);
      return;
    }

    try {
      await registerUser({
        name,
        email,
        phone,
        password,
        role: 'User', // Force User role on frontend side too
      }, tenantSlug);

      setSuccess(true);
      setTimeout(() => {
        window.location.href = getTenantRedirectUrl(null);
      }, 3000);
    } catch (err: any) {
      console.error(err);
      let msg = 'Registrasi gagal. Silakan coba lagi.';
      if (err.response?.data?.detail) {
        msg = err.response.data.detail;
      }
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen w-screen relative overflow-hidden bg-[#f8fafc] flex items-center justify-center font-sans antialiased py-12">
      {/* Background Glowing Blobs */}
      <div className="absolute top-[-20%] left-[-10%] w-[500px] h-[500px] rounded-full bg-gradient-to-tr from-orange-500/5 to-red-650/5 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[600px] h-[600px] rounded-full bg-gradient-to-tr from-blue-600/3 to-orange-500/4 blur-[150px] pointer-events-none" />

      {/* Main Container */}
      <div className="w-full max-w-md p-6 relative z-10">
        {/* Brand Header */}
        <div className="flex flex-col items-center mb-6">
          <motion.div 
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="inline-flex items-center justify-center p-3 bg-gradient-to-tr from-orange-500 to-red-650 rounded-2xl shadow-xl shadow-orange-500/10 mb-4"
          >
            <Activity className="w-8 h-8 text-white" />
          </motion.div>
          <span className="text-[10px] uppercase font-black tracking-[0.25em] text-orange-550 mb-1 leading-none text-center">
            Badan Nasional Pencarian dan Pertolongan
          </span>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight text-center">
            Lapor <span className="bg-gradient-to-r from-orange-500 to-red-600 bg-clip-text text-transparent">SAR</span> Command Center
          </h1>
        </div>

        {/* Card */}
        <motion.div
          initial={{ y: 30, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="bg-white border border-slate-200/80 p-8 rounded-3xl shadow-xl shadow-slate-100/50 flex flex-col relative overflow-hidden"
        >
          {/* Top Subtle Border Highlight */}
          <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-orange-500/30 to-transparent" />

          {/* Close button */}
          {!success && (
            <button
              onClick={() => window.location.href = getTenantRedirectUrl(null)}
              className="absolute top-6 right-6 p-1.5 hover:bg-slate-100 rounded-xl text-slate-400 hover:text-slate-655 transition-all cursor-pointer z-20"
              title="Kembali ke Halaman Utama"
            >
              <X className="w-5 h-5" />
            </button>
          )}

          {success ? (
            <motion.div 
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="py-12 flex flex-col items-center text-center space-y-4"
            >
              <div className="w-16 h-16 bg-green-50 rounded-full flex items-center justify-center text-green-500 shadow-sm border border-green-100">
                <CheckCircle2 className="w-8 h-8" />
              </div>
              <h2 className="text-xl font-bold text-slate-800">Registrasi Berhasil!</h2>
              <p className="text-sm text-slate-500 max-w-[280px]">
                Akun pelapor Anda telah aktif. Anda akan diarahkan ke halaman utama dalam beberapa saat...
              </p>
              <Loader2 className="w-5 h-5 text-orange-500 animate-spin mt-4" />
            </motion.div>
          ) : (
            <>
              <h2 className="text-lg font-bold text-slate-800 mb-5">Pendaftaran Pelapor Baru</h2>

              <form onSubmit={handleRegister} className="space-y-4">
                {/* Full Name */}
                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-500 pl-0.5">Nama Lengkap</label>
                  <div className="relative">
                    <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">
                      <User className="w-4 h-4" />
                    </span>
                    <input
                      type="text"
                      required
                      placeholder="Contoh: Budi Santoso"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-200 focus:border-orange-500/50 rounded-2xl py-3 pl-11 pr-4 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-4 focus:ring-orange-500/5 transition-all font-semibold focus:bg-white"
                    />
                  </div>
                </div>

                {/* Email Address */}
                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-500 pl-0.5">Alamat Email</label>
                  <div className="relative">
                    <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">
                      <Mail className="w-4 h-4" />
                    </span>
                    <input
                      type="email"
                      required
                      placeholder="Contoh: budi@gmail.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-200 focus:border-orange-500/50 rounded-2xl py-3 pl-11 pr-4 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-4 focus:ring-orange-500/5 transition-all font-semibold focus:bg-white"
                    />
                  </div>
                </div>

                {/* Phone Number */}
                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-500 pl-0.5">Nomor Telepon / WhatsApp</label>
                  <div className="relative">
                    <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">
                      <Phone className="w-4 h-4" />
                    </span>
                    <input
                      type="tel"
                      required
                      placeholder="Contoh: 08123456789"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-200 focus:border-orange-500/50 rounded-2xl py-3 pl-11 pr-4 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-4 focus:ring-orange-500/5 transition-all font-semibold focus:bg-white"
                    />
                  </div>
                </div>

                {/* Password */}
                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-500 pl-0.5">Kata Sandi</label>
                  <div className="relative">
                    <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">
                      <Lock className="w-4 h-4" />
                    </span>
                    <input
                      type="password"
                      required
                      placeholder="Minimal 6 karakter"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-200 focus:border-orange-500/50 rounded-2xl py-3 pl-11 pr-4 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-4 focus:ring-orange-500/5 transition-all font-semibold focus:bg-white"
                    />
                  </div>
                </div>

                {/* Kota / Kabupaten */}
                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-500 pl-0.5">Kota / Kabupaten Tempat Tinggal</label>
                  <div className="relative">
                    <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">
                      <MapPin className="w-4 h-4" />
                    </span>
                    <input
                      type="text"
                      required
                      placeholder="Contoh: Natuna, Surabaya, dll."
                      value={userCity}
                      onChange={(e) => {
                        const val = e.target.value;
                        setUserCity(val);
                        const resolvedSlug = resolveTenantFromCity(val, tenants);
                        setTenantSlug(resolvedSlug);
                      }}
                      className="w-full bg-slate-50 border border-slate-200 focus:border-orange-500/50 rounded-2xl py-3 pl-11 pr-4 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-4 focus:ring-orange-500/5 transition-all font-semibold focus:bg-white"
                    />
                  </div>
                  {userCity.trim() && (
                    <p className="text-[10px] text-orange-600 font-extrabold flex items-center gap-1 mt-1 pl-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-pulse"></span>
                      Kantor SAR Penanggung Jawab: {tenants.find((t: any) => t.slug === tenantSlug)?.name || 'Kantor Basarnas Pusat'}
                    </p>
                  )}
                </div>

                {/* Error Box */}
                {error && (
                  <motion.div
                    initial={{ opacity: 0, y: -5 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="p-3 bg-red-50 border border-red-100 rounded-2xl text-xs text-red-600 font-semibold flex items-center gap-2"
                  >
                    <ShieldAlert className="w-4 h-4 shrink-0" />
                    <span>{error}</span>
                  </motion.div>
                )}

                {/* Submit Button */}
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full py-4 mt-2 bg-gradient-to-r from-orange-500 to-red-650 hover:from-orange-600 hover:to-red-700 text-white font-bold text-sm rounded-2xl shadow-lg shadow-orange-500/15 flex items-center justify-center gap-2 transition-all group disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" /> Mendaftarkan...
                    </>
                  ) : (
                    <>
                      Daftar Sekarang <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
                    </>
                  )}
                </button>
              </form>

              {/* Login Redirect Link */}
              <div className="mt-5 text-center">
                <p className="text-xs text-slate-500 font-semibold">
                  Sudah memiliki akun?{' '}
                  <a href="/login" className="text-orange-550 hover:text-orange-600 font-bold underline transition-colors">
                    Masuk di sini
                  </a>
                </p>
              </div>
            </>
          )}
        </motion.div>

        {/* Copyright Footer */}
        <p className="text-[10px] text-slate-400 font-semibold text-center mt-6">
          © {new Date().getFullYear()} BASARNAS. All rights reserved.
        </p>
      </div>
    </div>
  );
}
