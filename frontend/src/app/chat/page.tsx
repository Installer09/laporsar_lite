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
  Sparkles, 
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
  ExternalLink,
  Info,
  Trash2
} from 'lucide-react';
import { motion } from 'framer-motion';
import { useLaporSar } from '@/providers/LaporSarProvider';

export default function ChatPage() {
  const queryClient = useQueryClient();
  // States with useEffect for safe hydration-friendly local storage recovery
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [operatorMessage, setOperatorMessage] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Lapor SAR Context
  const {
    isLaporSarOpen,
    setIsLaporSarOpen,
    laporSarUserId,
    setLaporSarUserId,
    laporSarName,
    setLaporSarName,
    laporSarPhone,
    setLaporSarPhone
  } = useLaporSar();

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

  // Synchronize fields with the active web session to allow seamless resumption
  useEffect(() => {
    if (activeSession && activeSession.channel === 'web') {
      setLaporSarUserId(activeSession.user_id);
      setLaporSarName(activeSession.contact_name || 'Pelapor Web');
      setLaporSarPhone(activeSession.contact_phone || '08123456789');
    }
  }, [activeSession, setLaporSarUserId, setLaporSarName, setLaporSarPhone]);


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
          <span className="flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <MessageCircle className="w-3 h-3 text-blue-400" /> Telegram
          </span>
        );
      case 'whatsapp':
        return (
          <span className="flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded-full bg-green-500/10 text-green-400 border border-green-500/20">
            <Phone className="w-3 h-3 text-green-400" /> WhatsApp
          </span>
        );
      default:
        return (
          <span className="flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Globe className="w-3 h-3 text-amber-400" /> Web Chat
          </span>
        );
    }
  };

  // Filter sessions based on search
  const filteredSessions = sessions.filter((s: any) => {
    const searchLower = searchQuery.toLowerCase();
    const nameMatch = (s.contact_name || '').toLowerCase().includes(searchLower);
    const idMatch = (s.user_id || '').toLowerCase().includes(searchLower);
    const phoneMatch = (s.contact_phone || '').toLowerCase().includes(searchLower);
    return nameMatch || idMatch || phoneMatch;
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
      <div className="w-80 bg-white rounded-2xl border border-gray-200 flex flex-col shrink-0 overflow-hidden shadow-sm">
        <div className="p-4 border-b border-gray-100 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-bold text-gray-800 text-lg flex items-center gap-2">
              <MessageSquare className="w-5 h-5 text-orange-600" /> Chat Manual
            </h2>
            <button 
              onClick={() => refetchSessions()}
              className="p-1.5 text-gray-400 hover:text-orange-600 hover:bg-orange-50 rounded-lg transition-colors"
              title="Refresh"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
          
          <div className="relative">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Cari kontak atau nomor..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-gray-50 border border-gray-200 rounded-xl pl-9 pr-4 py-2 text-sm text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500"
            />
          </div>

          <button
            onClick={() => setIsLaporSarOpen(true)}
            className="w-full py-2 px-3 bg-gradient-to-r from-orange-500 to-red-600 hover:from-orange-600 hover:to-red-700 text-white font-semibold text-xs rounded-xl shadow-md flex items-center justify-center gap-2 transition-all"
          >
            <Sparkles className="w-3.5 h-3.5" /> Buka Lapor SAR
          </button>
        </div>

        {/* Sessions scrollable list */}
        <div className="flex-1 overflow-y-auto divide-y divide-gray-50 p-2 space-y-1">
          {isLoadingSessions ? (
            <div className="h-40 flex items-center justify-center flex-col gap-2 text-gray-400">
              <Loader2 className="w-8 h-8 animate-spin text-orange-500" />
              <p className="text-xs">Memuat sesi chat...</p>
            </div>
          ) : filteredSessions.length === 0 ? (
            <div className="h-40 flex flex-col items-center justify-center text-center p-4 text-gray-400 space-y-2">
              <HelpCircle className="w-8 h-8 text-gray-300" />
              <p className="text-sm font-medium">Tidak ada sesi chat</p>
              <p className="text-xs">Gunakan widget Lapor SAR untuk membuat sesi chat web baru</p>
            </div>
          ) : (
            filteredSessions.map((session: any) => {
              const isSelected = selectedSessionId === session.id;
              const lastMessage = session.conversation_history?.[session.conversation_history.length - 1]?.content || 'Mulai percakapan...';
              
              return (
                <button
                  key={session.id}
                  onClick={() => setSelectedSessionId(session.id)}
                  className={`w-full text-left p-3 rounded-xl transition-all duration-200 flex gap-3 items-start border ${
                    isSelected 
                      ? 'bg-orange-50/70 border-orange-200/50 shadow-sm' 
                      : 'border-transparent hover:bg-gray-50'
                  }`}
                >
                  <div className="relative shrink-0 mt-0.5">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center text-white font-bold text-sm bg-gradient-to-tr ${
                      session.channel === 'whatsapp' 
                        ? 'from-green-500 to-emerald-600' 
                        : session.channel === 'telegram'
                        ? 'from-blue-500 to-sky-600'
                        : 'from-amber-500 to-orange-600'
                    }`}>
                      {session.contact_name ? session.contact_name.substring(0, 2).toUpperCase() : 'US'}
                    </div>
                    {session.autopilot && (
                      <span className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-green-500 border-2 border-white flex items-center justify-center text-[10px] text-white shadow" title="Bot Auto-Pilot Aktif">
                        <Bot className="w-3 h-3 text-white" />
                      </span>
                    )}
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-start gap-1">
                      <p className="font-semibold text-gray-800 text-sm truncate">
                        {session.contact_name || 'Pelapor Anonim'}
                      </p>
                      <span className="text-[10px] text-gray-400 font-medium shrink-0">
                        {session.updated_at ? new Date(session.updated_at).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' }) : ''}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 truncate mt-0.5">
                      {lastMessage}
                    </p>
                    <div className="flex gap-2 items-center mt-2">
                      <span className={`text-[10px] font-bold uppercase tracking-wider ${
                        session.channel === 'whatsapp' 
                          ? 'text-green-600' 
                          : session.channel === 'telegram'
                          ? 'text-blue-600'
                          : 'text-amber-600'
                      }`}>
                        {session.channel}
                      </span>
                      <span className="w-1 h-1 bg-gray-300 rounded-full"></span>
                      <span className="text-[10px] bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded font-semibold uppercase truncate max-w-[120px]">
                        {session.state.replace('AWAITING_', 'PERLU ')}
                      </span>
                    </div>
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>

      {/* CENTER PANEL: Main Conversation Thread */}
      <div className="flex-1 bg-white rounded-2xl border border-gray-200 flex flex-col overflow-hidden shadow-sm">
        {selectedSessionId && activeSession ? (
          <>
            {/* Conversation Header */}
            <div className="p-3.5 border-b border-gray-100 flex items-center justify-between gap-3 bg-gray-50/50">
              <div className="flex items-center gap-2.5 min-w-0 flex-1">
                <div className="w-9 h-9 rounded-full bg-gradient-to-br from-gray-700 to-gray-900 text-white font-bold flex items-center justify-center shadow shrink-0 text-sm">
                  {activeSession.contact_name ? activeSession.contact_name.substring(0, 2).toUpperCase() : 'US'}
                </div>
                <div className="min-w-0 flex-1">
                  <h3 className="font-bold text-gray-800 text-sm flex items-center gap-1.5 flex-wrap">
                    <span className="truncate max-w-[130px]">{activeSession.contact_name || 'Pelapor Anonim'}</span>
                    {getPlatformBadge(activeSession.channel)}
                  </h3>
                  <div className="flex items-center gap-1.5 text-[10px] text-gray-500 mt-0.5 flex-wrap font-medium">
                    {activeSession.contact_phone && (
                      <span className="flex items-center gap-0.5 truncate">
                        <Phone className="w-3 h-3 text-gray-400" /> {activeSession.contact_phone}
                      </span>
                    )}
                    {activeSession.platform_username && (
                      <span className="text-gray-400 truncate max-w-[90px]">
                        {activeSession.platform_username}
                      </span>
                    )}
                    <span className="w-1 h-1 bg-gray-300 rounded-full shrink-0"></span>
                    <span className="text-[9px] font-bold text-orange-600 bg-orange-50 px-1.5 py-0.5 rounded border border-orange-100 uppercase tracking-wide shrink-0">
                      {activeSession.state.replace('AWAITING_', 'PERLU ')}
                    </span>
                  </div>
                </div>
              </div>

              {/* Bot Autopilot Takeover Control */}
              <div className="flex items-center gap-1.5 shrink-0">
                <button
                  onClick={handleToggleBot}
                  disabled={toggleAutopilotMutation.isPending}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border transition-all shadow-sm font-bold text-[10px] uppercase tracking-wider ${
                    activeSession.autopilot 
                      ? 'bg-green-50 border-green-200 text-green-700 hover:bg-green-100' 
                      : 'bg-amber-50 border-amber-200 text-amber-700 hover:bg-amber-100'
                  }`}
                  title={activeSession.autopilot ? 'Klik untuk Jeda Bot (Ambil Alih)' : 'Klik untuk Aktifkan Kembali Bot'}
                >
                  {toggleAutopilotMutation.isPending ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : activeSession.autopilot ? (
                    <>
                      <Bot className="w-3.5 h-3.5 text-green-600 animate-pulse shrink-0" />
                      <span>Autopilot</span>
                    </>
                  ) : (
                    <>
                      <Pause className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                      <span>Takeover</span>
                    </>
                  )}
                </button>

                <button
                  onClick={() => handleDeleteSession(activeSession.id)}
                  disabled={deleteSessionMutation.isPending}
                  className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-xl transition-all border border-gray-200 hover:border-red-100 shadow-sm bg-white"
                  title="Hapus Sesi Chatting"
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
                  <Loader2 className="w-10 h-10 animate-spin text-orange-500" />
                  <p className="text-sm font-medium">Memuat percakapan...</p>
                </div>
              ) : activeSession.conversation_history.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center p-6 text-gray-400 space-y-2">
                  <MessageSquare className="w-12 h-12 text-gray-300" />
                  <p className="text-base font-bold">Percakapan Baru</p>
                  <p className="text-xs max-w-xs">Belum ada pesan pada sesi ini. Tulis tanggapan atau gunakan widget Lapor SAR untuk memulai.</p>
                </div>
              ) : (
                activeSession.conversation_history.map((msg: any, idx: number) => {
                  const isUser = msg.role === 'user';
                  const isOperator = msg.sender === 'operator';
                  
                  return (
                    <div 
                      key={idx} 
                      className={`flex ${isUser ? 'justify-start' : 'justify-end'} items-end gap-2`}
                    >
                      {isUser && (
                        <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-orange-400 to-red-500 text-white font-bold text-xs flex items-center justify-center shadow shrink-0">
                          {activeSession.contact_name ? activeSession.contact_name.substring(0, 1).toUpperCase() : 'U'}
                        </div>
                      )}
                      
                      <div className="max-w-[70%] space-y-1">
                        <div className={`p-3.5 rounded-2xl text-sm leading-relaxed shadow-sm ${
                          isUser 
                            ? 'bg-white text-gray-800 rounded-bl-none border border-gray-100' 
                            : isOperator 
                            ? 'bg-gradient-to-r from-orange-500 to-red-600 text-white rounded-br-none'
                            : 'bg-white text-gray-800 rounded-br-none border border-orange-100'
                        }`}>
                          {!isUser && (
                            <div className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider mb-1.5 opacity-80">
                              {isOperator ? (
                                <span className="px-1.5 py-0.5 rounded bg-white/20 text-white">Operator Command</span>
                              ) : (
                                <span className="px-1.5 py-0.5 rounded bg-orange-100 text-orange-700 flex items-center gap-0.5">
                                  <Bot className="w-2.5 h-2.5" /> AI Engine
                                </span>
                              )}
                            </div>
                          )}
                          <p className="whitespace-pre-wrap">{msg.content}</p>
                        </div>
                        <div className={`text-[10px] text-gray-400 flex items-center gap-1 ${isUser ? 'justify-start pl-1' : 'justify-end pr-1'}`}>
                          <Clock className="w-2.5 h-2.5 text-gray-300" />
                          {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' }) : 'Baru saja'}
                        </div>
                      </div>

                      {!isUser && (
                        <div className={`w-7 h-7 rounded-full text-white font-bold text-xs flex items-center justify-center shadow shrink-0 ${
                          isOperator ? 'bg-orange-600' : 'bg-gray-800'
                        }`}>
                          {isOperator ? <User className="w-4 h-4 text-white" /> : <Bot className="w-4 h-4 text-white" />}
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
              <div className="px-4 py-2 bg-orange-50/50 border-t border-orange-100 flex items-center gap-2.5 shrink-0">
                <span className="text-xs font-bold text-orange-700 flex items-center gap-1.5">
                  <Calendar className="w-4 h-4" /> Pilih Kalender Waktu Kejadian:
                </span>
                <input
                  type="datetime-local"
                  className="bg-white border border-orange-200 rounded-lg px-3 py-1 text-xs text-gray-700 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500"
                  onChange={(e) => {
                    if (e.target.value) {
                      const val = e.target.value.replace('T', ' ');
                      setOperatorMessage(val);
                    }
                  }}
                />
                <span className="text-[10px] text-gray-400 font-medium">(Terjemah otomatis ke PDTW oleh AI)</span>
              </div>
            )}

            {/* Message Reply Input Area */}
            <form 
              onSubmit={handleSendOperator}
              className="p-4 border-t border-gray-100 flex items-center gap-3 bg-white"
            >
              <input
                type="text"
                placeholder={
                  activeSession.autopilot
                    ? "Jeda Bot Auto-pilot terlebih dahulu untuk membalas manual..."
                    : "Ketik pesan balasan manual sebagai Operator..."
                }
                value={operatorMessage}
                onChange={(e) => setOperatorMessage(e.target.value)}
                disabled={activeSession.autopilot || sendMessageMutation.isPending}
                className="flex-1 bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
              />
              <button
                type="submit"
                disabled={!operatorMessage.trim() || activeSession.autopilot || sendMessageMutation.isPending}
                className="p-3 bg-orange-600 hover:bg-orange-700 text-white rounded-xl shadow-md transition-all flex items-center justify-center shrink-0 disabled:bg-gray-200 disabled:shadow-none disabled:cursor-not-allowed"
              >
                {sendMessageMutation.isPending ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Send className="w-5 h-5" />
                )}
              </button>
            </form>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-8 text-gray-400 space-y-4">
            <div className="w-20 h-20 bg-orange-50 rounded-full flex items-center justify-center text-orange-600 shadow-sm border border-orange-100">
              <MessageSquare className="w-10 h-10" />
            </div>
            <div>
              <h3 className="font-bold text-gray-800 text-lg">Pilih Sesi Chatting</h3>
              <p className="text-sm max-w-sm mt-1">Pilih salah satu sesi dari daftar sebelah kiri untuk memantau percakapan bot, melakukan takeover manual, atau memantau ekstraksi data AI.</p>
            </div>
          </div>
        )}
      </div>

      {/* RIGHT PANEL: Visual AI Extraction Board */}
      <div className="w-80 bg-white rounded-2xl border border-gray-200 flex flex-col overflow-hidden shadow-sm shrink-0">
        <div className="p-4 border-b border-gray-100 bg-gray-50/50">
          <h3 className="font-bold text-gray-800 text-sm flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-orange-600" /> AI Parameter Extraction
          </h3>
          <p className="text-[11px] text-gray-500 mt-0.5">Parameter kecelakaan yang berhasil dianalisis oleh AI secara real-time.</p>
        </div>

        {selectedSessionId && activeSession ? (
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Verification Status */}
            <div className={`p-4 rounded-xl border flex gap-3 ${
              activeSession.state === 'CONFIRMING'
                ? 'bg-blue-50 border-blue-200 text-blue-800'
                : activeSession.state === 'COMPLETED'
                ? 'bg-green-50 border-green-200 text-green-800'
                : 'bg-amber-50 border-amber-200 text-amber-800'
            }`}>
              <Info className="w-5 h-5 shrink-0" />
              <div className="space-y-1">
                <p className="text-xs font-bold uppercase tracking-wider">Status Validasi</p>
                <p className="text-xs leading-relaxed font-semibold">
                  {activeSession.state === 'CONFIRMING'
                    ? 'Data Lengkap! Menunggu konfirmasi Ya/Tidak dari pelapor.'
                    : activeSession.state === 'COMPLETED'
                    ? 'Laporan Tervalidasi & Berhasil Dikirimkan!'
                    : 'AI sedang mengekstraksi data dari teks percakapan pelapor.'}
                </p>
              </div>
            </div>

            {/* Extracted Fields Cards */}
            <div className="space-y-3">
              {/* Field: Waktu */}
              <div className="p-3.5 bg-gray-50 rounded-xl border border-gray-100 flex gap-3 items-start">
                <div className="p-2 bg-blue-100 text-blue-700 rounded-lg shrink-0">
                  <Calendar className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <span className="text-[10px] text-gray-400 font-bold uppercase">Waktu Kejadian</span>
                  <p className={`text-sm font-semibold mt-0.5 truncate ${
                    activeSession.extracted_data.waktu ? 'text-gray-800' : 'text-gray-400 italic'
                  }`}>
                    {activeSession.extracted_data.waktu || 'Belum diperoleh'}
                  </p>
                </div>
              </div>

              {/* Field: Lokasi */}
              <div className="p-3.5 bg-gray-50 rounded-xl border border-gray-100 flex gap-3 items-start">
                <div className="p-2 bg-emerald-100 text-emerald-700 rounded-lg shrink-0">
                  <MapPin className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <span className="text-[10px] text-gray-400 font-bold uppercase">Lokasi Kejadian</span>
                  <p className={`text-sm font-semibold mt-0.5 ${
                    activeSession.extracted_data.lokasi_teks ? 'text-gray-800' : 'text-gray-400 italic'
                  }`}>
                    {activeSession.extracted_data.lokasi_teks || 'Belum diperoleh'}
                  </p>
                </div>
              </div>

              {/* Field: Data Korban */}
              <div className="p-3.5 bg-gray-50 rounded-xl border border-gray-100 flex gap-3 items-start">
                <div className="p-2 bg-rose-100 text-rose-700 rounded-lg shrink-0">
                  <Users2 className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <span className="text-[10px] text-gray-400 font-bold uppercase">Kondisi & Jumlah Korban</span>
                  <p className={`text-sm font-semibold mt-0.5 ${
                    activeSession.extracted_data.data_korban || activeSession.extracted_data.korban ? 'text-gray-800' : 'text-gray-400 italic'
                  }`}>
                    {formatDataKorban(activeSession.extracted_data.data_korban || activeSession.extracted_data.korban)}
                  </p>
                </div>
              </div>
            </div>

            {/* Extracted JSON Debug Block */}
            <div className="space-y-1">
              <span className="text-[10px] text-gray-400 font-bold uppercase pl-1">Data Ekstraksi Lengkap</span>
              <pre className="p-3 bg-gray-900 text-green-400 text-xs font-mono rounded-xl overflow-x-auto max-h-48 border border-gray-800 leading-normal">
                {JSON.stringify(activeSession.extracted_data, null, 2)}
              </pre>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-gray-400 space-y-2">
            <Info className="w-8 h-8 text-gray-300" />
            <p className="text-xs">Pilih salah satu percakapan untuk melihat ekstraksi data AI secara visual.</p>
          </div>
        )}
      </div>


    </div>
  );
}
