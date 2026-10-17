'use client';

import { useState, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  getKnowledgeBase, 
  createDictionaryWord, 
  updateDictionaryWord, 
  deleteDictionaryWord,
  exportDictionary,
  importDictionary,
  vectorizeAllDictionary
} from '@/lib/api';
import { decodeJwt } from '@/lib/utils';
import { 
  Search, 
  Book, 
  Plus, 
  Pencil, 
  Trash2, 
  X, 
  Loader2, 
  CheckCircle,
  HelpCircle,
  AlertCircle,
  Database,
  Lock,
  Download,
  Upload,
  AlertTriangle,
  Sparkles,
  Cpu,
  ArrowRight
} from 'lucide-react';
import { SkeletonLoader } from '@/components/ui/SkeletonLoader';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { motion, AnimatePresence } from 'framer-motion';

export default function KnowledgePage() {
  const queryClient = useQueryClient();
  const [userRole, setUserRole] = useState<string | null>(null);
  const [tenantSlug, setTenantSlug] = useState<string | null>(null);

  // Import/Export States
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importResult, setImportResult] = useState<any>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [importError, setImportError] = useState('');
  const [importIsGlobal, setImportIsGlobal] = useState(false);

  const handleExport = async () => {
    try {
      setIsExporting(true);
      const data = await exportDictionary();
      const url = window.URL.createObjectURL(new Blob([data], { type: 'text/csv;charset=utf-8;' }));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `laporsar_kamus_${new Date().toISOString().slice(0,10)}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error("Gagal mengekspor kamus:", err);
      alert("Gagal mengekspor data kamus.");
    } finally {
      setIsExporting(false);
    }
  };

  const handleTemplateDownload = () => {
    const headers = "Kata;Definisi;Contoh Kalimat;Tipe Kata;Sinonim Target;Apakah Typo/Slang;Tipe NER;Target NER;Status\n";
    const blob = new Blob(['\ufeff' + headers], { type: 'text/csv;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'template_kamus.csv');
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
      const res = await importDictionary(importFile, importIsGlobal);
      setImportResult(res);
      queryClient.invalidateQueries({ queryKey: ['knowledge'] });
    } catch (err: any) {
      console.error("Gagal mengimpor kamus:", err);
      setImportError(err.response?.data?.detail || 'Gagal mengimpor file CSV. Pastikan format kolom sesuai.');
    } finally {
      setIsImporting(false);
    }
  };

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      const payload = decodeJwt(token);
      if (payload) {
        setUserRole(payload.role);
        setTenantSlug(payload.tenant_slug || null);
      }
    }
  }, []);

  // ============================================================
  // KAMUS & ISTILAH STATE & MUTATIONS
  // ============================================================
  const SAR_CATEGORIES = [
    { value: 'ALL', label: 'SEMUA KATEGORI SAR', badgeColor: 'bg-gray-100 text-gray-700 border-gray-200' },
    { value: 'OPERASIONAL_SAR', label: 'OPERASIONAL & NAVIGASI', badgeColor: 'bg-blue-50 text-blue-700 border-blue-100' },
    { value: 'SARANA_ALUT', label: 'SARANA & ALUT', badgeColor: 'bg-cyan-50 text-cyan-700 border-cyan-100' },
    { value: 'JENIS_INSIDEN', label: 'JENIS MUSIBAH / INSIDEN', badgeColor: 'bg-rose-50 text-rose-700 border-rose-100' },
    { value: 'KONDISI_KORBAN', label: 'KONDISI KORBAN', badgeColor: 'bg-amber-50 text-amber-700 border-amber-100' },
    { value: 'MEDAN_PERAIRAN', label: 'MEDAN & PERAIRAN', badgeColor: 'bg-emerald-50 text-emerald-700 border-emerald-100' },
    { value: 'SLANG_DIALEK', label: 'SLANG, DIALEK & TYPO', badgeColor: 'bg-purple-50 text-purple-700 border-purple-100' },
  ];

  const [searchQuery, setSearchQuery] = useState('');
  const [filterCategory, setFilterCategory] = useState('ALL');
  const [filterType, setFilterType] = useState('ALL'); // ALL, ABBREVIATION, JARGON, GENERAL
  const [filterStatus, setFilterStatus] = useState('ALL'); // ALL, APPROVED, PENDING, REJECTED
  const [isVectorizing, setIsVectorizing] = useState(false);
  
  // Modal & Form States
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<'create' | 'edit'>('create');
  const [selectedWord, setSelectedWord] = useState<any>(null);
  const [formError, setFormError] = useState('');
  
  const [formData, setFormData] = useState({
    word: '',
    definition: '',
    context_example: '',
    category: 'OPERASIONAL_SAR',
    canonical_name: '',
    semantic_description: '',
    word_type: 'GENERAL',
    ner_type: '',
    ner_target: '',
    status: 'APPROVED',
    synonym_target: '',
    is_typo_or_slang: false,
    is_global: false
  });

  // Fetch Dictionary Words
  const { data: words = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['knowledge'],
    queryFn: getKnowledgeBase,
  });

  // Uji Coba Istilah Lokal & Ekstraksi Kalimat Darurat
  const [isSandboxOpen, setIsSandboxOpen] = useState(false);
  const [testSentence, setTestSentence] = useState('Ada pompong nelayan patah kemudi di laut Natuna membawa 3 orang');

  const sandboxAnalysis = useMemo(() => {
    if (!testSentence.trim() || !words.length) {
      return { matches: [], totalMatched: 0 };
    }

    const textLower = testSentence.toLowerCase();
    const matchedTerms: any[] = [];

    // Sort words by word length descending so longer phrases match first
    const sortedWords = [...words].sort((a: any, b: any) => (b.word?.length || 0) - (a.word?.length || 0));

    sortedWords.forEach((item: any) => {
      if (!item.word || item.word.trim().length < 2) return;
      const term = item.word.toLowerCase();
      try {
        const regex = new RegExp(`\\b${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i');
        if (regex.test(textLower)) {
          // Avoid duplicate entries
          if (!matchedTerms.some((m) => m.word.toLowerCase() === term)) {
            matchedTerms.push({
              word: item.word,
              canonical_name: item.canonical_name || item.synonym_target || item.word,
              category: item.category,
              ner_type: item.ner_type,
              is_typo_or_slang: item.is_typo_or_slang,
              definition: item.definition
            });
          }
        }
      } catch (e) {
        // Safe regex fallback
      }
    });

    return {
      matches: matchedTerms,
      totalMatched: matchedTerms.length
    };
  }, [testSentence, words]);

  const handleVectorizeAll = async (force: boolean = false) => {
    try {
      setIsVectorizing(true);
      const res = await vectorizeAllDictionary(force);
      queryClient.invalidateQueries({ queryKey: ['knowledge'] });
      alert(`Sinkronisasi Vektor AI Selesai!\nDiproses: ${res.total_queued}\nBerhasil: ${res.success_count}\nGagal: ${res.failed_count}`);
    } catch (err: any) {
      console.error("Gagal sinkronisasi vektor AI:", err);
      alert(err.response?.data?.detail || "Gagal sinkronisasi vektor AI.");
    } finally {
      setIsVectorizing(false);
    }
  };

  // Mutations for Dictionary
  const createMutation = useMutation({
    mutationFn: createDictionaryWord,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge'] });
      setIsModalOpen(false);
      resetForm();
    },
    onError: (error: any) => {
      const errMsg = error.response?.data?.detail || 'Gagal menambahkan kosakata baru.';
      setFormError(errMsg);
    }
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data, isGlobal }: { id: number; data: any; isGlobal: boolean }) => updateDictionaryWord(id, data, isGlobal),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge'] });
      setIsModalOpen(false);
      setSelectedWord(null);
      resetForm();
    },
    onError: (error: any) => {
      const errMsg = error.response?.data?.detail || 'Gagal memperbarui definisi kosakata.';
      setFormError(errMsg);
    }
  });

  const deleteMutation = useMutation({
    mutationFn: deleteDictionaryWord,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge'] });
    }
  });

  const resetForm = () => {
    setFormData({
      word: '',
      definition: '',
      context_example: '',
      category: 'OPERASIONAL_SAR',
      canonical_name: '',
      semantic_description: '',
      word_type: 'GENERAL',
      ner_type: '',
      ner_target: '',
      status: 'APPROVED',
      synonym_target: '',
      is_typo_or_slang: false,
      is_global: false
    });
    setFormError('');
  };

  const handleOpenCreate = () => {
    resetForm();
    setModalMode('create');
    setIsModalOpen(true);
  };

  const handleOpenEdit = (item: any) => {
    setSelectedWord(item);
    setFormData({
      word: item.word || '',
      definition: item.definition || '',
      context_example: item.context_example || '',
      category: item.category || 'OPERASIONAL_SAR',
      canonical_name: item.canonical_name || '',
      semantic_description: item.semantic_description || '',
      word_type: item.word_type || 'GENERAL',
      ner_type: item.ner_type || '',
      ner_target: item.ner_target || '',
      status: item.status || 'APPROVED',
      synonym_target: item.synonym_target || '',
      is_typo_or_slang: item.is_typo_or_slang || false,
      is_global: item.is_global || false
    });
    setFormError('');
    setModalMode('edit');
    setIsModalOpen(true);
  };

  const handleDelete = (id: number, word: string, isGlobal: boolean) => {
    if (window.confirm(`Apakah Anda yakin ingin menghapus kosakata "${word}" dari Kamus Istilah?`)) {
      deleteMutation.mutate({ id, isGlobal });
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');
    if (modalMode === 'create') {
      createMutation.mutate(formData);
    } else if (modalMode === 'edit' && selectedWord) {
      updateMutation.mutate({ id: selectedWord.id, data: formData, isGlobal: selectedWord.is_global });
    }
  };

  // Filter & Search Logic (Dictionary)
  const filteredWords = words.filter((item: any) => {
    const wordStr = (item.word || '').toLowerCase();
    const defStr = (item.definition || '').toLowerCase();
    const canonStr = (item.canonical_name || '').toLowerCase();
    const categoryStr = item.category || 'OPERASIONAL_SAR';
    const typeStr = item.word_type || 'GENERAL';
    const statusStr = item.status || 'PENDING';
    const searchLower = searchQuery.toLowerCase();
    
    const matchesSearch = wordStr.includes(searchLower) || defStr.includes(searchLower) || canonStr.includes(searchLower);
    const matchesCategory = filterCategory === 'ALL' ? true : categoryStr === filterCategory;
    const matchesType = filterType === 'ALL' ? true : typeStr === filterType;
    const matchesStatus = filterStatus === 'ALL' ? true : statusStr === filterStatus;
    
    return matchesSearch && matchesCategory && matchesType && matchesStatus;
  });

  return (
    <div className="space-y-6 w-full pb-10">
      {/* HEADER */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight flex items-center gap-2">
            <Database className="w-8 h-8 text-slate-800 shrink-0" />
            Kamus Istilah Bot
          </h1>
          <p className="text-gray-500 mt-1">
            Kamus acuan kosakata lokal, singkatan mitigasi, dan istilah teknis operasi SAR untuk penyelarasan chatbot.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 mt-4 md:mt-0">
          <button
            onClick={() => handleVectorizeAll(false)}
            disabled={isVectorizing}
            className="px-3.5 py-2.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-semibold text-xs rounded-xl border border-indigo-200 transition-all flex items-center gap-1.5 shadow-sm active:scale-95 disabled:opacity-55 cursor-pointer"
            title="Generate embedding vektor AI untuk pencarian semantik kamus istilah"
          >
            {isVectorizing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 text-indigo-600" />}
            Sinkron Vektor AI
          </button>
          <button
            onClick={handleExport}
            disabled={isExporting}
            className="px-3.5 py-2.5 bg-white hover:bg-gray-50 text-gray-700 font-semibold text-xs rounded-xl border border-gray-200 transition-all flex items-center gap-1.5 shadow-sm active:scale-95 disabled:opacity-55 cursor-pointer"
          >
            {isExporting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
            Ekspor
          </button>
          <button
            onClick={() => {
              setImportFile(null);
              setImportResult(null);
              setImportError('');
              setImportIsGlobal(tenantSlug === 'pusat' || tenantSlug === 'global');
              setIsImportModalOpen(true);
            }}
            className="px-3.5 py-2.5 bg-white hover:bg-gray-50 text-gray-700 font-semibold text-xs rounded-xl border border-gray-200 transition-all flex items-center gap-1.5 shadow-sm active:scale-95 cursor-pointer"
          >
            <Upload className="w-3.5 h-3.5" />
            Impor Kolektif
          </button>
          <button
            onClick={() => setIsSandboxOpen(!isSandboxOpen)}
            className={`px-3.5 py-2.5 font-semibold text-xs rounded-xl border transition-all flex items-center gap-1.5 shadow-sm active:scale-95 cursor-pointer ${
              isSandboxOpen 
                ? 'bg-amber-100 text-amber-900 border-amber-300' 
                : 'bg-white hover:bg-gray-50 text-gray-700 border-gray-200'
            }`}
            title="Buka pengujian ekstraksi istilah lokal dan normalisasi kosakata"
          >
            <Cpu className={`w-3.5 h-3.5 ${isSandboxOpen ? 'text-amber-700' : 'text-slate-600'}`} />
            <span>{isSandboxOpen ? 'Tutup Uji Coba' : 'Uji Coba Istilah'}</span>
          </button>
          <button 
            onClick={handleOpenCreate}
            className="px-4 py-2.5 bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs rounded-xl transition-all shadow-sm flex items-center gap-1.5 active:scale-95 cursor-pointer"
          >
            <Plus className="w-5 h-5" /> Tambah Kosakata
          </button>
        </div>
      </div>

      {/* UJI COBA PENCOCOKAN ISTILAH & NORMALISASI KOSAKATA */}
      {isSandboxOpen && (
        <div className="bg-slate-900 text-slate-100 rounded-3xl p-6 shadow-lg border border-slate-800 space-y-5 animate-in fade-in duration-200">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="p-2 bg-amber-500/20 text-amber-400 rounded-xl border border-amber-500/30">
                <Cpu className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-extrabold text-sm text-white flex items-center gap-2">
                  Uji Coba Pencocokan Istilah & Normalisasi Kosakata
                  <span className="text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/30 px-2 py-0.5 rounded-full font-mono">
                    Deteksi Real-Time
                  </span>
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Uji coba kalimat darurat untuk melihat bagaimana kamus istilah lokal Anda dinormalisasi dan dikenali oleh sistem.
                </p>
              </div>
            </div>
            <button
              onClick={() => setIsSandboxOpen(false)}
              className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-xl transition-all cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
            {/* Input Kalimat Pengujian */}
            <div className="lg:col-span-7 space-y-3">
              <label className="block text-xs font-bold text-slate-300">
                Ketik Kalimat Laporan Masuk untuk Diuji:
              </label>
              <textarea
                rows={3}
                value={testSentence}
                onChange={(e) => setTestSentence(e.target.value)}
                placeholder="Contoh: Ada pompong nelayan patah kemudi di perairan Natuna membawa 3 orang..."
                className="w-full px-4 py-3 bg-slate-950 border border-slate-800 rounded-2xl text-xs text-slate-100 focus:ring-2 focus:ring-amber-500/30 focus:border-amber-500 outline-none resize-none leading-relaxed font-sans"
              />

              {/* Contoh Kalimat Uji (Presets) */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[11px] font-bold text-slate-400">Contoh Laporan:</span>
                {[
                  { label: 'Laka Laut Pompong', text: 'Ada pompong nelayan patah kemudi di laut Natuna membawa 3 orang' },
                  { label: 'Kapal Tenggelam', text: 'Jongkong tenggelam dihantam ombak di selat sunda, 1 orang hilang' },
                  { label: 'Kapal Kandas', text: 'Kapal lct kandas di karang dekat pulau subi' }
                ].map((preset, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setTestSentence(preset.text)}
                    className="text-[10px] px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700/80 transition-all cursor-pointer font-medium"
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Hasil Analisa & Ekstraksi */}
            <div className="lg:col-span-5 bg-slate-950 p-4 rounded-2xl border border-slate-800 space-y-3.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                  Hasil Pengenalan Istilah
                </span>
                <span className="text-[11px] px-2 py-0.5 rounded-full font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  {sandboxAnalysis.totalMatched} Terdeteksi
                </span>
              </div>

              {sandboxAnalysis.matches.length > 0 ? (
                <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                  {sandboxAnalysis.matches.map((m: any, idx: number) => (
                    <div key={idx} className="p-2.5 bg-slate-900 rounded-xl border border-slate-800 flex items-center justify-between text-xs">
                      <div>
                        <span className="font-bold text-amber-300 font-mono">{m.word}</span>
                        {m.canonical_name && m.canonical_name !== m.word && (
                          <span className="text-slate-400 text-[11px] ml-1.5">
                            → <strong className="text-emerald-400">{m.canonical_name}</strong>
                          </span>
                        )}
                        <p className="text-[10px] text-slate-500 mt-0.5 line-clamp-1">{m.definition || 'Kosakata Kamus SAR'}</p>
                      </div>
                      <span className="text-[9px] uppercase tracking-wider px-2 py-0.5 bg-slate-800 text-slate-300 rounded-md border border-slate-700 font-semibold shrink-0">
                        {m.category || 'ISTILAH'}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-6 text-xs text-slate-500">
                  Belum ada kata dalam kalimat yang cocok dengan kamus aktif. Coba tambahkan kosakata baru atau gunakan preset di samping.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* FILTER & SEARCH PANEL */}
      <div className="bg-white rounded-3xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="p-5 border-b border-gray-100 flex flex-col md:flex-row md:items-center gap-4 justify-between bg-gray-50/35">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4.5 h-4.5 text-gray-400" />
            <input 
              type="text" 
              placeholder="Cari kata, bentuk baku, atau arti definisi..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 bg-white border border-gray-200 rounded-xl text-xs font-semibold focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none text-gray-700"
            />
          </div>
          <div className="flex items-center gap-2 overflow-x-auto pb-1 md:pb-0 flex-wrap">
            {/* Filter Kategori SAR */}
            <select
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
              className="px-3 py-2.5 bg-white border border-gray-200 text-gray-700 text-xs font-bold rounded-xl outline-none"
            >
              {SAR_CATEGORIES.map((cat) => (
                <option key={cat.value} value={cat.value}>
                  {cat.label}
                </option>
              ))}
            </select>

            {/* Filter Tipe */}
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="px-3 py-2.5 bg-white border border-gray-200 text-gray-700 text-xs font-bold rounded-xl outline-none"
            >
              <option value="ALL">SEMUA TIPE KATA</option>
              <option value="GENERAL">UMUM / GENERAL</option>
              <option value="ABBREVIATION">SINGKATAN / AKRONIM</option>
              <option value="JARGON">JARGON TEKNIS</option>
            </select>

            {/* Filter Status */}
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="px-3 py-2.5 bg-white border border-gray-200 text-gray-700 text-xs font-bold rounded-xl outline-none"
            >
              <option value="ALL">SEMUA STATUS</option>
              <option value="APPROVED">APPROVED (AKTIF)</option>
              <option value="PENDING">PENDING</option>
              <option value="REJECTED">REJECTED</option>
            </select>
          </div>
        </div>

        {/* DICTIONARY TABLE */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-50/20">
                <th className="py-4 px-6 text-xs font-bold text-gray-500 uppercase tracking-wider border-b border-gray-100">Kosakata & Baku</th>
                <th className="py-4 px-6 text-xs font-bold text-gray-500 uppercase tracking-wider border-b border-gray-100">Kategori SAR</th>
                <th className="py-4 px-6 text-xs font-bold text-gray-500 uppercase tracking-wider border-b border-gray-100">Definisi & Semantik</th>
                <th className="py-4 px-6 text-xs font-bold text-gray-500 uppercase tracking-wider border-b border-gray-100">Vektor AI</th>
                <th className="py-4 px-6 text-xs font-bold text-gray-500 uppercase tracking-wider border-b border-gray-100">Status</th>
                <th className="py-4 px-6 text-xs font-bold text-gray-500 uppercase tracking-wider border-b border-gray-100 text-right">Aksi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {isLoading ? (
                Array(5).fill(0).map((_, i) => (
                  <tr key={i}>
                    <td colSpan={6} className="py-5 px-6">
                      <SkeletonLoader className="w-full h-10" />
                    </td>
                  </tr>
                ))
              ) : isError ? (
                <tr>
                  <td colSpan={6} className="py-12">
                    <ErrorState message="Gagal memuat data kosakata kamus." onRetry={refetch} />
                  </td>
                </tr>
              ) : filteredWords.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12">
                    <EmptyState message="Tidak ada kosakata kamus yang ditemukan." />
                  </td>
                </tr>
              ) : (
                filteredWords.map((item: any) => {
                  const catObj = SAR_CATEGORIES.find(c => c.value === (item.category || 'OPERASIONAL_SAR')) || SAR_CATEGORIES[1];
                  return (
                    <tr key={item.id} className="hover:bg-gray-50/30 transition-colors">
                      <td className="py-4 px-6 font-bold text-gray-900 text-sm">
                        <div className="flex flex-col">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span>{item.word}</span>
                            {item.is_global ? (
                              <span className="inline-flex px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded text-[9px] font-bold border border-blue-100 uppercase tracking-wider scale-90">
                                Pusat
                              </span>
                            ) : (
                              <span className="inline-flex px-1.5 py-0.5 bg-emerald-50 text-emerald-600 rounded text-[9px] font-bold border border-emerald-100 uppercase tracking-wider scale-90">
                                Lokal
                              </span>
                            )}
                            {item.is_typo_or_slang && (
                              <span className="inline-flex px-1.5 py-0.5 bg-rose-50 text-rose-600 rounded text-[9px] font-bold border border-rose-100 uppercase tracking-wider scale-90">
                                Typo/Slang
                              </span>
                            )}
                          </div>
                          {item.canonical_name && (
                            <span className="text-[11px] text-blue-600 font-bold mt-0.5 flex items-center gap-1">
                              Baku: {item.canonical_name}
                            </span>
                          )}
                          {item.synonym_target && (
                            <span className="text-[11px] text-slate-800 font-bold mt-0.5 flex items-center gap-1">
                              <ArrowRight className="w-3 h-3 text-slate-400 inline shrink-0" />
                              <span>{item.synonym_target}</span>
                              {item.similarity_score !== null && item.similarity_score !== undefined && (
                                <span className="text-[9px] text-gray-400 font-normal">
                                  ({Math.round(item.similarity_score * 100)}% match)
                                </span>
                              )}
                            </span>
                          )}
                          <span className="text-[10px] text-gray-400 font-semibold tracking-wider uppercase mt-0.5">
                            {item.word_type || 'GENERAL'} • Freq: {item.frequency || 1}
                          </span>
                        </div>
                      </td>
                      <td className="py-4 px-6 text-sm">
                        <span className={`inline-flex px-2.5 py-1 rounded-lg text-xs font-bold border shadow-xs ${catObj.badgeColor}`}>
                          {catObj.label}
                        </span>
                      </td>
                      <td className="py-4 px-6 text-gray-600 text-sm leading-relaxed max-w-sm">
                        {item.definition}
                        {item.semantic_description && (
                          <span className="block text-[11px] text-indigo-600 mt-1 font-medium bg-indigo-50/50 p-1.5 rounded-md border border-indigo-100/50">
                            Semantik AI: {item.semantic_description}
                          </span>
                        )}
                        {item.context_example && (
                          <span className="block text-[11px] text-gray-400 mt-1 italic font-medium">
                            Contoh: "{item.context_example}"
                          </span>
                        )}
                      </td>
                      <td className="py-4 px-6 text-sm">
                        {item.has_vector ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-emerald-50 text-emerald-700 rounded-lg text-xs font-bold border border-emerald-100 shadow-xs">
                            <Sparkles className="w-3.5 h-3.5 text-emerald-600" /> Vektor Aktif
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-gray-50 text-gray-500 rounded-lg text-xs font-medium border border-gray-200 shadow-xs">
                            <Cpu className="w-3.5 h-3.5 text-gray-400" /> Belum Vektor
                          </span>
                        )}
                      </td>
                      <td className="py-4 px-6">
                        {item.status === 'APPROVED' ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-green-50 text-green-700 rounded-lg text-xs font-bold border border-green-100 shadow-sm">
                            <CheckCircle className="w-3.5 h-3.5 text-green-500" /> Approved
                          </span>
                        ) : item.status === 'PENDING' ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-slate-100 text-slate-800 rounded-lg text-xs font-bold border border-slate-200 shadow-sm">
                            <HelpCircle className="w-3.5 h-3.5 text-slate-500" /> Pending
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-red-50 text-red-700 rounded-lg text-xs font-bold border border-red-100 shadow-sm">
                            <AlertCircle className="w-3.5 h-3.5 text-red-500" /> Rejected
                          </span>
                        )}
                      </td>
                    <td className="py-4 px-6">
                      <div className="flex items-center justify-end gap-1.5">
                        {item.is_global && tenantSlug !== 'pusat' && tenantSlug !== 'global' ? (
                          <span className="text-gray-450 flex items-center gap-1 text-xs font-semibold px-2 py-1 bg-gray-50 border border-gray-100 rounded-lg" title="Kosakata pusat bersifat Read-Only">
                            <Lock className="w-3.5 h-3.5 text-gray-400" /> Terkunci (Pusat)
                          </span>
                        ) : (
                          <>
                            <button 
                              onClick={() => handleOpenEdit(item)}
                              className="p-2 text-gray-400 hover:text-amber-600 hover:bg-amber-50 rounded-xl transition-all border border-transparent hover:border-amber-100"
                              title="Sunting Kosakata"
                            >
                              <Pencil className="w-4 h-4" />
                            </button>
                            <button 
                              onClick={() => handleDelete(item.id, item.word, item.is_global)}
                              className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-xl transition-all border border-transparent hover:border-red-100"
                              title="Hapus Kosakata"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* POPUP MODAL: CRUD FORM FOR DICTIONARY */}
      <AnimatePresence>
        {isModalOpen && (
          <>
            {/* Backdrop */}
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.5 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsModalOpen(false)}
              className="fixed inset-0 bg-black z-45"
            />
            
            {/* Modal Dialog */}
            <motion.div 
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="fixed inset-0 m-auto w-[550px] h-fit max-h-[85vh] bg-white rounded-3xl shadow-2xl border border-gray-100 z-50 overflow-hidden flex flex-col"
            >
              {/* Modal Header */}
              <div className="p-5 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-10 h-10 rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-800">
                    <Book className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-gray-800 text-base">
                      {modalMode === 'create' ? 'Tambah Entri Kosakata Baru' : `Sunting Kosakata: ${selectedWord?.word}`}
                    </h3>
                    <p className="text-[11px] text-gray-500 mt-0.5">
                      Tambahkan definisi acuan untuk meningkatkan keakuratan ekstraksi AI RAG
                    </p>
                  </div>
                </div>
                <button 
                  onClick={() => setIsModalOpen(false)}
                  className="p-1.5 text-gray-400 hover:text-gray-800 hover:bg-gray-100 rounded-xl transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Modal Body */}
              <div className="flex-1 overflow-y-auto p-6 space-y-4 text-gray-700">
                {formError && (
                  <div className="p-3 bg-red-50 text-red-700 border border-red-100 rounded-xl text-xs font-semibold flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{formError}</span>
                  </div>
                )}
                
                <form id="dictionaryForm" onSubmit={handleSubmit} className="space-y-4 text-xs">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="block font-bold text-gray-700">Kosakata / Akronim</label>
                      <input
                        type="text"
                        required
                        disabled={modalMode === 'edit'}
                        value={formData.word}
                        onChange={(e) => setFormData({ ...formData, word: e.target.value })}
                        placeholder="Contoh: pompong"
                        className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 focus:bg-white outline-none text-gray-800 disabled:bg-gray-150 disabled:text-gray-400 disabled:cursor-not-allowed font-semibold"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="block font-bold text-gray-700">Bentuk Baku / Istilah Resmi</label>
                      <input
                        type="text"
                        value={formData.canonical_name}
                        onChange={(e) => setFormData({ ...formData, canonical_name: e.target.value })}
                        placeholder="Contoh: Perahu Kayu Bermesin"
                        className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 focus:bg-white outline-none text-gray-800 font-semibold"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="block font-bold text-gray-700">Kategori Standar SAR</label>
                      <select
                        value={formData.category}
                        onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                        className="w-full px-2.5 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 focus:bg-white outline-none text-gray-800 font-medium"
                      >
                        {SAR_CATEGORIES.filter(c => c.value !== 'ALL').map((c) => (
                          <option key={c.value} value={c.value}>{c.label}</option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-1.5">
                      <label className="block font-bold text-gray-700">Karakter Istilah (Tipe)</label>
                      <select
                        value={formData.word_type}
                        onChange={(e) => setFormData({ ...formData, word_type: e.target.value })}
                        className="w-full px-2.5 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 focus:bg-white outline-none text-gray-800 font-medium"
                      >
                        <option value="GENERAL">GENERAL / UMUM</option>
                        <option value="ABBREVIATION">SINGKATAN / AKRONIM</option>
                        <option value="JARGON">JARGON TEKNIS</option>
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4 p-3 bg-gray-50/50 border border-gray-100 rounded-2xl">
                    <div className="space-y-1.5">
                      <label className="block font-bold text-gray-700 flex items-center gap-1.5 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={formData.is_typo_or_slang}
                          onChange={(e) => setFormData({ ...formData, is_typo_or_slang: e.target.checked, word_type: e.target.checked ? 'TYPO' : formData.word_type })}
                          className="w-3.5 h-3.5 text-slate-800 border-gray-300 rounded focus:ring-slate-900/10"
                        />
                        Salah Ketik / Slang Pelapor
                      </label>
                      <span className="text-[10px] text-gray-400 block leading-tight font-medium">
                        Aktifkan untuk kata/typo yang perlu di-autocorrect otomatis oleh sistem.
                      </span>
                    </div>
                    
                    <div className="space-y-1.5">
                      <label className="block font-bold text-gray-700">Pemetaan Sinonim / Kata Standar</label>
                      <input
                        type="text"
                        value={formData.synonym_target}
                        onChange={(e) => setFormData({ ...formData, synonym_target: e.target.value })}
                        placeholder="Contoh: pompong"
                        disabled={!formData.is_typo_or_slang}
                        className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 focus:bg-white outline-none text-gray-800 disabled:bg-gray-100 disabled:cursor-not-allowed font-semibold"
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="block font-bold text-gray-700">Arti / Definisi Singkat</label>
                    <textarea
                      required
                      rows={3}
                      value={formData.definition}
                      onChange={(e) => setFormData({ ...formData, definition: e.target.value })}
                      placeholder="Masukkan penjelasan arti atau definisi kosakata dalam konteks SAR..."
                      className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 focus:bg-white outline-none text-gray-800 leading-normal resize-none"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="block font-bold text-gray-700">Contoh Konteks Penggunaan (Opsional)</label>
                    <input
                      type="text"
                      value={formData.context_example}
                      onChange={(e) => setFormData({ ...formData, context_example: e.target.value })}
                      placeholder="Contoh: Nelayan pergi memancing menggunakan kapal pompong"
                      className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 focus:bg-white outline-none text-gray-800"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="block font-bold text-gray-700 flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
                      Konteks Semantik untuk AI (Opsional)
                    </label>
                    <input
                      type="text"
                      value={formData.semantic_description}
                      onChange={(e) => setFormData({ ...formData, semantic_description: e.target.value })}
                      placeholder="Contoh: Digunakan di pesisir Sumatra & Riau untuk perahu kayu bermesin dompeng"
                      className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:ring-1 focus:ring-indigo-500 focus:bg-white outline-none text-gray-800"
                    />
                    <span className="text-[10px] text-gray-400 block leading-tight font-medium">
                      Memberikan petunjuk tambahan bagi model embedding AI ketika mencari kedekatan makna.
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-4">
                    <div className="space-y-1.5">
                      <label className="block font-bold text-gray-700">Tipe NER (Opsional)</label>
                      <select
                        value={formData.ner_type || ''}
                        onChange={(e) => setFormData({ ...formData, ner_type: e.target.value })}
                        className="w-full px-2.5 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 focus:bg-white outline-none text-gray-800 font-medium"
                      >
                        <option value="">Bukan NER (Umum)</option>
                        <option value="Nama Tempat">Nama Tempat / Lokasi</option>
                        <option value="Nama Kejadian">Nama Kejadian / Klasifikasi</option>
                        <option value="Waktu">Penanda Waktu</option>
                        <option value="Jenis Kapal">Jenis Kapal / Sarana</option>
                        <option value="Status Korban">Status / Kondisi Korban</option>
                      </select>
                    </div>
                    <div className="space-y-1.5">
                      <label className="block font-bold text-gray-700">Target NER (Opsional)</label>
                      <select
                        value={formData.ner_target || ''}
                        onChange={(e) => setFormData({ ...formData, ner_target: e.target.value })}
                        className="w-full px-2.5 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 focus:bg-white outline-none text-gray-800 font-medium"
                      >
                        <option value="">Tidak Ada Target</option>
                        {/* Target Klasifikasi Resmi */}
                        <option value="Laka Kapal">Laka Kapal (Kecelakaan Laut)</option>
                        <option value="Laka Pesawat">Laka Pesawat (Kecelakaan Udara)</option>
                        <option value="KPK">KPK (Penanganan Khusus)</option>
                        <option value="Bencana">Bencana (Bencana Alam)</option>
                        <option value="KMM">KMM (Membahayakan Manusia)</option>
                        {/* Target Ekstraksi Field */}
                        <option value="Data Lokasi">Data Lokasi / Koordinat</option>
                        <option value="Data Kapal">Data Kapal (Vessel)</option>
                        <option value="Waktu">Waktu Kejadian</option>
                        <option value="Lokasi">Lokasi Kejadian</option>
                      </select>
                    </div>
                    <div className="space-y-1.5">
                      <label className="block font-bold text-gray-700">Status Entri</label>
                      <select
                        value={formData.status}
                        onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                        className="w-full px-2.5 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 focus:bg-white outline-none text-gray-800 font-medium"
                      >
                        <option value="APPROVED">APPROVED (AKTIF)</option>
                        <option value="PENDING">PENDING</option>
                        <option value="REJECTED">REJECTED</option>
                      </select>
                    </div>
                  </div>

                  {(tenantSlug === 'pusat' || tenantSlug === 'global') && modalMode === 'create' && (
                    <div className="p-3 bg-blue-50/50 border border-blue-100 rounded-2xl mt-4">
                      <label className="block font-bold text-gray-700 flex items-center gap-1.5 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={formData.is_global}
                          onChange={(e) => setFormData({ ...formData, is_global: e.target.checked })}
                          className="w-3.5 h-3.5 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                        />
                        Jadikan Kamus Dasar (Global)
                      </label>
                      <span className="text-[10px] text-gray-400 block leading-tight font-medium mt-1">
                        Jika dicentang, kata ini akan ditambahkan ke kamus dasar nasional yang dapat dibaca oleh seluruh UPT.
                      </span>
                    </div>
                  )}
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
                  form="dictionaryForm"
                  disabled={createMutation.isPending || updateMutation.isPending}
                  className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs rounded-xl shadow transition-all flex items-center gap-1.5 disabled:bg-gray-250 disabled:cursor-not-allowed active:scale-95"
                >
                  {(createMutation.isPending || updateMutation.isPending) ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" /> Menyimpan...
                    </>
                  ) : (
                    modalMode === 'create' ? 'Tambah Kosakata' : 'Simpan Perubahan'
                  )}
                </button>
              </div>
            </motion.div>
          </>
        )}

        {/* POPUP MODAL: IMPORT DICTIONARY */}
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
              className="fixed inset-0 m-auto w-[540px] h-fit max-h-[85vh] bg-white rounded-3xl shadow-2xl border border-gray-100 z-50 overflow-hidden flex flex-col"
            >
              {/* Modal Header */}
              <div className="p-5 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-10 h-10 rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-800">
                    <Upload className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-gray-800 text-base">Impor Kamus Kolektif</h3>
                    <p className="text-[11px] text-gray-500 mt-0.5">Unggah spreadsheet (.csv) untuk memperbarui database kosakata chatbot.</p>
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
                    <li><strong>Kata</strong>: Kosakata/akronim baru (<strong>wajib & unik</strong>).</li>
                    <li><strong>Definisi</strong>: Arti kata atau penjelasan (opsional).</li>
                    <li><strong>Contoh Kalimat</strong>: Contoh kalimat penggunaan kata (opsional).</li>
                    <li><strong>Tipe Kata</strong>: <code>GENERAL</code>, <code>ABBREVIATION</code>, atau <code>JARGON</code> (opsional).</li>
                    <li><strong>Sinonim Target</strong>: Pemetaan kata standar (opsional).</li>
                    <li><strong>Apakah Typo/Slang</strong>: Diisi <code>YA</code> atau <code>TIDAK</code> (opsional).</li>
                    <li><strong>Tipe NER</strong>: <code>INCIDENT_KEYWORD</code>, <code>LOCATION</code>, <code>TIME_MARKER</code>, atau <code>VICTIM_STATUS</code> (opsional).</li>
                    <li><strong>Target NER</strong>: Nilai pemetaan NER, e.g. KMM/LAKA KAPAL (opsional).</li>
                    <li><strong>Status</strong>: <code>APPROVED</code> atau <code>PENDING</code> (opsional).</li>
                  </ul>
                  <button
                    type="button"
                    onClick={handleTemplateDownload}
                    className="mt-2 text-xs font-bold text-slate-800 hover:text-slate-800 flex items-center gap-1 hover:underline cursor-pointer"
                  >
                    <Download className="w-3.5 h-3.5" /> Unduh Template CSV Contoh
                  </button>
                </div>

                <form id="importForm" onSubmit={handleImportSubmit} className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="block text-xs font-bold text-gray-700">Pilih File CSV</label>
                    <div className="border-2 border-dashed border-gray-200 hover:border-slate-900/50 rounded-2xl p-6 transition-all flex flex-col items-center justify-center gap-2 bg-gray-50/50 hover:bg-white relative">
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

                  {(tenantSlug === 'pusat' || tenantSlug === 'global') && !importResult && (
                    <div className="p-3 bg-blue-50/50 border border-blue-100 rounded-2xl">
                      <label className="block text-xs font-bold text-gray-700 flex items-center gap-1.5 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={importIsGlobal}
                          onChange={(e) => setImportIsGlobal(e.target.checked)}
                          className="w-3.5 h-3.5 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                        />
                        Impor ke Kamus Dasar (Global)
                      </label>
                      <span className="text-[9px] text-gray-400 block leading-tight font-medium mt-1">
                        Jika dicentang, kata-kata yang diimpor akan disimpan di Kamus Dasar Nasional yang berlaku di seluruh UPT.
                      </span>
                    </div>
                  )}
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
                      <CheckCircle className="w-4.5 h-4.5 text-emerald-600" /> Impor Berhasil Diproses
                    </div>
                    <div className="grid grid-cols-2 gap-2 mt-1">
                      <div className="bg-white/80 p-2.5 rounded-xl border border-emerald-100/50">
                        <div className="text-gray-500 text-[10px] uppercase font-bold">Kata Baru</div>
                        <div className="text-lg font-extrabold text-emerald-700 mt-0.5">{importResult.created} kata</div>
                      </div>
                      <div className="bg-white/80 p-2.5 rounded-xl border border-emerald-100/50">
                        <div className="text-gray-500 text-[10px] uppercase font-bold">Kata Diperbarui</div>
                        <div className="text-lg font-extrabold text-amber-700 mt-0.5">{importResult.updated} kata</div>
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
                    className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs rounded-xl shadow transition-all flex items-center gap-1.5 disabled:bg-gray-200 disabled:cursor-not-allowed cursor-pointer"
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
