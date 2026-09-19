'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { api, getTenantSlug } from '@/lib/api';
import { ShieldAlert, Lock, Mail, Loader2, ArrowRight, Activity, X } from 'lucide-react';
import { motion } from 'framer-motion';
import { decodeJwt, getTenantRedirectUrl } from '@/lib/utils';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();

  useEffect(() => {
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem('logging_out');
    }
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const { data } = await api.post('/auth/login', {
        username: email,
        password: password,
      });

      if (data.access_token) {
        localStorage.setItem('token', data.access_token);
        sessionStorage.removeItem('logging_out');
        
        const payload = decodeJwt(data.access_token);
        if (payload) {
          const tokenSlug = payload.tenant_slug ? payload.tenant_slug.toLowerCase().trim() : 'pusat';
          const normalizedTokenTenant = (tokenSlug === 'pusat' || tokenSlug === '') ? 'pusat' : tokenSlug;
          
          const slug = getTenantSlug();
          const currentSlug = slug ? slug.toLowerCase().trim() : 'pusat';
          const normalizedCurrentTenant = (currentSlug === 'pusat' || currentSlug === '') ? 'pusat' : currentSlug;
          
          if (normalizedTokenTenant !== normalizedCurrentTenant) {
            const redirectUrl = getTenantRedirectUrl(payload.tenant_slug);
            window.location.href = `${redirectUrl}/?token=${encodeURIComponent(data.access_token)}`;
            return;
          }
        }

        // Refresh router and redirect to dashboard
        router.refresh();
        router.push('/');
      } else {
        setError('Gagal mendapatkan token autentikasi.');
      }
    } catch (err: any) {
      console.error(err);
      let msg = 'Kombinasi email dan kata sandi salah.';
      if (err.response?.status === 401) {
        msg = 'Username atau password salah.';
      } else if (err.response?.data?.detail) {
        msg = err.response.data.detail;
      }
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-screen relative overflow-hidden bg-[#f8fafc] flex items-center justify-center font-sans antialiased">
      {/* Dynamic Background Glowing Blobs */}
      <div className="absolute top-[-20%] left-[-10%] w-[500px] h-[500px] rounded-full bg-gradient-to-tr from-orange-500/5 to-red-650/5 blur-[120px] pointer-events-none animate-pulse duration-[6000ms]" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[600px] h-[600px] rounded-full bg-gradient-to-tr from-blue-600/3 to-orange-500/4 blur-[150px] pointer-events-none animate-pulse duration-[8000ms]" />

      {/* Main Container */}
      <div className="w-full max-w-md p-6 relative z-10">
        {/* Brand Header */}
        <div className="flex flex-col items-center mb-8">
          <motion.div 
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: 'spring', stiffness: 200, damping: 15 }}
            className="inline-flex items-center justify-center p-3 bg-gradient-to-tr from-orange-500 to-red-600 rounded-2xl shadow-xl shadow-orange-500/10 mb-4"
          >
            <Activity className="w-8 h-8 text-white" />
          </motion.div>
          <span className="text-[10px] uppercase font-black tracking-[0.25em] text-orange-500 mb-1 leading-none text-center">
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
          {/* Top Subtle Border highlight */}
          <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-orange-500/30 to-transparent" />

          {/* Close button */}
          <button
            onClick={() => window.location.href = getTenantRedirectUrl(null)}
            className="absolute top-6 right-6 p-1.5 hover:bg-slate-100 rounded-xl text-slate-400 hover:text-slate-655 transition-all cursor-pointer z-20"
            title="Kembali ke Halaman Utama"
          >
            <X className="w-5 h-5" />
          </button>

          <h2 className="text-lg font-bold text-slate-800 mb-6">Masuk ke Akun Anda</h2>

          <form onSubmit={handleLogin} className="space-y-5">
            {/* Email Field */}
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-500">Email Address / Username</label>
              <div className="relative">
                <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">
                  <Mail className="w-4 h-4" />
                </span>
                <input
                  type="text"
                  required
                  placeholder="name@basarnas.go.id atau admin"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    setError('');
                  }}
                  className="w-full bg-slate-50 border border-slate-200 focus:border-orange-500/50 rounded-2xl py-3.5 pl-11 pr-4 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-4 focus:ring-orange-500/5 transition-all font-semibold focus:bg-white"
                />
              </div>
            </div>

            {/* Password Field */}
            <div className="space-y-1.5">
              <div className="flex justify-between items-center">
                <label className="text-xs font-bold text-slate-500">Kata Sandi</label>
              </div>
              <div className="relative">
                <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">
                  <Lock className="w-4 h-4" />
                </span>
                <input
                  type="password"
                  required
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    setError('');
                  }}
                  className="w-full bg-slate-50 border border-slate-200 focus:border-orange-500/50 rounded-2xl py-3.5 pl-11 pr-4 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-4 focus:ring-orange-500/5 transition-all font-semibold focus:bg-white"
                />
              </div>
            </div>

            {/* Error Message */}
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -5 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-3 bg-red-500/10 border border-red-500/20 rounded-2xl text-xs text-red-600 font-semibold flex items-center gap-2"
              >
                <ShieldAlert className="w-4 h-4 shrink-0" />
                <span>{error}</span>
              </motion.div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-4 bg-gradient-to-r from-orange-500 to-red-600 hover:from-orange-600 hover:to-red-700 text-white font-bold text-sm rounded-2xl shadow-lg shadow-orange-500/15 flex items-center justify-center gap-2 transition-all group disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" /> Memverifikasi...
                </>
              ) : (
                <>
                  Masuk <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
                </>
              )}
            </button>
          </form>
        </motion.div>
        
        {/* Copyright Footer */}
        <p className="text-[10px] text-slate-400 font-semibold text-center mt-8">
          © {new Date().getFullYear()} BASARNAS. All rights reserved.
        </p>
      </div>
    </div>
  );
}
