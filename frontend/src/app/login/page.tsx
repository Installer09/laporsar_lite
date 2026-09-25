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
    <div className="min-h-screen w-screen relative overflow-hidden bg-slate-50 flex items-center justify-center font-sans antialiased">
      {/* Main Container */}
      <div className="w-full max-w-md p-6 relative z-10">
        {/* Brand Header */}
        <div className="flex flex-col items-center mb-6 text-center">
          <div className="w-12 h-12 mb-3 flex items-center justify-center">
            <img src="/logo.png" alt="Logo BASARNAS" className="w-12 h-12 object-contain" />
          </div>
          <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500 mb-1 leading-none">
            Badan Nasional Pencarian dan Pertolongan
          </span>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            Portal Petugas <span className="text-orange-600">Lapor SAR</span>
          </h1>
        </div>

        {/* Card */}
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
          className="bg-white border border-slate-200 p-7 rounded-2xl shadow-xs flex flex-col relative"
        >

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
              className="w-full py-3 bg-orange-600 hover:bg-orange-700 text-white font-semibold text-sm rounded-xl shadow-xs flex items-center justify-center gap-2 transition-colors cursor-pointer disabled:bg-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Memverifikasi...</span>
                </>
              ) : (
                <>
                  <span>Masuk</span>
                  <ArrowRight className="w-4 h-4" />
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
