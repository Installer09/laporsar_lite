'use client';

import { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  getChatSessions, 
  getChatSession, 
  sendOperatorMessage, 
  toggleAutopilot, 
  deleteChatSession
} from '@/lib/api';
import { 
  Search, 
  MessageSquare, 
  Send, 
  Bot, 
  User, 
  Phone, 
  Loader2, 
  Globe, 
  Calendar, 
  MapPin, 
  Users2, 
  RefreshCw, 
  Play, 
  Pause,
  MessageCircle,
  HelpCircle,
  Clock,
  Info,
  Trash2,
  ChevronDown,
  ChevronUp,
  FileText
} from 'lucide-react';
import { motion } from 'framer-motion';

export default function ChatPage() {
  const queryClient = useQueryClient();
  // States with useEffect for safe hydration-friendly local storage recovery
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [operatorMessage, setOperatorMessage] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showRawJson, setShowRawJson] = useState(false);
  const [sessionFilter, setSessionFilter] = useState<'all' | 'emergency' | 'info'>('all');

  const renderStateBadge = (state: string) => {
    if (!state || state === 'MAIN_MENU') {
      return (
        <span className="text-[9px] bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded font-semibold uppercase tracking-wide border border-slate-200">
          Menu Utama
        </span>
      );
    }
    if (state === 'MODE_BANTUAN') {
      return (
        <span className="text-[9px] bg-indigo-50 text-indigo-700 px-1.5 py-0.5 rounded font-semibold uppercase tracking-wide border border-indigo-200">
          Info SAR
        </span>
      );
    }
    if (state.startsWith('AWAITING_')) {
      return (
        <span className="text-[9px] bg-amber-50 text-amber-800 px-1.5 py-0.5 rounded font-semibold uppercase tracking-wide border border-amber-200">
          {state.replace('AWAITING_', 'Perlu ')}
        </span>
      );
    }
    if (state === 'CONFIRMING') {
      return (
        <span className="text-[9px] bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded font-semibold uppercase tracking-wide border border-blue-200">
          Konfirmasi
        </span>
      );
    }
    if (state === 'COMPLETED') {
      return (
        <span className="text-[9px] bg-emerald-50 text-emerald-700 px-1.5 py-0.5 rounded font-semibold uppercase tracking-wide border border-emerald-200">
          Selesai
        </span>
      );
    }
    return (
      <span className="text-[9px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded font-semibold uppercase tracking-wide border border-slate-200">
        {state}
      </span>
    );
  };

  // Hydrate states from localStorage on mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const savedSession = localStorage.getItem('sarbot_selected_session_id');
      if (savedSession) setSelectedSessionId(parseInt(savedSession, 10));
    }
  }, []);

  // Persist states to localStorage when they change
  useEffect(() => {
    if (selectedSessionId !== null) {
      localStorage.setItem('sarbot_selected_session_id', selectedSessionId.toString());
    } else {
      localStorage.removeItem('sarbot_selected_session_id');
    }
  }, [selectedSessionId]);

  const messagesEndRef = useRef<HTMLDivElement>(null);


  // Fetch all sessions
  const { 
    data: sessions = [], 
    isLoading: isLoadingSessions,
    isError: isErrorSessions,
    refetch: refetchSessions
  } = useQuery({
    queryKey: ['chatSessions'],
    queryFn: getChatSessions,
    refetchInterval: 15000, // Fallback polling every 15s
  });

  // Fetch active session details if selected
  const { 
    data: activeSession = null,
    isLoading: isLoadingActiveSession,
    refetch: refetchActiveSession
  } = useQuery({
    queryKey: ['chatSession', selectedSessionId],
    queryFn: () => selectedSessionId ? getChatSession(selectedSessionId) : Promise.resolve(null),
    enabled: !!selectedSessionId,
  });

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeSession?.conversation_history, isLoadingActiveSession]);



  // Send Operator Message Mutation
  const sendMessageMutation = useMutation({
    mutationFn: ({ id, message }: { id: number; message: string }) => sendOperatorMessage(id, message),
    onSuccess: (data) => {
      setOperatorMessage('');
      queryClient.invalidateQueries({ queryKey: ['chatSession', selectedSessionId] });
      queryClient.invalidateQueries({ queryKey: ['chatSessions'] });
    },
  });

  // Toggle Autopilot Mutation
  const toggleAutopilotMutation = useMutation({
    mutationFn: ({ id, autopilot }: { id: number; autopilot: boolean }) => toggleAutopilot(id, autopilot),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chatSession', selectedSessionId] });
      queryClient.invalidateQueries({ queryKey: ['chatSessions'] });
    },
  });

  // Delete Chat Session Mutation
  const deleteSessionMutation = useMutation({
    mutationFn: deleteChatSession,
    onSuccess: () => {
      setSelectedSessionId(null);
      queryClient.invalidateQueries({ queryKey: ['chatSessions'] });
    },
  });

  const handleDeleteSession = (id: number) => {
    if (window.confirm('Apakah Anda yakin ingin menghapus seluruh riwayat percakapan sesi ini secara permanen? Tindakan ini tidak dapat dibatalkan.')) {
      deleteSessionMutation.mutate(id);
    }
  };


  const handleSendOperator = (e: React.FormEvent) => {
    e.preventDefault();
    if (!operatorMessage.trim() || !selectedSessionId) return;
    sendMessageMutation.mutate({ id: selectedSessionId, message: operatorMessage });
  };

  const handleToggleBot = () => {
    if (!activeSession) return;
    toggleAutopilotMutation.mutate({ 
      id: activeSession.id, 
      autopilot: !activeSession.autopilot 
    });
  };

  const getPlatformBadge = (channel: string) => {
    switch (channel) {
      case 'telegram':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-md bg-sky-50 text-sky-700 border border-sky-200">
            <MessageCircle className="w-3 h-3 text-sky-600" /> Telegram
          </span>
        );
      case 'whatsapp':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200">
            <Phone className="w-3 h-3 text-emerald-600" /> WhatsApp
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 border border-slate-200">
            <Globe className="w-3 h-3 text-slate-600" /> Web Portal
          </span>
        );
    }
  };

  // Filter sessions based on search & category
  const filteredSessions = sessions.filter((s: any) => {
    const searchLower = searchQuery.toLowerCase();
    const nameMatch = (s.contact_name || '').toLowerCase().includes(searchLower);
    const idMatch = (s.user_id || '').toLowerCase().includes(searchLower);
    const phoneMatch = (s.contact_phone || '').toLowerCase().includes(searchLower);
    const matchesSearch = nameMatch || idMatch || phoneMatch;
    if (!matchesSearch) return false;

    const state = s.state || 'MAIN_MENU';
    if (sessionFilter === 'emergency') {
      return state.startsWith('AWAITING_') || state === 'CONFIRMING' || state === 'COMPLETED';
    }
    if (sessionFilter === 'info') {
      return state === 'MAIN_MENU' || state === 'MODE_BANTUAN';
    }
    return true;
  });

  const formatDataKorban = (dataKorban: any): string => {
    if (!dataKorban) return 'Belum diperoleh';
    
    // If it's a string, check if it's JSON
    if (typeof dataKorban === 'string') {
      const trimmed = dataKorban.trim();
      if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
        try {
          const parsed = JSON.parse(trimmed);
          return formatDataKorban(parsed);
        } catch (e) {
          // Fallback to plain string if JSON parse fails
        }
      }
      return trimmed;
    }

    // If it's an array, map each item cleanly
    if (Array.isArray(dataKorban)) {
      if (dataKorban.length === 0) return 'Belum diperoleh';
      return dataKorban.map((item, idx) => {
        if (typeof item === 'object' && item !== null) {
          const detail = Object.entries(item)
            .map(([k, v]) => {
              const label = k === 'kondisi' ? 'Kondisi' : k === 'nama' ? 'Nama' : k;
              return `${label}: ${typeof v === 'object' ? JSON.stringify(v) : v}`;
            })
            .join(' - ');
          return `[${idx + 1}] ${detail}`;
        }
        return `[${idx + 1}] ${String(item)}`;
      }).join(', ');
    }

    // If it's a single object
    if (typeof dataKorban === 'object' && dataKorban !== null) {
      // Check if it has conditions inside
      return Object.entries(dataKorban)
        .map(([k, v]) => {
          const label = k === 'kondisi' ? 'Kondisi' : k === 'nama' ? 'Nama' : k;
          return `${label}: ${typeof v === 'object' ? JSON.stringify(v) : v}`;
        })
        .join(', ');
    }

    return String(dataKorban);
  };


  return (
    <div className="h-[calc(100vh-8rem)] flex gap-6 overflow-hidden">
      {/* LEFT PANEL: Session List */}
      <div className="w-80 bg-white rounded-2xl border border-slate-200 flex flex-col shrink-0 overflow-hidden shadow-sm">
        <div className="p-4 border-b border-slate-100 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-bold text-slate-800 text-sm tracking-wide flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-slate-700" /> Saluran Obrolan SAR
            </h2>
            <button 
              onClick={() => refetchSessions()}
              className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
              title="Perbarui daftar sesi"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
          
          <div className="relative">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Cari kontak atau nomor..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400 focus:border-slate-400 font-medium"
            />
          </div>

          {/* Filter Tabs */}
          <div className="flex gap-1 bg-slate-100 p-1 rounded-xl">
            <button
              onClick={() => setSessionFilter('all')}
              className={`flex-1 py-1 text-[11px] font-semibold rounded-lg transition-all ${
                sessionFilter === 'all'
                  ? 'bg-white text-slate-800 shadow-xs'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              Semua
            </button>
            <button
              onClick={() => setSessionFilter('emergency')}
              className={`flex-1 py-1 text-[11px] font-semibold rounded-lg transition-all ${
                sessionFilter === 'emergency'
                  ? 'bg-white text-amber-800 shadow-xs'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              Darurat
            </button>
            <button
              onClick={() => setSessionFilter('info')}
              className={`flex-1 py-1 text-[11px] font-semibold rounded-lg transition-all ${
                sessionFilter === 'info'
                  ? 'bg-white text-indigo-700 shadow-xs'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              Menu & Info
            </button>
          </div>
        </div>

        {/* Sessions scrollable list */}
        <div className="flex-1 overflow-y-auto divide-y divide-slate-100 p-2 space-y-1">
          {isLoadingSessions ? (
            <div className="h-40 flex items-center justify-center flex-col gap-2 text-gray-400">
              <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
              <p className="text-xs">Memuat sesi chat...</p>
            </div>
          ) : isErrorSessions ? (
            <div className="h-40 flex flex-col items-center justify-center text-center p-4 text-slate-500 space-y-2">
              <HelpCircle className="w-8 h-8 text-slate-300" />
              <p className="text-xs font-semibold text-slate-700">Gagal memuat sesi chat</p>
              <button 
                onClick={() => refetchSessions()}
                className="px-3 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs rounded-lg transition-colors cursor-pointer"
              >
                Coba lagi
              </button>
            </div>
          ) : filteredSessions.length === 0 ? (
            <div className="h-40 flex flex-col items-center justify-center text-center p-4 text-gray-400 space-y-2">
              <HelpCircle className="w-8 h-8 text-gray-300" />
              <p className="text-sm font-medium">Tidak ada sesi chat</p>
              <p className="text-xs">Sesi pesan baru dari pelapor (WhatsApp, Telegram, atau Web) akan muncul di sini secara otomatis.</p>
            </div>
          ) : (
            filteredSessions.map((session: any) => {
              const isSelected = selectedSessionId === session.id;
              const lastMessage = session.conversation_history?.[session.conversation_history.length - 1]?.content || 'Mulai percakapan...';
              
              return (
                <button
                  key={session.id}
                  onClick={() => setSelectedSessionId(session.id)}
                  className={`w-full text-left p-3 rounded-xl transition-all duration-150 flex gap-3 items-start border cursor-pointer ${
                    isSelected 
                      ? 'bg-slate-50 border-slate-300 shadow-sm' 
                      : 'border-transparent hover:bg-slate-50'
                  }`}
                >
                  <div className="relative shrink-0 mt-0.5">
                    <div className="w-9 h-9 rounded-xl flex items-center justify-center text-white font-bold text-xs bg-slate-800 shadow-sm">
                      {session.contact_name ? session.contact_name.substring(0, 2).toUpperCase() : 'US'}
                    </div>
                    {session.autopilot && (
                      <span className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-emerald-500 border-2 border-white flex items-center justify-center text-[8px] text-white shadow-sm" title="Bot Autopilot Aktif">
                        <Bot className="w-2.5 h-2.5 text-white" />
                      </span>
                    )}
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-start gap-1">
                      <p className="font-bold text-slate-900 text-xs truncate">
                        {session.contact_name || 'Pelapor Anonim'}
                      </p>
                      <span className="text-[10px] text-slate-400 font-medium shrink-0">
                        {session.updated_at ? new Date(session.updated_at).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' }) : ''}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 truncate mt-0.5 font-normal">
                      {lastMessage}
                    </p>
                    <div className="flex gap-1.5 items-center mt-2 flex-wrap">
                      {getPlatformBadge(session.channel)}
                      {renderStateBadge(session.state)}
                    </div>
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>

      {/* CENTER PANEL: Main Conversation Thread */}
      <div className="flex-1 bg-white rounded-2xl border border-slate-200 flex flex-col overflow-hidden shadow-sm">
        {selectedSessionId && activeSession ? (
          <>
            {/* Conversation Header */}
            <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between gap-3 bg-slate-50/80">
              <div className="flex items-center gap-3 min-w-0 flex-1">
                <div className="w-9 h-9 rounded-xl bg-slate-900 text-white font-bold flex items-center justify-center shadow-sm shrink-0 text-xs">
                  {activeSession.contact_name ? activeSession.contact_name.substring(0, 2).toUpperCase() : 'US'}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-bold text-slate-900 text-sm truncate max-w-[180px]">
                      {activeSession.contact_name || 'Pelapor Anonim'}
                    </h3>
                    {getPlatformBadge(activeSession.channel)}
                    {renderStateBadge(activeSession.state)}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-slate-500 mt-0.5 flex-wrap">
                    {activeSession.contact_phone && (
                      <span className="flex items-center gap-1 font-mono text-xs">
                        <Phone className="w-3 h-3 text-slate-400" /> {activeSession.contact_phone}
                      </span>
                    )}
                    {activeSession.platform_username && (
                      <span className="text-slate-400 font-normal">
                        @{activeSession.platform_username}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Bot Autopilot Takeover Control */}
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={handleToggleBot}
                  disabled={toggleAutopilotMutation.isPending}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border transition-all text-xs font-semibold cursor-pointer shadow-sm ${
                    activeSession.autopilot 
                      ? 'bg-emerald-50 border-emerald-200 text-emerald-800 hover:bg-emerald-100' 
                      : 'bg-amber-50 border-amber-300 text-amber-900 hover:bg-amber-100'
                  }`}
                  title={activeSession.autopilot ? 'Klik untuk mengambil alih percakapan secara manual' : 'Klik untuk mengembalikan ke asisten AI'}
                >
                  {toggleAutopilotMutation.isPending ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : activeSession.autopilot ? (
                    <>
                      <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                      <span>Autopilot AI</span>
                      <span className="text-[10px] text-emerald-700 font-normal underline ml-0.5">Ambil Alih</span>
                    </>
                  ) : (
                    <>
                      <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                      <span>Operator Manual</span>
                      <span className="text-[10px] text-amber-700 font-normal underline ml-0.5">Kembalikan ke AI</span>
                    </>
                  )}
                </button>

                <button
                  onClick={() => handleDeleteSession(activeSession.id)}
                  disabled={deleteSessionMutation.isPending}
                  className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-xl transition-all border border-slate-200 hover:border-red-200 bg-white cursor-pointer"
                  title="Hapus Sesi Percakapan"
                >
                  {deleteSessionMutation.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Trash2 className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            {/* Message Thread History */}
            <div className="flex-1 overflow-y-auto p-6 bg-gray-50/50 space-y-4">
              {isLoadingActiveSession ? (
                <div className="h-full flex items-center justify-center flex-col gap-2 text-gray-400">
                  <Loader2 className="w-10 h-10 animate-spin text-slate-400" />
                  <p className="text-sm font-medium">Memuat percakapan...</p>
                </div>
              ) : activeSession.conversation_history.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center p-6 text-gray-400 space-y-2">
                  <MessageSquare className="w-12 h-12 text-gray-300" />
                  <p className="text-base font-bold">Percakapan Baru</p>
                  <p className="text-xs max-w-xs">Belum ada pesan pada sesi ini. Tulis pesan di bawah untuk menghubungi pelapor.</p>
                </div>
              ) : (
                activeSession.conversation_history.map((msg: any, idx: number) => {
                  const isUser = msg.role === 'user';
                  const isOperator = msg.sender === 'operator';
                  
                  return (
                    <div 
                      key={idx} 
                      className={`flex ${isUser ? 'justify-start' : 'justify-end'} items-end gap-2.5`}
                    >
                      {isUser && (
                        <div className="w-7 h-7 rounded-full bg-slate-700 text-white font-semibold text-xs flex items-center justify-center shrink-0 shadow-sm">
                          {activeSession.contact_name ? activeSession.contact_name.substring(0, 1).toUpperCase() : 'U'}
                        </div>
                      )}
                      
                      <div className="max-w-[72%] space-y-1">
                        <div className={`p-3.5 rounded-2xl text-sm leading-relaxed shadow-sm ${
                          isUser 
                            ? 'bg-white text-slate-800 rounded-bl-none border border-slate-200' 
                            : isOperator 
                            ? 'bg-slate-900 text-white rounded-br-none border border-slate-800'
                            : 'bg-white text-slate-800 rounded-br-none border border-slate-200'
                        }`}>
                          {!isUser && (
                            <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider mb-2">
                              {isOperator ? (
                                <span className="px-2 py-0.5 rounded bg-slate-900 text-white">Operator Command</span>
                              ) : (
                                <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 flex items-center gap-1 border border-slate-200">
                                  <Bot className="w-3 h-3 text-slate-700" /> Otomatisasi AI
                                </span>
                              )}
                            </div>
                          )}
                          <p className="whitespace-pre-wrap">{msg.content}</p>
                        </div>
                        <div className={`text-[10px] text-slate-400 flex items-center gap-1 ${isUser ? 'justify-start pl-1' : 'justify-end pr-1'}`}>
                          <Clock className="w-2.5 h-2.5 text-slate-400" />
                          {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' }) : 'Baru saja'}
                        </div>
                      </div>

                      {!isUser && (
                        <div className={`w-7 h-7 rounded-full text-white font-bold text-xs flex items-center justify-center shadow-sm shrink-0 ${
                          isOperator ? 'bg-slate-900' : 'bg-slate-900'
                        }`}>
                          {isOperator ? <User className="w-3.5 h-3.5 text-white" /> : <Bot className="w-3.5 h-3.5 text-white" />}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Calendar / Date-Time Picker Helper for AWAITING_WAKTU */}
            {activeSession.state === 'AWAITING_WAKTU' && !activeSession.autopilot && (
              <div className="px-4 py-2 bg-slate-100 border-t border-slate-200 flex items-center gap-2.5 shrink-0">
                <span className="text-xs font-semibold text-slate-800 flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-slate-700" /> Pilih Kalender Kejadian:
                </span>
                <input
                  type="datetime-local"
                  className="bg-white border border-slate-200 rounded-lg px-2.5 py-1 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-400/20 focus:border-slate-400"
                  onChange={(e) => {
                    if (e.target.value) {
                      const val = e.target.value.replace('T', ' ');
                      setOperatorMessage(val);
                    }
                  }}
                />
                <span className="text-[10px] text-slate-500 font-medium">(Otomatis dikonversi ke format PDTW)</span>
              </div>
            )}

            {/* Message Reply Input Area */}
            <form 
              onSubmit={handleSendOperator}
              className="p-3.5 border-t border-slate-200 flex items-center gap-2.5 bg-white"
            >
              <input
                type="text"
                placeholder={
                  activeSession.autopilot
                    ? "Matikan Autopilot di atas untuk mengirim instruksi langsung..."
                    : "Ketik pesan tanggapan operator ke pelapor..."
                }
                value={operatorMessage}
                onChange={(e) => setOperatorMessage(e.target.value)}
                disabled={activeSession.autopilot || sendMessageMutation.isPending}
                className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400/20 focus:border-slate-400 disabled:bg-slate-100 disabled:cursor-not-allowed"
              />
              <button
                type="submit"
                disabled={!operatorMessage.trim() || activeSession.autopilot || sendMessageMutation.isPending}
                className="px-4 py-2.5 bg-slate-900 hover:bg-slate-800 text-white text-sm font-semibold rounded-xl shadow-sm transition-all flex items-center justify-center gap-1.5 shrink-0 disabled:bg-slate-200 disabled:text-slate-400 disabled:shadow-none disabled:cursor-not-allowed"
              >
                {sendMessageMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    <span>Kirim</span>
                  </>
                )}
              </button>
            </form>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-8 text-slate-400 space-y-3">
            <div className="w-14 h-14 bg-slate-100 rounded-2xl flex items-center justify-center text-slate-500 border border-slate-200">
              <MessageSquare className="w-7 h-7" />
            </div>
            <div>
              <h3 className="font-bold text-slate-800 text-base">Pilih Sesi Komunikasi</h3>
              <p className="text-xs text-slate-500 max-w-sm mt-1 leading-relaxed">
                Pilih salah satu sesi di panel kiri untuk memantau pertukaran pesan, mengambil alih intervensi secara manual, atau memvalidasi parameter laporan.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* RIGHT PANEL: Visual AI Extraction Board */}
      <div className="w-80 bg-white rounded-2xl border border-slate-200 flex flex-col overflow-hidden shadow-sm shrink-0">
        <div className="p-4 border-b border-slate-200 bg-slate-50/70">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-slate-100 flex items-center justify-center text-slate-700 shrink-0">
              <FileText className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-slate-800 text-sm">Ekstraksi Parameter</h3>
              <p className="text-[11px] text-slate-500">Data hasil telaah otomatis percakapan</p>
            </div>
          </div>
        </div>

        {selectedSessionId && activeSession ? (
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Verification Status */}
            <div className={`p-3.5 rounded-xl border flex gap-2.5 ${
              activeSession.state === 'MAIN_MENU'
                ? 'bg-slate-50 border-slate-200 text-slate-800'
                : activeSession.state === 'MODE_BANTUAN'
                ? 'bg-indigo-50 border-indigo-200 text-indigo-900'
                : activeSession.state === 'CONFIRMING'
                ? 'bg-blue-50 border-blue-200 text-blue-900'
                : activeSession.state === 'COMPLETED'
                ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                : 'bg-amber-50 border-amber-200 text-amber-900'
            }`}>
              <Info className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <p className="text-[10px] font-bold uppercase tracking-wider">Tahap Penanganan</p>
                <p className="text-xs font-semibold leading-relaxed">
                  {activeSession.state === 'MAIN_MENU'
                    ? 'Pengguna berada di Menu Utama. Menunggu pemilihan layanan atau penyampaian musibah.'
                    : activeSession.state === 'MODE_BANTUAN'
                    ? 'Pengguna sedang berkonsultasi mengenai informasi dan SOP SAR melalui asisten AI.'
                    : activeSession.state === 'CONFIRMING'
                    ? 'Parameter lengkap. Menunggu konfirmasi verifikasi pelapor.'
                    : activeSession.state === 'COMPLETED'
                    ? 'Laporan terverifikasi dan tercatat ke sistem operasi.'
                    : 'Mengumpulkan parameter (Waktu, Lokasi, Korban) dari percakapan.'}
                </p>
              </div>
            </div>

            {/* Context-Aware Content */}
            {activeSession.state === 'MAIN_MENU' ? (
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-center space-y-2 text-slate-500">
                <Clock className="w-8 h-8 text-slate-400 mx-auto" />
                <p className="text-xs font-semibold text-slate-700">Pelaporan Belum Dimulai</p>
                <p className="text-[11px] leading-relaxed">
                  Pengguna baru mengakses menu utama dan belum memilih layanan pelaporan darurat.
                </p>
              </div>
            ) : activeSession.state === 'MODE_BANTUAN' ? (
              <div className="p-4 bg-indigo-50/60 border border-indigo-100 rounded-xl text-center space-y-2 text-indigo-700">
                <HelpCircle className="w-8 h-8 text-indigo-400 mx-auto" />
                <p className="text-xs font-semibold text-indigo-900">Konsultasi Informasi SAR</p>
                <p className="text-[11px] leading-relaxed text-indigo-600">
                  Pengguna sedang mencari informasi regulasi atau SOP SAR. Bot melayani secara otomatis (Autopilot AI).
                </p>
              </div>
            ) : (
              /* Extracted Fields Cards */
              <div className="space-y-2.5">
                {/* Field: Waktu */}
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80 flex gap-3 items-start">
                  <div className="p-2 bg-blue-100 text-blue-700 rounded-lg shrink-0">
                    <Calendar className="w-3.5 h-3.5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Waktu Kejadian (PDTW)</span>
                    <p className={`text-xs font-semibold mt-0.5 break-words ${
                      activeSession.extracted_data.waktu ? 'text-slate-800' : 'text-slate-400 italic'
                    }`}>
                      {activeSession.extracted_data.waktu || 'Belum diperoleh'}
                    </p>
                  </div>
                </div>

                {/* Field: Lokasi */}
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80 flex gap-3 items-start">
                  <div className="p-2 bg-emerald-100 text-emerald-700 rounded-lg shrink-0">
                    <MapPin className="w-3.5 h-3.5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Lokasi Kejadian</span>
                    <p className={`text-xs font-semibold mt-0.5 break-words ${
                      activeSession.extracted_data.lokasi_teks ? 'text-slate-800' : 'text-slate-400 italic'
                    }`}>
                      {activeSession.extracted_data.lokasi_teks || 'Belum diperoleh'}
                    </p>
                  </div>
                </div>

                {/* Field: Data Korban */}
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80 flex gap-3 items-start">
                  <div className="p-2 bg-rose-100 text-rose-700 rounded-lg shrink-0">
                    <Users2 className="w-3.5 h-3.5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Kondisi & Korban</span>
                    <p className={`text-xs font-semibold mt-0.5 break-words ${
                      activeSession.extracted_data.data_korban || activeSession.extracted_data.korban ? 'text-slate-800' : 'text-slate-400 italic'
                    }`}>
                      {formatDataKorban(activeSession.extracted_data.data_korban || activeSession.extracted_data.korban)}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Extracted JSON Collapsible Block */}
            <div className="pt-2 border-t border-slate-200">
              <button
                type="button"
                onClick={() => setShowRawJson(!showRawJson)}
                className="flex items-center justify-between w-full text-xs font-semibold text-slate-500 hover:text-slate-800 py-1 transition-colors"
              >
                <span>Inspeksi Raw JSON</span>
                {showRawJson ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>
              {showRawJson && (
                <pre className="mt-2 p-3 bg-slate-900 text-emerald-400 text-[11px] font-mono rounded-xl overflow-x-auto max-h-48 border border-slate-800 leading-normal">
                  {JSON.stringify(activeSession.extracted_data, null, 2)}
                </pre>
              )}
            </div>
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-slate-400 space-y-2">
            <Info className="w-7 h-7 text-slate-300" />
            <p className="text-xs text-slate-500">Pilih salah satu percakapan untuk meninjau ekstraksi parameter kejadian.</p>
          </div>
        )}
      </div>


    </div>
  );
}
