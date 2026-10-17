'use client';

import { useState, useEffect, useRef } from 'react';
import { Bell, Search, Loader2, AlertTriangle, User, Menu, LogOut, HelpCircle, Settings } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { globalSearch, getReports } from '@/lib/api';
import { useSocket } from '@/hooks/useSocket';
import Link from 'next/link';
import { useSidebar } from '@/providers/SidebarProvider';
import { useLaporSar } from '@/providers/LaporSarProvider';
import { decodeJwt, getTenantRedirectUrl } from '@/lib/utils';

export function Header() {
  const { isSidebarOpen, toggleSidebar } = useSidebar();
  const { setSelectedGlobalReport, setIsGlobalReportDetailOpen } = useLaporSar();
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [showSearchDrop, setShowSearchDrop] = useState(false);
  const [showNotifDrop, setShowNotifDrop] = useState(false);
  const { clickedReportIds, markReportAsRead } = useLaporSar();
  
  const [isMounted, setIsMounted] = useState(false);
  const [userRole, setUserRole] = useState<string | null>(null);
  const [userName, setUserName] = useState<string | null>(null);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [tenantSlug, setTenantSlug] = useState<string | null>(null);
  const [showProfileDrop, setShowProfileDrop] = useState(false);
  
  const searchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        searchInputRef.current?.focus();
      } else if (e.key === '/' && document.activeElement?.tagName !== 'INPUT' && document.activeElement?.tagName !== 'TEXTAREA') {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);
  
  const searchRef = useRef<HTMLDivElement>(null);
  const notifRef = useRef<HTMLDivElement>(null);
  const profileRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      const payload = decodeJwt(token);
      if (payload) {
        setUserRole(payload.role || null);
        setUserName(payload.name || null);
        setUserEmail(payload.sub || null);
        setTenantSlug(payload.tenant_slug || null);
      }
    }
  }, []);

  const getInitials = (name: string | null, role: string | null) => {
    if (name && name.trim()) {
      const parts = name.trim().split(/\s+/);
      if (parts.length >= 2) {
        return (parts[0][0] + parts[1][0]).toUpperCase();
      }
      return name.slice(0, 2).toUpperCase();
    }
    if (role === 'Super Admin') return 'SA';
    if (role === 'Operator') return 'OP';
    if (role === 'User') return 'US';
    return 'AD';
  };

  const displayName = userName 
    || (userRole === 'Super Admin'
      ? 'Super Admin'
      : userRole === 'Operator'
      ? 'Operator SAR'
      : userRole === 'User'
      ? 'Pengguna'
      : tenantSlug && tenantSlug !== 'pusat'
      ? `Admin SAR ${tenantSlug.charAt(0).toUpperCase() + tenantSlug.slice(1)}`
      : 'Admin CC');
  
  const { isConnected } = useSocket();
  
  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const { data: searchResults, isFetching: isSearching } = useQuery({
    queryKey: ['search', debouncedQuery],
    queryFn: () => globalSearch(debouncedQuery),
    enabled: debouncedQuery.length >= 2,
  });

  const { data: reports } = useQuery({
    queryKey: ['reports_header'],
    queryFn: getReports,
    refetchInterval: 30000, // Refresh every 30s as backup to WebSocket
  });

  // Handle click outside to close dropdowns
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
        setShowSearchDrop(false);
      }
      if (notifRef.current && !notifRef.current.contains(event.target as Node)) {
        setShowNotifDrop(false);
      }
      if (profileRef.current && !profileRef.current.contains(event.target as Node)) {
        setShowProfileDrop(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleNotificationClick = (report: any) => {
    markReportAsRead(String(report.id));
    setSelectedGlobalReport(report);
    setIsGlobalReportDetailOpen(true);
    setShowNotifDrop(false);
  };

  const latestReports = reports && isMounted
    ? reports
        .filter((r: any) => r.status?.toUpperCase() === 'PENDING' || r.status?.toUpperCase() === 'AKTIF')
        .filter((r: any) => !clickedReportIds.includes(String(r.id)))
        .slice(0, 5)
    : [];

  return (
    <header className="h-20 bg-white border-b border-gray-100 flex items-center justify-between px-8 relative z-50">
      <div className="flex-1 max-w-xl flex items-center gap-4" ref={searchRef}>
        <button
          onClick={toggleSidebar}
          className="p-2.5 text-slate-500 hover:text-slate-900 hover:bg-slate-100 rounded-xl transition-all border border-transparent hover:border-slate-200 shrink-0"
          title={isSidebarOpen ? "Tutup Sidebar" : "Buka Sidebar"}
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="relative flex-1 flex items-center">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
          <input 
            ref={searchInputRef}
            type="text" 
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setShowSearchDrop(true);
            }}
            onFocus={() => setShowSearchDrop(true)}
            placeholder="Cari Laporan atau Kontak... (Tekan /)" 
            className="w-full pl-10 pr-12 py-2.5 bg-slate-50 border border-slate-200/60 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 focus:bg-white transition-all outline-none text-slate-800"
          />
          <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1.5 pointer-events-none">
            {isSearching ? (
              <Loader2 className="w-4 h-4 text-gray-400 animate-spin" />
            ) : (
              <kbd className="hidden sm:inline-block text-[10px] font-mono font-bold text-slate-400 bg-white border border-slate-200 px-1.5 py-0.5 rounded shadow-2xs">
                /
              </kbd>
            )}
          </div>
        </div>

        {/* Search Dropdown */}
        {showSearchDrop && searchQuery.length >= 2 && (
          <div className="absolute top-full left-8 mt-2 w-full max-w-xl bg-white border border-gray-100 rounded-xl shadow-lg overflow-hidden">
            <div className="p-2 max-h-96 overflow-y-auto">
              {!isSearching && (!searchResults?.reports?.length && !searchResults?.contacts?.length) && (
                <div className="p-4 text-center text-sm text-gray-500">Tidak ada hasil ditemukan.</div>
              )}
              
              {searchResults?.reports?.length > 0 && (
                <div className="mb-2">
                  <div className="px-3 py-1 text-xs font-bold text-gray-400 uppercase">Laporan</div>
                  {searchResults.reports.map((item: any) => (
                    <Link href={item.link} key={item.id} onClick={() => setShowSearchDrop(false)}>
                      <div className="px-3 py-2 hover:bg-gray-50 rounded-lg cursor-pointer">
                        <div className="text-sm font-semibold text-gray-900">{item.title}</div>
                        <div className="text-xs text-gray-500">{item.subtitle}</div>
                      </div>
                    </Link>
                  ))}
                </div>
              )}

              {searchResults?.contacts?.length > 0 && (
                <div>
                  <div className="px-3 py-1 text-xs font-bold text-gray-400 uppercase">Kontak</div>
                  {searchResults.contacts.map((item: any) => (
                    <Link href={item.link} key={item.id} onClick={() => setShowSearchDrop(false)}>
                      <div className="px-3 py-2 hover:bg-gray-50 rounded-lg cursor-pointer">
                        <div className="text-sm font-semibold text-gray-900 flex items-center gap-2">
                          <User className="w-3 h-3" /> {item.title}
                        </div>
                        <div className="text-xs text-gray-500">{item.subtitle}</div>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
      
      <div className="flex items-center gap-4">
        {/* Connection Status indicator */}
        <div 
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-slate-50 border border-slate-200/60 text-[11px] font-semibold text-slate-600 shadow-2xs" 
          title={isConnected ? 'WebSocket Terhubung Real-Time' : 'WebSocket Terputus (Mode Polling Cadangan)'}
        >
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-500' : 'bg-rose-500 animate-pulse'}`} />
          <span className="hidden sm:inline text-[10px] uppercase tracking-wider font-bold text-slate-500">
            {isConnected ? 'Live' : 'Offline'}
          </span>
        </div>

        <div className="relative" ref={notifRef}>
          <button 
            onClick={() => setShowNotifDrop(!showNotifDrop)}
            className="relative p-2.5 rounded-xl hover:bg-gray-50 text-gray-500 transition-colors"
          >
            <Bell className="w-5 h-5" />
            {latestReports.length > 0 && (
              <span className="absolute top-2 right-2.5 w-2 h-2 bg-red-500 rounded-full border-2 border-white"></span>
            )}
          </button>

          {/* Notifications Dropdown */}
          {showNotifDrop && (
            <div className="absolute right-0 top-full mt-2 w-80 bg-white border border-gray-100 rounded-xl shadow-lg overflow-hidden">
              <div className="p-4 border-b border-gray-100 flex justify-between items-center">
                <h3 className="font-bold text-gray-900">Notifikasi Terbaru</h3>
                <span className="text-xs bg-slate-100 text-slate-700 font-semibold px-2 py-0.5 rounded-full">{latestReports.length} Baru</span>
              </div>
              <div className="max-h-80 overflow-y-auto">
                {latestReports.length > 0 ? (
                  latestReports.map((report: any) => (
                    <div
                      key={report.id}
                      onClick={() => handleNotificationClick(report)}
                      className="block p-4 border-b border-gray-50 hover:bg-gray-50 transition-colors cursor-pointer"
                    >
                      <div className="flex gap-3">
                        <div className="w-8 h-8 rounded-full bg-red-50 flex items-center justify-center shrink-0">
                          <AlertTriangle className="w-4 h-4 text-red-500" />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-gray-900 line-clamp-1">{report.no_laporan || report.jenis_kejadian}</p>
                          <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{report.lokasi_teks}</p>
                          <p className="text-xs text-gray-400 mt-1">{new Date(report.created_at).toLocaleString('id-ID')}</p>
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="p-8 text-center text-sm text-gray-500">Belum ada notifikasi</div>
                )}
              </div>
              <div className="p-3 border-t border-gray-100 text-center">
                <Link href="/reports" onClick={() => setShowNotifDrop(false)} className="text-sm text-slate-900 font-semibold hover:text-slate-700">
                  Lihat Semua Laporan
                </Link>
              </div>
            </div>
          )}
        </div>

        {/* User Profile Dropdown */}
        <div className="relative" ref={profileRef}>
          <button
            onClick={() => setShowProfileDrop(!showProfileDrop)}
            className="flex items-center gap-2.5 p-1.5 hover:bg-slate-50 border border-transparent hover:border-slate-100 rounded-xl transition-all outline-none"
            title="Profil Pengguna"
          >
            <div className="w-8 h-8 rounded-full bg-slate-900 flex items-center justify-center text-white font-bold text-xs shadow-sm shrink-0">
              {getInitials(displayName, userRole)}
            </div>
            <div className="hidden sm:flex flex-col text-left min-w-0 pr-1">
              <span className="text-xs font-semibold text-slate-800 leading-none truncate max-w-[140px]" title={displayName}>
                {displayName}
              </span>
              <span className="text-[9px] text-slate-500 font-medium flex items-center gap-1 mt-0.5 leading-none">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span>
                <span className="text-green-600 font-semibold">Online</span>
                {tenantSlug && (
                  <span className="text-slate-400 font-mono">({tenantSlug.toUpperCase()})</span>
                )}
              </span>
            </div>
          </button>

          {showProfileDrop && (
            <div className="absolute right-0 top-full mt-2 w-56 bg-white border border-gray-100 rounded-xl shadow-lg overflow-hidden py-1 z-50">
              <div className="px-4 py-2.5 border-b border-gray-100 flex flex-col">
                <span className="text-xs font-bold text-slate-900 truncate" title={displayName}>
                  {displayName}
                </span>
                {userEmail && (
                  <span className="text-[10px] text-slate-500 truncate" title={userEmail}>
                    {userEmail}
                  </span>
                )}
                <div className="mt-1.5 flex items-center gap-1.5">
                  <span className="inline-block px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 font-mono text-[9px] font-semibold">
                    {tenantSlug ? `WORKSPACE: ${tenantSlug.toUpperCase()}` : 'WORKSPACE: PUSAT'}
                  </span>
                  <span className="text-[9px] text-emerald-600 font-bold flex items-center gap-1 ml-auto">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                    Online
                  </span>
                </div>
              </div>
              <div className="py-1 border-b border-gray-100">
                <Link
                  href="/help-center"
                  onClick={() => setShowProfileDrop(false)}
                  className="w-full flex items-center gap-2.5 px-4 py-2 text-xs font-semibold text-slate-700 hover:text-slate-900 hover:bg-slate-50 transition-colors"
                >
                  <HelpCircle className="w-4 h-4 text-slate-400" />
                  <span>Pusat Bantuan & SOP</span>
                </Link>
                <Link
                  href="/settings"
                  onClick={() => setShowProfileDrop(false)}
                  className="w-full flex items-center gap-2.5 px-4 py-2 text-xs font-semibold text-slate-700 hover:text-slate-900 hover:bg-slate-50 transition-colors"
                >
                  <Settings className="w-4 h-4 text-slate-400" />
                  <span>Pengaturan Sistem</span>
                </Link>
              </div>
              <button
                onClick={() => {
                  sessionStorage.setItem('logging_out', 'true');
                  localStorage.removeItem('token');
                  window.location.href = `${getTenantRedirectUrl(null)}/?logout=true`;
                }}
                className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm font-semibold text-rose-600 hover:text-rose-700 hover:bg-rose-50 transition-colors text-left"
              >
                <LogOut className="w-4 h-4 shrink-0" />
                <span>Keluar</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
