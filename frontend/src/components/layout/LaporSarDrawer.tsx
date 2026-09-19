'use client';

import { useState, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { 
  getChatSessions, 
  getChatSession, 
  sendWebUserMessage, 
  getWebChatSession,
  api,
  getMe,
  getPublicTenants,
  registerUser,
  getTenantSlug
} from '@/lib/api';
import { 
  Sparkles, 
  ExternalLink, 
  Info, 
  Bot, 
  Send, 
  Loader2,
  MessageCircle,
  X,
  Settings,
  MapPin,
  User,
  Phone,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ChevronDown,
  Home,
  Lock,
  Mail,
  Building,
  ArrowRight,
  ArrowLeft,
  ShieldAlert
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useLaporSar } from '@/providers/LaporSarProvider';
import { resolveTenantFromCity } from '@/lib/utils';

interface DateTimePickerProps {
  onSelect: (dateTimeString: string) => void;
  onClose: () => void;
}

function LaporSarDateTimePicker({ onSelect, onClose }: DateTimePickerProps) {
  const tzOffset = 7; // WIB (UTC+7)
  
  const getWibNow = () => {
    const utc = new Date();
    const wib = new Date(utc.getTime() + (tzOffset * 60 * 60 * 1000));
    return wib;
  };
  
  const now = getWibNow();
  const [viewDate, setViewDate] = useState(new Date(now.getFullYear(), now.getMonth(), 1));
  const [selectedDay, setSelectedDay] = useState<number>(now.getDate());
  const [selectedMonth, setSelectedMonth] = useState<number>(now.getMonth());
  const [selectedYear, setSelectedYear] = useState<number>(now.getFullYear());
  const [selectedHour, setSelectedHour] = useState<string>(
    String(now.getHours()).padStart(2, '0') + ":00"
  );
  
  const timeContainerRef = useRef<HTMLDivElement>(null);
  
  const realMonthNames = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember"
  ];
  
  const daysOfWeek = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  
  const hours = Array.from({ length: 24 }, (_, i) => {
    const h = String(i).padStart(2, '0');
    return `${h}:00`;
  });
  
  const handlePrevMonth = () => {
    setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() - 1, 1));
  };
  
  const handleNextMonth = () => {
    setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 1));
  };
  
  const handleHome = () => {
    const today = getWibNow();
    setViewDate(new Date(today.getFullYear(), today.getMonth(), 1));
    setSelectedDay(today.getDate());
    setSelectedMonth(today.getMonth());
    setSelectedYear(today.getFullYear());
  };
  
  const calendarDays = [];
  const year = viewDate.getFullYear();
  const month = viewDate.getMonth();
  
  const firstDay = new Date(year, month, 1);
  const startDayOfWeek = firstDay.getDay(); // 0 = Sunday, 1 = Monday, ...
  
  const prevMonthObj = new Date(year, month, 0);
  const prevMonthDays = prevMonthObj.getDate();
  for (let i = startDayOfWeek - 1; i >= 0; i--) {
    calendarDays.push({
      day: prevMonthDays - i,
      month: month === 0 ? 11 : month - 1,
      year: month === 0 ? year - 1 : year,
      isCurrentMonth: false
    });
  }
  
  const currentMonthDays = new Date(year, month + 1, 0).getDate();
  for (let i = 1; i <= currentMonthDays; i++) {
    calendarDays.push({
      day: i,
      month: month,
      year: year,
      isCurrentMonth: true
    });
  }
  
  const remaining = 42 - calendarDays.length;
  for (let i = 1; i <= remaining; i++) {
    calendarDays.push({
      day: i,
      month: month === 11 ? 0 : month + 1,
      year: month === 11 ? year + 1 : year,
      isCurrentMonth: false
    });
  }
  
  const scrollTime = (direction: 'up' | 'down') => {
    if (timeContainerRef.current) {
      const scrollAmount = 40;
      timeContainerRef.current.scrollTop += direction === 'down' ? scrollAmount : -scrollAmount;
    }
  };
  
  const handleConfirm = () => {
    const yyyy = selectedYear;
    const mm = String(selectedMonth + 1).padStart(2, '0');
    const dd = String(selectedDay).padStart(2, '0');
    onSelect(`${yyyy}-${mm}-${dd} jam ${selectedHour}`);
  };
  
  return (
    <div className="bg-white border border-gray-200 rounded-3xl shadow-2xl flex flex-col w-[310px] select-none text-gray-800 overflow-hidden font-sans border-t-4 border-t-orange-500">
      {/* Upper Area: Calendar & Time */}
      <div className="flex border-b border-gray-100 h-[220px]">
        {/* Left: Calendar Pane */}
        <div className="w-[210px] p-2 flex flex-col justify-between">
          {/* Calendar Header */}
          <div className="flex items-center justify-between pb-1.5 border-b border-gray-50 mb-1">
            <div className="flex items-center gap-0.5">
              <button 
                type="button" 
                onClick={handlePrevMonth}
                className="p-1 hover:bg-gray-100 rounded-lg text-gray-400 hover:text-gray-700 transition-colors"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </button>
              <button 
                type="button" 
                onClick={handleHome}
                className="p-1 hover:bg-gray-100 rounded-lg text-gray-400 hover:text-gray-700 transition-colors"
                title="Hari Ini"
              >
                <Home className="w-3.5 h-3.5" />
              </button>
            </div>
            
            <div className="text-[11px] font-bold text-gray-700 flex items-center gap-1">
              <span>{realMonthNames[month]}</span>
              <span className="text-gray-400 font-semibold">{year}</span>
            </div>
            
            <button 
              type="button" 
              onClick={handleNextMonth}
              className="p-1 hover:bg-gray-100 rounded-lg text-gray-400 hover:text-gray-700 transition-colors"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
          
          {/* Days of week header */}
          <div className="grid grid-cols-7 text-center text-[9px] font-extrabold text-gray-400 uppercase tracking-wider mb-1">
            {daysOfWeek.map(d => <span key={d}>{d}</span>)}
          </div>
          
          {/* Calendar Grid */}
          <div className="grid grid-cols-7 gap-y-0.5 text-center flex-1">
            {calendarDays.map((cell, idx) => {
              const isSelected = selectedDay === cell.day && selectedMonth === cell.month && selectedYear === cell.year;
              return (
                <button
                  key={idx}
                  type="button"
                  onClick={() => {
                    setSelectedDay(cell.day);
                    setSelectedMonth(cell.month);
                    setSelectedYear(cell.year);
                    if (cell.month !== month) {
                      setViewDate(new Date(cell.year, cell.month, 1));
                    }
                  }}
                  className={`text-[9.5px] py-0.5 font-bold transition-all flex items-center justify-center rounded-lg ${
                    !cell.isCurrentMonth ? 'text-gray-300' : 'text-gray-600 hover:bg-gray-55'
                  } ${
                    isSelected ? 'bg-orange-500 hover:bg-orange-600 text-white font-black shadow-md shadow-orange-500/20' : ''
                  }`}
                >
                  {cell.day}
                </button>
              );
            })}
          </div>
        </div>
        
        {/* Right: Time Scroll Pane */}
        <div className="w-[100px] border-l border-gray-100 flex flex-col justify-between relative bg-gray-50/30">
          {/* Up arrow */}
          <button 
            type="button"
            onClick={() => scrollTime('up')}
            className="w-full py-1 hover:bg-gray-100 flex items-center justify-center text-gray-400 hover:text-gray-600 border-b border-gray-100 transition-colors bg-white/90 z-10 shrink-0"
          >
            <ChevronUp className="w-3.5 h-3.5" />
          </button>
          
          {/* Scrollable list */}
          <div 
            ref={timeContainerRef}
            className="flex-1 overflow-y-auto py-0.5 space-y-0.5 scrollbar-none"
            style={{ scrollBehavior: 'smooth' }}
          >
            {hours.map(h => {
              const isSelected = selectedHour === h;
              return (
                <button
                  key={h}
                  type="button"
                  onClick={() => setSelectedHour(h)}
                  className={`w-full py-1.5 text-[10px] font-bold transition-all text-center block ${
                    isSelected 
                      ? 'bg-orange-500 text-white font-black shadow-sm' 
                      : 'text-gray-500 hover:bg-gray-100'
                  }`}
                >
                  {h}
                </button>
              );
            })}
          </div>
          
          {/* Down arrow */}
          <button 
            type="button"
            onClick={() => scrollTime('down')}
            className="w-full py-1 hover:bg-gray-100 flex items-center justify-center text-gray-400 hover:text-gray-600 border-t border-gray-100 transition-colors bg-white/90 z-10 shrink-0"
          >
            <ChevronDown className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
      
      {/* Footer: Confirm/Cancel Buttons */}
      <div className="p-2 bg-gray-55/30 flex items-center justify-end gap-1.5 border-t border-gray-100 rounded-b-3xl">
        <button
          type="button"
          onClick={onClose}
          className="px-3 py-1.5 text-[10px] font-extrabold text-gray-500 hover:bg-gray-100 hover:text-gray-700 rounded-xl transition-all border border-gray-200 bg-white active:scale-95 cursor-pointer"
        >
          Batal
        </button>
        <button
          type="button"
          onClick={handleConfirm}
          className="px-3.5 py-1.5 text-[10px] font-extrabold text-white bg-orange-600 hover:bg-orange-700 rounded-xl shadow-md shadow-orange-500/10 transition-all active:scale-95 cursor-pointer"
        >
          Konfirmasi
        </button>
      </div>
    </div>
  );
}

export function LaporSarDrawer() {
  const queryClient = useQueryClient();
  const {
    isLaporSarOpen,
    setIsLaporSarOpen,
    laporSarUserId,
    setLaporSarUserId,
    laporSarName,
    setLaporSarName,
    laporSarPhone,
    setLaporSarPhone,
    isLaporSarRegistered,
    setIsLaporSarRegistered
  } = useLaporSar();

  const [laporSarText, setLaporSarText] = useState('');
  const [isSendingWidgetMessage, setIsSendingWidgetMessage] = useState(false);
  const [showConfig, setShowConfig] = useState(false);
  const [isChatActive, setIsChatActive] = useState(false);
  const [showDatePicker, setShowDatePicker] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // New emergency usability states
  const [widgetStartMode, setWidgetStartMode] = useState<'selection' | 'auth'>('selection');
  const [isOnline, setIsOnline] = useState(true);

  // Monitor network status
  useEffect(() => {
    if (typeof window !== 'undefined') {
      setIsOnline(navigator.onLine);
      const handleOnline = () => setIsOnline(true);
      const handleOffline = () => setIsOnline(false);
      window.addEventListener('online', handleOnline);
      window.addEventListener('offline', handleOffline);
      return () => {
        window.removeEventListener('online', handleOnline);
        window.removeEventListener('offline', handleOffline);
      };
    }
  }, []);

  // Local inputs for registration
  const [regName, setRegName] = useState('');
  const [regPhone, setRegPhone] = useState('');
  const [regError, setRegError] = useState('');

  // Integrated authentication states for the widget
  const [authTab, setAuthTab] = useState<'login' | 'register'>('login');
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regTenant, setRegTenant] = useState('pusat');
  const [regUserCity, setRegUserCity] = useState('');
  const [isRegistering, setIsRegistering] = useState(false);

  const [userProfile, setUserProfile] = useState<any>(null);
  const [isFetchingProfile, setIsFetchingProfile] = useState(false);

  // Fetch active tenants for widget registration dropdown
  const { data: widgetTenants = [] } = useQuery({
    queryKey: ['widgetPublicTenants'],
    queryFn: getPublicTenants,
    enabled: isLaporSarOpen,
  });

  // Sync user profile when token is present
  useEffect(() => {
    const syncUserProfile = async () => {
      if (typeof window === 'undefined') return;
      const token = localStorage.getItem('token');
      if (token) {
        setIsFetchingProfile(true);
        try {
          const user = await getMe();
          if (user) {
            setUserProfile(user);
            setLaporSarName(user.name);
            setLaporSarPhone(user.phone || '');
            setLaporSarUserId(`user_${user.id}`);
            setIsLaporSarRegistered(true);
          }
        } catch (err) {
          console.error('Failed to sync profile in LaporSarDrawer:', err);
        } finally {
          setIsFetchingProfile(false);
        }
      } else {
        setUserProfile(null);
      }
    };

    if (isLaporSarOpen) {
      syncUserProfile();
    }
  }, [isLaporSarOpen]);

  const handleWidgetLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError('');
    setIsLoggingIn(true);

    try {
      const { data } = await api.post('/auth/login', {
        username: loginEmail,
        password: loginPassword,
      });

      if (data.access_token) {
        localStorage.setItem('token', data.access_token);
        const user = await getMe();
        if (user) {
          setUserProfile(user);
          setLaporSarName(user.name);
          setLaporSarPhone(user.phone || '');
          setLaporSarUserId(`user_${user.id}`);
          setIsLaporSarRegistered(true);
        }
      } else {
        setLoginError('Gagal mendapatkan token autentikasi.');
      }
    } catch (err: any) {
      console.error(err);
      let msg = 'Kombinasi email dan kata sandi salah.';
      if (err.response?.status === 401) {
        msg = 'Username atau password salah.';
      } else if (err.response?.data?.detail) {
        msg = err.response.data.detail;
      }
      setLoginError(msg);
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleWidgetRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setRegError('');

    if (!regName.trim() || !regEmail.trim() || !regPhone.trim() || !regPassword.trim() || !regUserCity.trim()) {
      setRegError('Semua kolom wajib diisi.');
      return;
    }

    setIsRegistering(true);

    try {
      await registerUser({
        name: regName.trim(),
        email: regEmail.trim(),
        phone: regPhone.trim(),
        password: regPassword.trim(),
        role: 'User',
      }, regTenant);

      // Auto login on success
      const { data } = await api.post('/auth/login', {
        username: regEmail.trim(),
        password: regPassword.trim(),
      });

      if (data.access_token) {
        localStorage.setItem('token', data.access_token);
        const user = await getMe();
        if (user) {
          setUserProfile(user);
          setLaporSarName(user.name);
          setLaporSarPhone(user.phone || '');
          setLaporSarUserId(`user_${user.id}`);
          setIsLaporSarRegistered(true);
        }
      }
    } catch (err: any) {
      console.error(err);
      let msg = 'Registrasi gagal. Silakan coba lagi.';
      if (err.response?.data?.detail) {
        msg = err.response.data.detail;
      }
      setRegError(msg);
    } finally {
      setIsRegistering(false);
    }
  };

  // Sync local inputs when context values hydrate/change
  useEffect(() => {
    if (laporSarName) setRegName(laporSarName);
    if (laporSarPhone) setRegPhone(laporSarPhone);
  }, [laporSarName, laporSarPhone]);

  const [isLocating, setIsLocating] = useState(false);
  const [geoError, setGeoError] = useState<string | null>(null);
  const [showGeoPrompt, setShowGeoPrompt] = useState(false);

  const handleSosReport = async () => {
    setIsLocating(true);
    setGeoError(null);

    const finalName = laporSarName.trim() || 'Pelapor Darurat (SOS)';
    const finalPhone = laporSarPhone.trim() || '08123456789';
    if (!laporSarName.trim()) setLaporSarName(finalName);
    if (!laporSarPhone.trim()) setLaporSarPhone(finalPhone);

    const guestId = laporSarUserId || 'web_guest_' + Math.floor(10000 + Math.random() * 90000);
    if (!laporSarUserId) setLaporSarUserId(guestId);
    setIsLaporSarRegistered(true);

    const startSessionAndSend = async (messageText: string) => {
      setIsChatActive(true);
      setIsSendingWidgetMessage(true);
      try {
        const response = await sendWebUserMessage(
          guestId,
          messageText,
          finalName,
          finalPhone
        );
        queryClient.invalidateQueries({ queryKey: ['chatSessions'] });
        queryClient.invalidateQueries({ queryKey: ['webChatSession', guestId] });
      } catch (err) {
        console.error('Failed to send SOS message:', err);
      } finally {
        setIsSendingWidgetMessage(false);
      }
    };

    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        async (position) => {
          const { latitude, longitude } = position.coords;
          const msg = `🚨 LAPORAN DARURAT (SOS)\nLokasi GPS: ${latitude}, ${longitude}\n(Mohon bantuan darurat di koordinat ini)`;
          await startSessionAndSend(msg);
          setIsLocating(false);
        },
        async (error) => {
          console.error("Geo error:", error);
          let errText = "Akses lokasi ditolak. Silakan ketik lokasi Anda.";
          if (error.code === error.PERMISSION_DENIED) {
            errText = "Izin lokasi ditolak. Aktifkan lokasi untuk SOS cepat.";
          } else if (error.code === error.POSITION_UNAVAILABLE) {
            errText = "Sinyal GPS tidak tersedia.";
          } else if (error.code === error.TIMEOUT) {
            errText = "Pencarian lokasi GPS habis waktu.";
          }
          setGeoError(errText);
          await startSessionAndSend("🚨 LAPORAN DARURAT (SOS) - Gagal mendapatkan lokasi GPS.");
          setIsLocating(false);
        },
        { enableHighAccuracy: true, timeout: 8000, maximumAge: 0 }
      );
    } else {
      setGeoError("Browser tidak mendukung GPS.");
      await startSessionAndSend("🚨 LAPORAN DARURAT (SOS) - Browser tidak mendukung GPS.");
      setIsLocating(false);
    }
  };

  // Fetch active session details directly
  const { data: activeSession = null, isLoading: isLoadingActiveSession } = useQuery({
    queryKey: ['webChatSession', laporSarUserId],
    queryFn: () => getWebChatSession(laporSarUserId),
    enabled: !!laporSarUserId && isLaporSarRegistered,
    refetchInterval: 15000, // Fallback polling
  });

  // Sync isChatActive if history is loaded
  useEffect(() => {
    if (activeSession && activeSession.conversation_history && activeSession.conversation_history.length > 0) {
      setIsChatActive(true);
    } else {
      setIsChatActive(false);
    }
  }, [activeSession]);

  // Global WebSocket for Real-Time Updates (handles all screens)
  useEffect(() => {
    const getWsUrl = () => {
      if (process.env.NEXT_PUBLIC_WS_URL) return process.env.NEXT_PUBLIC_WS_URL;
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || (typeof window !== 'undefined' ? `${window.location.protocol}//${window.location.hostname}:8000/api` : 'http://localhost:8000/api');
      if (apiUrl.startsWith('http')) {
        return apiUrl.replace(/^http/, 'ws').replace(/\/api\/?$/, '/api/ws');
      }
      return typeof window !== 'undefined' ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.hostname}:8000/api/ws` : 'ws://localhost:8000/api/ws';
    };
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
    const wsUrl = token ? `${getWsUrl()}?token=${token}` : getWsUrl();
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'chat_message') {
          // Invalidate both lists and detail queries globally
          queryClient.invalidateQueries({ queryKey: ['chatSessions'] });
          queryClient.invalidateQueries({ queryKey: ['webChatSession', laporSarUserId] });
          queryClient.invalidateQueries({ queryKey: ['chatSession'] });
          // Also invalidate reports/stats so dashboard updates in real-time
          queryClient.invalidateQueries({ queryKey: ['reports'] });
          queryClient.invalidateQueries({ queryKey: ['stats'] });
        }
      } catch (err) {
        console.error('Error parsing WS message in LaporSarDrawer:', err);
      }
    };

    ws.onclose = () => {
      console.log('Global WS Connection closed, retrying in 5 seconds...');
    };

    return () => ws.close();
  }, [queryClient]);

  // Scroll to bottom of chat history when history updates
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeSession?.conversation_history]);

  const handleSendWidget = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!laporSarText.trim()) return;

    setIsSendingWidgetMessage(true);
    try {
      const response = await sendWebUserMessage(
        laporSarUserId,
        laporSarText,
        laporSarName,
        laporSarPhone
      );
      
      setLaporSarText('');
      queryClient.invalidateQueries({ queryKey: ['webChatSession', laporSarUserId] });
      queryClient.invalidateQueries({ queryKey: ['chatSessions'] });
    } catch (err) {
      console.error('Failed to send simulated message:', err);
    } finally {
      setIsSendingWidgetMessage(false);
    }
  };

  const handleSendWidgetOption = async (optionText: string) => {
    setIsSendingWidgetMessage(true);
    try {
      const response = await sendWebUserMessage(
        laporSarUserId,
        optionText,
        laporSarName,
        laporSarPhone
      );
      
      queryClient.invalidateQueries({ queryKey: ['webChatSession', laporSarUserId] });
      queryClient.invalidateQueries({ queryKey: ['chatSessions'] });
    } catch (err) {
      console.error('Failed to send option message:', err);
    } finally {
      setIsSendingWidgetMessage(false);
    }
  };

  // Auto-start chat with /start when drawer is opened, user is registered, and no active session exists
  useEffect(() => {
    if (isLaporSarOpen && isLaporSarRegistered && !activeSession && !isLoadingActiveSession && !isSendingWidgetMessage) {
      handleSendWidgetOption('/start');
    }
  }, [isLaporSarOpen, isLaporSarRegistered, activeSession, isLoadingActiveSession]);

  // Auto-open date picker when session state becomes AWAITING_WAKTU
  useEffect(() => {
    if (activeSession?.state === 'AWAITING_WAKTU') {
      setShowDatePicker(true);
    } else {
      setShowDatePicker(false);
    }
  }, [activeSession?.state]);

  return (
    <>
      {/* WEB CHAT WIDGET: Floating Chat Window */}
      <AnimatePresence>
        {isLaporSarOpen && (
          <motion.div 
            initial={{ opacity: 0, scale: 0.85, y: 50 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.85, y: 50 }}
            transition={{ type: 'spring', damping: 22, stiffness: 220 }}
            className="fixed bottom-6 right-6 w-[380px] max-w-[calc(100vw-32px)] h-[580px] max-h-[calc(100vh-48px)] bg-white shadow-[0_12px_40px_rgba(0,0,0,0.12)] z-50 flex flex-col border border-slate-100 rounded-3xl overflow-hidden"
          >
            {/* Header */}
            <div className="px-4.5 py-3.5 bg-gradient-to-r from-orange-500 via-orange-500 to-red-600 text-white flex items-center justify-between shadow-[0_2px_10px_rgba(249,115,22,0.1)] shrink-0">
              <div className="flex items-center gap-3">
                <div className="relative">
                  <div className="w-10 h-10 rounded-full bg-white flex items-center justify-center border border-white/20 overflow-hidden shrink-0">
                    <img src="/logo.png" alt="Lapor SAR Logo" className="w-8 h-8 object-contain" />
                  </div>
                  <span className="absolute bottom-0 right-0 w-3 h-3 bg-green-400 rounded-full border-2 border-orange-500" />
                </div>
                <div>
                  <h3 className="font-extrabold text-sm leading-tight flex items-center gap-1.5">
                    Lapor SAR <Sparkles className="w-3.5 h-3.5 text-yellow-300 animate-pulse" />
                  </h3>
                  <p className="text-[9px] text-orange-100 font-bold uppercase tracking-wider">Online • Hubungi Command Center</p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <button 
                  onClick={() => {
                    setIsLaporSarRegistered(false);
                    setWidgetStartMode('selection');
                  }}
                  className="p-1.5 text-orange-100 hover:bg-white/10 hover:text-white rounded-lg transition-colors"
                  title="Menu Utama Portal"
                >
                  <Home className="w-4 h-4 text-white" />
                </button>
                <button 
                  onClick={() => setShowConfig(!showConfig)}
                  className={`p-1.5 rounded-lg transition-colors ${showConfig ? 'bg-white/20 text-white' : 'text-orange-100 hover:bg-white/10 hover:text-white'}`}
                  title="Konfigurasi Lapor SAR"
                >
                  <Settings className="w-4 h-4" />
                </button>
                <button 
                  onClick={() => setIsLaporSarOpen(false)}
                  className="p-1.5 text-orange-100 hover:bg-white/10 hover:text-white rounded-full transition-all active:scale-90"
                  title="Tutup Obrolan"
                >
                  <X className="w-4.5 h-4.5 text-white" />
                </button>
              </div>
            </div>

            {/* Collapsible Simulation Config Panel */}
            <AnimatePresence>
              {showConfig && (
                <motion.div 
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="bg-gray-50 border-b border-gray-100 overflow-hidden shrink-0"
                >
                  <div className="p-3.5 space-y-3">
                    <div className="grid grid-cols-2 gap-2">
                      <div className="space-y-1">
                        <label className="text-[9px] font-bold text-gray-500 uppercase pl-0.5">Nama Pengirim</label>
                        <input
                          type="text"
                          value={laporSarName}
                          onChange={(e) => setLaporSarName(e.target.value)}
                          className="w-full bg-white border border-gray-200 rounded-lg px-2 py-1 text-xs text-gray-700 focus:outline-none focus:ring-1 focus:ring-orange-500"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-[9px] font-bold text-gray-500 uppercase pl-0.5">No Telepon</label>
                        <input
                          type="text"
                          value={laporSarPhone}
                          onChange={(e) => setLaporSarPhone(e.target.value)}
                          className="w-full bg-white border border-gray-200 rounded-lg px-2 py-1 text-xs text-gray-700 focus:outline-none focus:ring-1 focus:ring-orange-500"
                        />
                      </div>
                    </div>

                    <div className="flex items-center justify-between gap-2 pt-2 border-t border-gray-200/50">
                      <div className="min-w-0">
                        <p className="text-[9px] text-gray-400">ID Sesi Pelapor:</p>
                        <p className="text-[10px] font-mono font-bold text-gray-500 truncate max-w-[150px]">{laporSarUserId}</p>
                      </div>
                      
                      <div className="flex gap-1.5">
                        <button
                          onClick={() => {
                            setLaporSarUserId('web_user_' + Math.floor(10000 + Math.random() * 90000));
                            setIsChatActive(false);
                          }}
                          className="py-1 px-2 border border-gray-200 hover:border-orange-500 hover:text-orange-600 text-gray-500 font-semibold text-[9px] rounded bg-white transition-colors"
                          title="Reset sesi chat baru"
                        >
                          Reset Sesi
                        </button>
                        <button
                          onClick={() => {
                            setIsLaporSarRegistered(false);
                            setLaporSarName('');
                            setLaporSarPhone('');
                            setRegName('');
                            setRegPhone('');
                            setLaporSarUserId('web_user_' + Math.floor(10000 + Math.random() * 90000));
                            setIsChatActive(false);
                            if (typeof window !== 'undefined') {
                              localStorage.removeItem('sarbot_lapor_sar_registered');
                              localStorage.removeItem('sarbot_lapor_sar_name');
                              localStorage.removeItem('sarbot_lapor_sar_phone');
                            }
                          }}
                          className="py-1 px-2 border border-rose-200 hover:border-rose-500 hover:text-rose-600 text-rose-500 font-semibold text-[9px] rounded bg-white transition-colors"
                          title="Hapus data registrasi dan daftar ulang"
                        >
                          Reset Daftar
                        </button>
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {!isLaporSarRegistered ? (
              widgetStartMode === 'selection' ? (
                /* Layar Pemilihan Awal (Lapor Cepat vs Saksi) */
                <div className="flex-1 overflow-y-auto p-5 bg-slate-50/50 flex flex-col justify-start pt-8 min-h-0 font-sans">
                  <div className="text-center space-y-2 shrink-0 mb-3">
                    <div className="mx-auto h-14 w-14 bg-white rounded-2xl flex items-center justify-center shadow-md shadow-orange-500/5 border border-slate-100 overflow-hidden">
                      <img src="/logo.png" alt="Lapor SAR Logo" className="w-10 h-10 object-contain" />
                    </div>
                    <div>
                      <h3 className="text-sm font-black text-slate-800 tracking-wide">Portal Darurat Lapor SAR</h3>
                      <p className="text-[10.5px] text-slate-500 font-medium max-w-[250px] mx-auto leading-relaxed">
                        Pilih jenis laporan Anda untuk respon penyelamatan tercepat.
                      </p>
                    </div>
                  </div>

                  <div className="space-y-3">
                    {/* Tombol 1: Lapor Cepat (GPS SOS) */}
                    <button
                      onClick={handleSosReport}
                      disabled={isLocating}
                      className="w-full p-3.5 bg-gradient-to-r from-red-650 to-orange-600 hover:from-red-700 hover:to-orange-700 text-white rounded-2xl shadow-md hover:shadow-lg hover:shadow-red-500/10 hover:scale-[1.01] active:scale-98 transition-all cursor-pointer text-left flex items-start gap-3.5 border border-red-500/20 group relative overflow-hidden"
                    >
                      <div className="absolute right-0 bottom-0 translate-x-2 translate-y-2 opacity-5 scale-150 group-hover:scale-[1.7] transition-transform duration-300">
                        <ShieldAlert className="w-20 h-20 text-white" />
                      </div>
                      <div className="p-2.5 bg-white/15 rounded-xl shrink-0 mt-0.5">
                        {isLocating ? (
                          <Loader2 className="w-5 h-5 animate-spin text-white" />
                        ) : (
                          <MapPin className="w-5 h-5 text-white animate-bounce" />
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <h4 className="font-black text-xs uppercase tracking-wide flex items-center gap-1">
                          🚨 Lapor Cepat <span className="text-[9px] font-semibold text-red-100 font-normal lowercase">(SOS Instan)</span>
                        </h4>
                        <p className="text-[9.5px] text-red-100 pt-0.5 font-medium leading-relaxed">
                          Saya korban / di lokasi. Kirim koordinat GPS saya sekarang tanpa chat.
                        </p>
                      </div>
                    </button>

                    {/* Tombol 2: Laporkan Kejadian (Chat AI) */}
                    <button
                      onClick={() => setWidgetStartMode('auth')}
                      className="w-full p-3.5 bg-white hover:bg-slate-50 text-slate-800 rounded-2xl shadow-sm hover:shadow-md border border-slate-200/80 hover:scale-[1.01] active:scale-98 transition-all cursor-pointer text-left flex items-start gap-3.5 group relative overflow-hidden"
                    >
                      <div className="absolute right-0 bottom-0 translate-x-2 translate-y-2 opacity-5 scale-150 group-hover:scale-[1.7] transition-transform duration-300">
                        <MessageCircle className="w-20 h-20 text-slate-800" />
                      </div>
                      <div className="p-2.5 bg-orange-100 rounded-xl shrink-0 mt-0.5">
                        <MessageCircle className="w-5 h-5 text-orange-600" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <h4 className="font-black text-xs text-slate-850 uppercase tracking-wide">
                          📝 Laporkan Kejadian
                        </h4>
                        <p className="text-[9.5px] text-slate-500 pt-0.5 font-medium leading-relaxed">
                          Saya saksi / ingin melapor detail musibah via Obrolan AI Chatbot.
                        </p>
                      </div>
                    </button>

                    {/* Tombol 3: Bantuan SAR Lainnya (RAG Knowledge QA) */}
                    <button
                      onClick={async () => {
                        setIsLaporSarRegistered(true);
                        const guestId = laporSarUserId || 'web_user_' + Math.floor(10000 + Math.random() * 90000);
                        setLaporSarUserId(guestId);
                        setIsChatActive(true);
                        setIsSendingWidgetMessage(true);
                        try {
                          await sendWebUserMessage(guestId, '/bantuan', laporSarName || 'Pelapor Web', laporSarPhone || '');
                          queryClient.invalidateQueries({ queryKey: ['webChatSession', guestId] });
                          queryClient.invalidateQueries({ queryKey: ['chatSessions'] });
                        } catch (err) {
                          console.error('Failed to start Bantuan SAR session:', err);
                        } finally {
                          setIsSendingWidgetMessage(false);
                        }
                      }}
                      className="w-full p-3.5 bg-white hover:bg-slate-50 text-slate-800 rounded-2xl shadow-sm hover:shadow-md border border-slate-200/80 hover:scale-[1.01] active:scale-98 transition-all cursor-pointer text-left flex items-start gap-3.5 group relative overflow-hidden"
                    >
                      <div className="absolute right-0 bottom-0 translate-x-2 translate-y-2 opacity-5 scale-150 group-hover:scale-[1.7] transition-transform duration-300">
                        <Info className="w-20 h-20 text-slate-800" />
                      </div>
                      <div className="p-2.5 bg-blue-100 rounded-xl shrink-0 mt-0.5">
                        <Info className="w-5 h-5 text-blue-600" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <h4 className="font-black text-xs text-slate-850 uppercase tracking-wide">
                          ℹ️ Bantuan SAR Lainnya
                        </h4>
                        <p className="text-[9.5px] text-slate-500 pt-0.5 font-medium leading-relaxed">
                          Tanya Jawab SOP, informasi penyelamatan, istilah SAR & kontak via AI.
                        </p>
                      </div>
                    </button>
                  </div>
                </div>
              ) : (
                /* Widget Authentication Interface (Masuk / Daftar) */
                <div className="flex-1 overflow-y-auto p-5 space-y-4 bg-slate-50/50 flex flex-col min-h-0 font-sans">
                  {/* Back button to Selection */}
                  <button
                    onClick={() => setWidgetStartMode('selection')}
                    className="flex items-center gap-1.5 text-slate-600 hover:text-orange-600 transition-colors font-extrabold text-[10px] cursor-pointer group self-start"
                  >
                    <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" />
                    Kembali ke Pilihan
                  </button>

                  {/* Brand Header */}
                  <div className="text-center space-y-2 shrink-0 py-2">
                    <div className="mx-auto h-12 w-12 bg-gradient-to-tr from-orange-500 to-red-600 rounded-2xl flex items-center justify-center shadow-lg shadow-orange-500/10">
                      <MessageCircle className="w-6 h-6 text-white" />
                    </div>
                    <div>
                      <h3 className="text-sm font-black text-slate-800 tracking-wide">Widget Lapor SAR</h3>
                      <p className="text-[10px] text-slate-400 font-medium max-w-[250px] mx-auto leading-relaxed">
                        Masuk atau daftarkan akun pelapor Anda untuk terhubung ke Kantor SAR.
                      </p>
                    </div>
                  </div>

                  {/* Tabs */}
                  <div className="flex bg-slate-100 p-1 rounded-xl shrink-0 border border-slate-200/30">
                    <button
                      type="button"
                      onClick={() => setAuthTab('login')}
                      className={`flex-1 py-1.5 text-[10px] font-extrabold rounded-lg transition-all cursor-pointer ${
                        authTab === 'login' 
                          ? 'bg-white text-slate-800 shadow-sm' 
                          : 'text-slate-550 hover:text-slate-800'
                      }`}
                    >
                      Masuk
                    </button>
                    <button
                      type="button"
                      onClick={() => setAuthTab('register')}
                      className={`flex-1 py-1.5 text-[10px] font-extrabold rounded-lg transition-all cursor-pointer ${
                        authTab === 'register' 
                          ? 'bg-white text-slate-800 shadow-sm' 
                          : 'text-slate-550 hover:text-slate-800'
                      }`}
                    >
                      Daftar Baru
                    </button>
                  </div>

                  {/* Forms container */}
                  <div className="flex-1 min-h-0">
                    <AnimatePresence mode="wait">
                      {authTab === 'login' ? (
                        <motion.form
                          key="login-form"
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          exit={{ opacity: 0, x: 10 }}
                          onSubmit={handleWidgetLogin}
                          className="space-y-3"
                        >
                          {loginError && (
                            <div className="bg-red-55/5 border border-red-100 p-2.5 rounded-xl flex items-start gap-1.5 text-[10px] text-red-650 font-semibold leading-relaxed">
                              <ShieldAlert className="w-3.5 h-3.5 text-red-500 shrink-0 mt-0.5" />
                              <span>{loginError}</span>
                            </div>
                          )}

                          <div className="space-y-1">
                            <label className="block text-[9px] font-bold text-slate-500 uppercase pl-0.5">Alamat Email</label>
                            <div className="relative">
                              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
                                <Mail className="w-3.5 h-3.5" />
                              </span>
                              <input
                                type="email"
                                required
                                placeholder="name@email.com"
                                value={loginEmail}
                                onChange={(e) => { setLoginEmail(e.target.value); setLoginError(''); }}
                                className="block w-full pl-9 pr-3 py-2 border border-slate-200 focus:border-orange-500 focus:ring-2 focus:ring-orange-500/10 outline-none transition-all text-slate-800 bg-white font-semibold rounded-xl text-xs"
                              />
                            </div>
                          </div>

                          <div className="space-y-1">
                            <label className="block text-[9px] font-bold text-slate-500 uppercase pl-0.5">Kata Sandi</label>
                            <div className="relative">
                              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
                                <Lock className="w-3.5 h-3.5" />
                              </span>
                              <input
                                type="password"
                                required
                                placeholder="••••••••"
                                value={loginPassword}
                                onChange={(e) => { setLoginPassword(e.target.value); setLoginError(''); }}
                                className="block w-full pl-9 pr-3 py-2 border border-slate-200 focus:border-orange-500 focus:ring-2 focus:ring-orange-500/10 outline-none transition-all text-slate-800 bg-white font-semibold rounded-xl text-xs"
                              />
                            </div>
                          </div>

                          <button
                            type="submit"
                            disabled={isLoggingIn}
                            className="w-full flex justify-center items-center gap-1.5 py-2.5 px-4 mt-2 bg-gradient-to-r from-orange-500 to-red-600 hover:from-orange-600 hover:to-red-700 text-white font-bold text-[11px] rounded-xl shadow-md shadow-orange-500/10 transition-all active:scale-95 disabled:opacity-55 cursor-pointer"
                          >
                            {isLoggingIn ? (
                              <>
                                <Loader2 className="w-3.5 h-3.5 animate-spin" /> Memverifikasi...
                              </>
                            ) : (
                              <>
                                Masuk Pelapor <ArrowRight className="w-3.5 h-3.5" />
                              </>
                            )}
                          </button>
                        </motion.form>
                      ) : (
                        <motion.form
                          key="register-form"
                          initial={{ opacity: 0, x: 10 }}
                          animate={{ opacity: 1, x: 0 }}
                          exit={{ opacity: 0, x: -10 }}
                          onSubmit={handleWidgetRegister}
                          className="space-y-3 py-1"
                        >
                          {regError && (
                            <div className="bg-red-55/5 border border-red-100 p-2.5 rounded-xl flex items-start gap-1.5 text-[10px] text-red-650 font-semibold leading-relaxed">
                              <ShieldAlert className="w-3.5 h-3.5 text-red-500 shrink-0 mt-0.5" />
                              <span>{regError}</span>
                            </div>
                          )}

                          <div className="space-y-1">
                            <label className="block text-[9px] font-bold text-slate-500 uppercase pl-0.5">Nama Lengkap</label>
                            <div className="relative">
                              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
                                <User className="w-3.5 h-3.5" />
                              </span>
                              <input
                                type="text"
                                required
                                placeholder="Contoh: Budi Santoso"
                                value={regName}
                                onChange={(e) => { setRegName(e.target.value); setRegError(''); }}
                                className="block w-full pl-9 pr-3 py-1.5 border border-slate-200 focus:border-orange-500 focus:ring-2 focus:ring-orange-500/10 outline-none transition-all text-slate-800 bg-white font-semibold rounded-xl text-xs"
                              />
                            </div>
                          </div>

                          <div className="space-y-1">
                            <label className="block text-[9px] font-bold text-slate-500 uppercase pl-0.5">Alamat Email</label>
                            <div className="relative">
                              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
                                <Mail className="w-3.5 h-3.5" />
                              </span>
                              <input
                                type="email"
                                required
                                placeholder="name@email.com"
                                value={regEmail}
                                onChange={(e) => { setRegEmail(e.target.value); setRegError(''); }}
                                className="block w-full pl-9 pr-3 py-1.5 border border-slate-200 focus:border-orange-500 focus:ring-2 focus:ring-orange-500/10 outline-none transition-all text-slate-800 bg-white font-semibold rounded-xl text-xs"
                              />
                            </div>
                          </div>

                          <div className="space-y-1">
                            <label className="block text-[9px] font-bold text-slate-500 uppercase pl-0.5">No. Telepon / WhatsApp</label>
                            <div className="relative">
                              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
                                <Phone className="w-3.5 h-3.5" />
                              </span>
                              <input
                                type="tel"
                                required
                                placeholder="Contoh: 08123456789"
                                value={regPhone}
                                onChange={(e) => { setRegPhone(e.target.value); setRegError(''); }}
                                className="block w-full pl-9 pr-3 py-1.5 border border-slate-200 focus:border-orange-500 focus:ring-2 focus:ring-orange-500/10 outline-none transition-all text-slate-800 bg-white font-semibold rounded-xl text-xs"
                              />
                            </div>
                          </div>

                          <div className="space-y-1">
                            <label className="block text-[9px] font-bold text-slate-500 uppercase pl-0.5">Kata Sandi</label>
                            <div className="relative">
                              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
                                <Lock className="w-3.5 h-3.5" />
                              </span>
                              <input
                                type="password"
                                required
                                placeholder="Minimal 6 karakter"
                                value={regPassword}
                                onChange={(e) => { setRegPassword(e.target.value); setRegError(''); }}
                                className="block w-full pl-9 pr-3 py-1.5 border border-slate-200 focus:border-orange-500 focus:ring-2 focus:ring-orange-500/10 outline-none transition-all text-slate-800 bg-white font-semibold rounded-xl text-xs"
                              />
                            </div>
                          </div>

                          <div className="space-y-1">
                            <label className="block text-[9px] font-bold text-slate-500 uppercase pl-0.5">Kota / Kabupaten Tempat Tinggal</label>
                            <div className="relative">
                              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
                                <MapPin className="w-3.5 h-3.5" />
                              </span>
                              <input
                                type="text"
                                required
                                placeholder="Contoh: Natuna, Surabaya, dll."
                                value={regUserCity}
                                onChange={(e) => {
                                  const val = e.target.value;
                                  setRegUserCity(val);
                                  setRegError('');
                                  const resolvedSlug = resolveTenantFromCity(val, widgetTenants);
                                  setRegTenant(resolvedSlug);
                                }}
                                className="block w-full pl-9 pr-3 py-1.5 border border-slate-200 focus:border-orange-500 focus:ring-2 focus:ring-orange-500/10 outline-none transition-all text-slate-800 bg-white font-semibold rounded-xl text-xs"
                              />
                            </div>
                            {regUserCity.trim() && (
                              <p className="text-[8px] text-orange-655 font-extrabold flex items-center gap-1 mt-1 pl-0.5">
                                <span className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-pulse"></span>
                                Kantor SAR Penanggung Jawab: {widgetTenants.find((t: any) => t.slug === regTenant)?.name || 'Kantor Basarnas Pusat'}
                              </p>
                            )}
                          </div>

                          <button
                            type="submit"
                            disabled={isRegistering}
                            className="w-full flex justify-center items-center gap-1.5 py-2.5 px-4 mt-2 bg-gradient-to-r from-orange-500 to-red-600 hover:from-orange-600 hover:to-red-700 text-white font-bold text-[11px] rounded-xl shadow-md shadow-orange-500/10 transition-all active:scale-95 disabled:opacity-55 cursor-pointer"
                          >
                            {isRegistering ? (
                              <>
                                <Loader2 className="w-3.5 h-3.5 animate-spin" /> Mendaftarkan...
                              </>
                            ) : (
                              <>
                                Daftar & Hubungkan <ArrowRight className="w-3.5 h-3.5" />
                              </>
                            )}
                          </button>
                        </motion.form>
                      )}
                    </AnimatePresence>
                  </div>
                </div>
              )) : (
              <>
                {/* Chat History Container */}
                <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50/50 flex flex-col min-h-0">
                  {/* Offline Warning Banner */}
                  {!isOnline && (
                    <div className="p-3.5 bg-red-600 border border-red-500 rounded-2xl text-xs text-white flex flex-col gap-2 shrink-0 shadow-lg shadow-red-500/10 font-sans animate-pulse">
                      <div className="flex gap-2">
                        <ShieldAlert className="w-4.5 h-4.5 shrink-0 text-white mt-0.5" />
                        <p className="leading-relaxed font-bold">
                          Koneksi Internet Terputus! Hubungi nomor fallback darurat Kantor SAR setempat.
                        </p>
                      </div>
                      <a
                        href={`tel:${widgetTenants.find((t: any) => t.slug === (getTenantSlug() || 'pusat'))?.fallback_phone || '115'}`}
                        className="w-full py-2 bg-white text-red-600 hover:bg-slate-50 font-black rounded-xl text-center shadow-md active:scale-95 transition-all text-xs"
                      >
                        📞 Telepon Sekarang: {widgetTenants.find((t: any) => t.slug === (getTenantSlug() || 'pusat'))?.fallback_phone || '115'}
                      </a>
                    </div>
                  )}

                  <div className="p-3.5 bg-orange-50/60 border border-orange-100 rounded-2xl text-xs text-orange-800 flex gap-2 shrink-0 shadow-sm font-sans">
                    <Info className="w-4.5 h-4.5 shrink-0 text-orange-500 mt-0.5" />
                    <p className="leading-relaxed font-semibold">
                      Silakan laporkan kejadian darurat di bawah. Obrolan ini terhubung langsung dengan Asisten Penyelamatan AI Kantor SAR.
                    </p>
                  </div>

                  {activeSession && activeSession.conversation_history && activeSession.conversation_history.length > 0 ? (
                    <div className="flex-1 space-y-3.5 overflow-y-auto pr-1 py-1">
                      {activeSession.conversation_history.map((msg: any, idx: number) => {
                        const isUser = msg.role === 'user';
                        return (
                          <div 
                            key={idx} 
                            className={`flex ${isUser ? 'justify-end' : 'justify-start'} items-end gap-2`}
                          >
                            {!isUser && (
                              <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-orange-550 to-red-500 text-white flex items-center justify-center shadow shrink-0 text-[10px] mb-1">
                                <Bot className="w-4 h-4 text-white" />
                              </div>
                            )}
                            <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} max-w-[80%] space-y-1.5`}>
                              <div className={`rounded-2xl px-3.5 py-2 text-xs shadow-sm ${
                                isUser 
                                  ? 'bg-gradient-to-r from-orange-500 to-red-600 text-white font-semibold rounded-br-none' 
                                  : 'bg-white text-slate-800 border border-slate-100 rounded-bl-none font-medium'
                              }`}>
                                <p className="leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                              </div>
                              
                              {/* Render Opsi Jawaban Pelapor */}
                              {!isUser && msg.buttons && msg.buttons.length > 0 && (
                                <div className="flex flex-wrap gap-1.5 pt-1 pl-1">
                                  {msg.buttons.map((btn: any, btnIdx: number) => {
                                    const btnText = typeof btn === 'object' ? (btn.text || '') : String(btn);
                                    const isLinkBtn = btnText.toLowerCase().includes('daftar widget');
                                    if (isLinkBtn) {
                                      return (
                                        <a
                                          key={btnIdx}
                                          href="/widget-registration"
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          className="px-3.5 py-2 bg-orange-50 hover:bg-orange-100/80 text-orange-700 font-extrabold border border-orange-200/60 rounded-full transition-all shadow-sm active:scale-95 cursor-pointer text-[10px] inline-flex items-center gap-1"
                                        >
                                          {btnText} <ExternalLink className="w-3 h-3" />
                                        </a>
                                      );
                                    }
                                    return (
                                      <button
                                        key={btnIdx}
                                        type="button"
                                        onClick={() => handleSendWidgetOption(btnText)}
                                        disabled={isSendingWidgetMessage}
                                        className="px-3.5 py-2 bg-orange-55/10 hover:bg-orange-100/60 disabled:bg-slate-100 disabled:text-slate-400 disabled:border-slate-200 text-orange-700 font-extrabold border border-orange-200/50 rounded-full transition-all shadow-sm active:scale-95 cursor-pointer text-[10px]"
                                      >
                                        {btnText}
                                      </button>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })}
                      <div ref={messagesEndRef} />
                    </div>
                  ) : (
                    /* Empty / Loading State */
                    <div className="flex-1 flex flex-col items-center justify-center text-center p-4 text-slate-400 space-y-3 my-auto font-sans">
                      <div className="relative flex items-center justify-center">
                        <div className="absolute w-12 h-12 rounded-full bg-orange-500/10 animate-ping duration-1000" />
                        <Loader2 className="w-8 h-8 animate-spin text-orange-500 relative z-10" />
                      </div>
                      <p className="text-xs font-bold text-slate-500">Memulai sesi obrolan...</p>
                    </div>
                  )}
                </div>

                {/* Calendar / Date-Time Picker Helper for simulated users */}
                {isChatActive && activeSession?.state === 'AWAITING_WAKTU' && (
                  <div className="px-4 py-2.5 bg-orange-50/50 border-t border-gray-100 flex items-center justify-between gap-2 shrink-0 shadow-inner">
                    <span className="text-[10px] font-bold text-orange-700 flex items-center gap-1">
                      📅 Pilih Waktu Kejadian:
                    </span>
                    <button
                      type="button"
                      onClick={() => setShowDatePicker(true)}
                      className="bg-white hover:bg-orange-50 border border-orange-200 rounded-full px-3.5 py-1 text-[10px] font-extrabold text-orange-700 transition-all active:scale-95 shadow-sm cursor-pointer"
                    >
                      Pilih Tanggal & Pukul...
                    </button>
                  </div>
                )}

                {/* Message Send Form */}
                <form 
                  onSubmit={handleSendWidget}
                  className="p-3.5 border-t border-gray-100 bg-white shrink-0 font-sans"
                >
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      placeholder="Ketik pesan laporan darurat di sini..."
                      value={laporSarText}
                      onChange={(e) => setLaporSarText(e.target.value)}
                      disabled={isSendingWidgetMessage}
                      className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-4 py-2 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 disabled:bg-slate-100 transition-all"
                    />
                    
                    {/* Tombol GPS Obrolan */}
                    <button
                      type="button"
                      onClick={handleSosReport}
                      disabled={isLocating || isSendingWidgetMessage}
                      className="p-2.5 bg-slate-100 hover:bg-orange-50 text-slate-500 hover:text-orange-600 rounded-full transition-all flex items-center justify-center shrink-0 disabled:opacity-50 cursor-pointer"
                      title="Kirim Lokasi GPS"
                    >
                      {isLocating ? (
                        <Loader2 className="w-4 h-4 animate-spin text-orange-500" />
                      ) : (
                        <MapPin className="w-4 h-4" />
                      )}
                    </button>

                    <button
                      type="submit"
                      disabled={!laporSarText.trim() || isSendingWidgetMessage}
                      className="p-2.5 bg-gradient-to-r from-orange-500 to-red-650 hover:from-orange-600 hover:to-red-750 text-white rounded-full shadow-md shadow-orange-500/10 transition-all flex items-center justify-center shrink-0 disabled:bg-slate-200 disabled:text-slate-400 disabled:shadow-none disabled:cursor-not-allowed cursor-pointer"
                    >
                      {isSendingWidgetMessage ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Send className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </form>
              </>
            )}

            {/* Date Time Picker Dropdown Overlay */}
            <AnimatePresence>
              {showDatePicker && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="absolute inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4"
                >
                  <motion.div
                    initial={{ scale: 0.9, y: 15 }}
                    animate={{ scale: 1, y: 0 }}
                    exit={{ scale: 0.9, y: 15 }}
                    transition={{ type: 'spring', damping: 22, stiffness: 220 }}
                  >
                    <LaporSarDateTimePicker
                      onSelect={(val) => {
                        setLaporSarText(val);
                        setShowDatePicker(false);
                      }}
                      onClose={() => setShowDatePicker(false)}
                    />
                  </motion.div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Floating Action Button (FAB) - Hidden when chat is open */}
      <AnimatePresence>
        {!isLaporSarOpen && (
          <motion.button
            key="lapor-sar-fab"
            initial={{ opacity: 0, scale: 0.8, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.8, y: 20 }}
            onClick={() => setIsLaporSarOpen(true)}
            className="fixed bottom-6 right-6 z-40 text-white shadow-2xl shadow-orange-500/30 flex items-center justify-center border border-orange-400/25 px-5 py-3.5 rounded-full bg-gradient-to-r from-orange-500 to-red-600 hover:from-orange-600 hover:to-red-700 hover:scale-105 active:scale-95 transition-all duration-200 cursor-pointer font-sans"
            title="Buka Lapor SAR"
          >
            <div className="flex items-center gap-2.5">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500 shadow-sm border border-white/20"></span>
              </span>
              <span className="font-extrabold text-xs uppercase tracking-widest leading-none">Lapor SAR</span>
              <Sparkles className="w-4 h-4 text-yellow-300 animate-pulse" />
            </div>
          </motion.button>
        )}
      </AnimatePresence>
    </>
  );
}
