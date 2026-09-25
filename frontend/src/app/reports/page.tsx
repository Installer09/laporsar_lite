'use client';

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  getReports, 
  createReport, 
  updateReport, 
  deleteReport,
  generateInfoAwal,
  sendBroadcast
} from '@/lib/api';
import { 
  Search, 
  AlertTriangle, 
  Eye, 
  Clock, 
  Pencil, 
  Trash2, 
  Loader2, 
  X, 
  Plus, 
  Calendar, 
  MapPin, 
  User, 
  Phone, 
  FileText, 
  Activity, 
  Users2,
  Info,
  Send,
  ShieldAlert
} from 'lucide-react';
import { SkeletonLoader } from '@/components/ui/SkeletonLoader';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { motion, AnimatePresence } from 'framer-motion';
import { useLaporSar } from '@/providers/LaporSarProvider';

const playSirenSound = () => {
  if (typeof window === 'undefined') return;
  try {
    const AudioContext = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    
    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(440, ctx.currentTime);
    osc.frequency.linearRampToValueAtTime(880, ctx.currentTime + 0.3);
    osc.frequency.linearRampToValueAtTime(440, ctx.currentTime + 0.6);
    osc.frequency.linearRampToValueAtTime(880, ctx.currentTime + 0.9);
    osc.frequency.linearRampToValueAtTime(440, ctx.currentTime + 1.2);
    
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 1.5);
    
    osc.connect(gain);
    gain.connect(ctx.destination);
    
    osc.start();
    osc.stop(ctx.currentTime + 1.5);
  } catch (e) {
    console.error("Audio context failed:", e);
  }
};

function ReportsPageContent() {
  const queryClient = useQueryClient();
  const { markReportAsRead } = useLaporSar();
  const [filter, setFilter] = useState('ALL');
  const [dateFilter, setDateFilter] = useState('ALL');
  const [typeFilter, setTypeFilter] = useState('ALL');
  const [newReportAlert, setNewReportAlert] = useState<{ id: number; message: string } | null>(null);

  const searchParams = useSearchParams();
  const reportIdParam = searchParams.get('id');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Modal & Edit States
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<'create' | 'edit' | 'detail'>('create');
  const [selectedReport, setSelectedReport] = useState<any>(null);

  // Broadcast Modal & States
  const [isBroadcastModalOpen, setIsBroadcastModalOpen] = useState(false);
  const [bcTab, setBcTab] = useState<'dasar' | 'korban' | 'spesifik' | 'operasional'>('dasar');
  const [previewText, setPreviewText] = useState('');
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [isBroadcasting, setIsBroadcasting] = useState(false);

  // WebSocket real-time sirens and updates
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
        const msgType = data.type || data.event;
        
        if (msgType === 'new_report') {
          playSirenSound();
          setNewReportAlert({
            id: Date.now(),
            message: 'Laporan Darurat Baru Masuk. Silakan periksa daftar laporan.'
          });
          queryClient.invalidateQueries({ queryKey: ['reports'] });
        } else if (msgType === 'report_updated' || msgType === 'report_deleted') {
          queryClient.invalidateQueries({ queryKey: ['reports'] });
        }
      } catch (err) {
        console.error('Error parsing WS message in ReportsPageContent:', err);
      }
    };

    return () => ws.close();
  }, [queryClient]);
  
  const [bcVictims, setBcVictims] = useState<any[]>([]);
  const [bcForm, setBcForm] = useState({
    waktu: '',
    lokasi_teks: '',
    koordinat_lat: '',
    koordinat_lng: '',
    korban_total: '',
    korban_selamat: '',
    korban_meninggal: '',
    korban_hilang: '',
    unsur_sar_str: '',
    alut_palsar_str: '',
    cuaca: '',
    aksi: '',
    hasil: '',
    kronologi: '',
    // Kapal
    kapal_nama: '',
    kapal_jenis: '',
    kapal_warna: '',
    kapal_imo: '',
    kapal_call_sign: '',
    kapal_telp: '',
    // Pesawat
    pesawat_nama: '',
    pesawat_jenis: '',
    pesawat_warna: '',
    pesawat_register: '',
    pesawat_rute: '',
    pesawat_operator: '',
    // Alat
    alat_jenis: '',
    alat_warna: '',
    alat_nopol: '',
    alat_pemilik: ''
  });
  
  // Form State
  const [formData, setFormData] = useState({
    pelapor_nama: '',
    pelapor_nomor: '',
    jenis_kejadian: 'Laka Kapal',
    waktu: '',
    lokasi_teks: '',
    korban: '',
    kronologi: '',
    status: 'PENDING'
  });

  // Fetch Reports
  const { data: reports = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['reports'],
    queryFn: getReports,
  });

  useEffect(() => {
    if (reportIdParam && reports && reports.length > 0) {
      const report = reports.find((r: any) => String(r.id) === reportIdParam);
      if (report) {
        markReportAsRead(String(report.id));
        setSelectedReport(report);
        setModalMode('detail');
        setIsModalOpen(true);
      }
    }
  }, [reportIdParam, reports, markReportAsRead]);

  // Mutations
  const createMutation = useMutation({
    mutationFn: createReport,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
      setIsModalOpen(false);
      resetForm();
    }
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) => updateReport(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
      setIsModalOpen(false);
      setSelectedReport(null);
      resetForm();
    }
  });

  const handleStatusChange = async (id: number, newStatus: string, noLaporan: string) => {
    const statusLabels: Record<string, string> = {
      PENDING: 'Menunggu Validasi',
      AKTIF: 'Aktif / Valid',
      TIDAK_AKTIF: 'Tidak Aktif',
      SALAH_LAPORAN: 'Salah Laporan'
    };
    const statusLabel = statusLabels[newStatus] || newStatus;
    if (window.confirm(`Apakah Anda yakin ingin mengubah status laporan ${noLaporan} menjadi "${statusLabel}"?`)) {
      try {
        await updateReport(id, { status: newStatus });
        queryClient.invalidateQueries({ queryKey: ['reports'] });
        queryClient.invalidateQueries({ queryKey: ['stats'] });
      } catch (err) {
        console.error("Gagal memperbarui status:", err);
        alert("Gagal memperbarui status laporan.");
      }
    }
  };

  const deleteMutation = useMutation({
    mutationFn: deleteReport,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    }
  });

  const resetForm = () => {
    setFormData({
      pelapor_nama: '',
      pelapor_nomor: '',
      jenis_kejadian: 'Laka Kapal',
      waktu: '',
      lokasi_teks: '',
      korban: '',
      kronologi: '',
      status: 'PENDING'
    });
  };

  // Victims List Handlers
  const handleAddVictim = () => {
    setBcVictims([...bcVictims, { nama: '', jenis_kelamin: 'Laki-laki', umur: '', alamat: '', ciri_ciri: '' }]);
  };

  const handleRemoveVictim = (index: number) => {
    setBcVictims(bcVictims.filter((_, i) => i !== index));
  };

  const handleUpdateVictim = (index: number, key: string, val: any) => {
    const updated = [...bcVictims];
    updated[index][key] = val;
    setBcVictims(updated);
  };

  // Open Broadcast Panel (Pendalaman Info Awal)
  const handleOpenBroadcast = async (report: any) => {
    setSelectedReport(report);
    
    // Parse Unsur & Alut
    let unsurStr = '';
    let alutStr = '';
    if (report.unsur_alut) {
      try {
        const ua = typeof report.unsur_alut === 'string' ? JSON.parse(report.unsur_alut) : report.unsur_alut;
        if (ua.unsur) unsurStr = ua.unsur.map((u: any) => u.nama).join('\n');
        if (ua.alut) alutStr = ua.alut.map((a: any) => a.nama).join('\n');
      } catch (e) {
        console.error("Failed to parse unsur_alut:", e);
      }
    }
    
    // Parse Data Korban
    let victims: any[] = [];
    if (report.data_korban) {
      try {
        const dk = typeof report.data_korban === 'string' ? JSON.parse(report.data_korban) : report.data_korban;
        if (Array.isArray(dk)) {
          victims = dk;
        } else if (dk && dk.daftar_korban) {
          victims = dk.daftar_korban;
        } else if (typeof dk === 'string' && dk.trim()) {
          victims = [{ nama: dk.trim(), jenis_kelamin: 'Laki-laki', umur: '', alamat: '', ciri_ciri: '' }];
        }
      } catch (e) {
        if (typeof report.data_korban === 'string' && report.data_korban.trim()) {
          victims = [{ nama: report.data_korban.trim(), jenis_kelamin: 'Laki-laki', umur: '', alamat: '', ciri_ciri: '' }];
        } else {
          console.error("Failed to parse data_korban:", e);
        }
      }
    }
    if (victims.length === 0) {
      victims = [{ nama: '', jenis_kelamin: 'Laki-laki', umur: '', alamat: '', ciri_ciri: '' }];
    }

    // Parse Metadata Kejadian
    let kapal = { nama: '', jenis: '', warna: '', imo: '', call_sign: '', telp: '' };
    let pesawat = { nama: '', jenis: '', warna: '', register: '', rute: '', operator: '' };
    let alat = { jenis: '', warna: '', nopol: '', pemilik: '' };
    let cuacaVal = '';
    let aksiVal = '';
    let hasilVal = '';

    if (report.metadata_kejadian) {
      try {
        const md = typeof report.metadata_kejadian === 'string' ? JSON.parse(report.metadata_kejadian) : report.metadata_kejadian;
        
        if (md.data_kapal) {
          if (typeof md.data_kapal === 'string') {
            const lines = md.data_kapal.split('\n');
            let nama = '', jenis = '', warna = '';
            lines.forEach((line: string) => {
              const parts = line.split(':');
              if (parts.length >= 2) {
                const k = parts[0].trim().toLowerCase();
                const v = parts.slice(1).join(':').trim();
                if (k.includes('nama')) nama = v;
                else if (k.includes('jenis') || k.includes('kapal')) jenis = v;
                else if (k.includes('warna')) warna = v;
              }
            });
            kapal = { nama, jenis, warna, imo: '', call_sign: '', telp: '' };
          } else {
            kapal = {
              nama: md.data_kapal.nama_kapal || md.data_kapal.nama || '',
              jenis: md.data_kapal.jenis_kapal || md.data_kapal.jenis || '',
              warna: md.data_kapal.warna_kapal || md.data_kapal.warna || '',
              imo: md.data_kapal.imo || '',
              call_sign: md.data_kapal.call_sign || md.data_kapal.callsign || '',
              telp: md.data_kapal.telepon_satelit || md.data_kapal.telp || ''
            };
          }
        }
        if (md.data_pesawat) {
          if (typeof md.data_pesawat === 'string') {
            const lines = md.data_pesawat.split('\n');
            let nama = '', jenis = '', warna = '', register = '', rute = '', operator = '';
            lines.forEach((line: string) => {
              const parts = line.split(':');
              if (parts.length >= 2) {
                const k = parts[0].trim().toLowerCase();
                const v = parts.slice(1).join(':').trim();
                if (k.includes('nama')) nama = v;
                else if (k.includes('jenis') || k.includes('pesawat')) jenis = v;
                else if (k.includes('warna')) warna = v;
                else if (k.includes('register') || k.includes('call')) register = v;
                else if (k.includes('rute')) rute = v;
                else if (k.includes('operator')) operator = v;
              }
            });
            pesawat = { nama, jenis, warna, register, rute, operator };
          } else {
            pesawat = {
              nama: md.data_pesawat.nama_pesawat || md.data_pesawat.nama || '',
              jenis: md.data_pesawat.jenis_pesawat || md.data_pesawat.jenis || '',
              warna: md.data_pesawat.warna_pesawat || md.data_pesawat.warna || '',
              register: md.data_pesawat.register || md.data_pesawat.call_sign || '',
              rute: md.data_pesawat.rute || '',
              operator: md.data_pesawat.operator || ''
            };
          }
        }
        if (md.data_alat) {
          if (typeof md.data_alat === 'string') {
            const lines = md.data_alat.split('\n');
            let jenis = '', warna = '', nopol = '', pemilik = '';
            lines.forEach((line: string) => {
              const parts = line.split(':');
              if (parts.length >= 2) {
                const k = parts[0].trim().toLowerCase();
                const v = parts.slice(1).join(':').trim();
                if (k.includes('jenis') || k.includes('kendaraan') || k.includes('alat')) jenis = v;
                else if (k.includes('warna')) warna = v;
                else if (k.includes('nopol') || k.includes('polisi')) nopol = v;
                else if (k.includes('pemilik')) pemilik = v;
              }
            });
            alat = { jenis, warna, nopol, pemilik };
          } else {
            alat = {
              jenis: md.data_alat.jenis_kendaraan || md.data_alat.jenis || '',
              warna: md.data_alat.warna_kendaraan || md.data_alat.warna || '',
              nopol: md.data_alat.nopol || md.data_alat.no_polisi || '',
              pemilik: md.data_alat.pemilik || ''
            };
          }
        }
        cuacaVal = md.cuaca || '';
        aksiVal = md.aksi || '';
        hasilVal = md.hasil || '';
      } catch (e) {
        console.error("Failed to parse metadata_kejadian:", e);
      }
    }

    setBcVictims(victims);
    setBcForm({
      waktu: report.waktu || '',
      lokasi_teks: report.lokasi_teks || '',
      koordinat_lat: report.koordinat_lat !== null && report.koordinat_lat !== undefined ? String(report.koordinat_lat) : '',
      koordinat_lng: report.koordinat_lng !== null && report.koordinat_lng !== undefined ? String(report.koordinat_lng) : '',
      korban_total: report.korban_total !== null && report.korban_total !== undefined ? String(report.korban_total) : '',
      korban_selamat: report.korban_selamat !== null && report.korban_selamat !== undefined ? String(report.korban_selamat) : '',
      korban_meninggal: report.korban_meninggal !== null && report.korban_meninggal !== undefined ? String(report.korban_meninggal) : '',
      korban_hilang: report.korban_hilang !== null && report.korban_hilang !== undefined ? String(report.korban_hilang) : '',
      unsur_sar_str: unsurStr,
      alut_palsar_str: alutStr,
      cuaca: cuacaVal,
      aksi: aksiVal,
      hasil: hasilVal,
      kronologi: report.kronologi || '',
      // Kapal
      kapal_nama: kapal.nama,
      kapal_jenis: kapal.jenis,
      kapal_warna: kapal.warna,
      kapal_imo: kapal.imo,
      kapal_call_sign: kapal.call_sign,
      kapal_telp: kapal.telp,
      // Pesawat
      pesawat_nama: pesawat.nama,
      pesawat_jenis: pesawat.jenis,
      pesawat_warna: pesawat.warna,
      pesawat_register: pesawat.register,
      pesawat_rute: pesawat.rute,
      pesawat_operator: pesawat.operator,
      // Alat
      alat_jenis: alat.jenis,
      alat_warna: alat.warna,
      alat_nopol: alat.nopol,
      alat_pemilik: alat.pemilik
    });

    setBcTab('dasar');
    setIsBroadcastModalOpen(true);
    
    if (report.info_awal_text) {
      setPreviewText(report.info_awal_text);
    } else {
      setPreviewText('');
      // Auto-generate preview using report's existing data as baseline
      setTimeout(() => {
        handleRefreshPreview(report.id, {
          waktu: report.waktu || '',
          lokasi_teks: report.lokasi_teks || '',
          koordinat_lat: report.koordinat_lat !== null && report.koordinat_lat !== undefined ? String(report.koordinat_lat) : '',
          koordinat_lng: report.koordinat_lng !== null && report.koordinat_lng !== undefined ? String(report.koordinat_lng) : '',
          korban_total: report.korban_total !== null && report.korban_total !== undefined ? String(report.korban_total) : '',
          korban_selamat: report.korban_selamat !== null && report.korban_selamat !== undefined ? String(report.korban_selamat) : '',
          korban_meninggal: report.korban_meninggal !== null && report.korban_meninggal !== undefined ? String(report.korban_meninggal) : '',
          korban_hilang: report.korban_hilang !== null && report.korban_hilang !== undefined ? String(report.korban_hilang) : '',
          kronologi: report.kronologi || '',
          UNSUR_SAR: unsurStr,
          ALUT_PALSAR: alutStr,
          CUACA: cuacaVal,
          AKSI: aksiVal,
          HASIL: hasilVal
        });
      }, 100);
    }
  };

  // Refresh live Markdown report preview
  const handleRefreshPreview = async (reportId: number, overrideData?: any) => {
    setIsPreviewLoading(true);
    try {
      const dataToSubmit = overrideData || {
        waktu: bcForm.waktu,
        lokasi_teks: bcForm.lokasi_teks,
        koordinat_lat: bcForm.koordinat_lat,
        koordinat_lng: bcForm.koordinat_lng,
        korban_total: bcForm.korban_total,
        korban_selamat: bcForm.korban_selamat,
        korban_meninggal: bcForm.korban_meninggal,
        korban_hilang: bcForm.korban_hilang,
        kronologi: bcForm.kronologi,
        UNSUR_SAR: bcForm.unsur_sar_str,
        ALUT_PALSAR: bcForm.alut_palsar_str,
        CUACA: bcForm.cuaca,
        AKSI: bcForm.aksi,
        HASIL: bcForm.hasil
      };

      const manualData: Record<string, string> = {
        waktu: dataToSubmit.waktu,
        lokasi_teks: dataToSubmit.lokasi_teks,
        KOORDINAT: dataToSubmit.koordinat_lat && dataToSubmit.koordinat_lng ? `${dataToSubmit.koordinat_lat}, ${dataToSubmit.koordinat_lng}` : '',
        JUMLAH_KORBAN_TOTAL: dataToSubmit.korban_total,
        KORBAN_SELAMAT: dataToSubmit.korban_selamat,
        KORBAN_MENINGGAL: dataToSubmit.korban_meninggal,
        KORBAN_HILANG: dataToSubmit.korban_hilang,
        KRONOLOGI: dataToSubmit.kronologi,
        UNSUR_SAR: dataToSubmit.UNSUR_SAR,
        ALUT_PALSAR: dataToSubmit.ALUT_PALSAR,
        CUACA: dataToSubmit.CUACA,
        AKSI: dataToSubmit.AKSI,
        HASIL: dataToSubmit.HASIL
      };

      const res = await generateInfoAwal(reportId, manualData);
      if (res.status === 'success') {
        setPreviewText(res.text);
      }
    } catch (err) {
      console.error("Gagal menjaring preview info awal:", err);
    } finally {
      setIsPreviewLoading(false);
    }
  };

  // Save detailed information to PostgreSQL and broadcast to Telegram/WhatsApp groups
  const handleSaveAndBroadcast = async () => {
    if (!selectedReport) return;
    setIsBroadcasting(true);
    
    try {
      // Unsur & Alut JSON mapping
      const unsurLines = bcForm.unsur_sar_str.split('\n').map(l => l.replace(/^\*\s*/, '').trim()).filter(Boolean);
      const alutLines = bcForm.alut_palsar_str.split('\n').map(l => l.replace(/^\*\s*/, '').trim()).filter(Boolean);
      const unsurAlutJson = {
        unsur: unsurLines.map(name => ({ nama: name })),
        alut: alutLines.map(name => ({ nama: name }))
      };

      const validVictims = bcVictims.filter(v => v.nama.trim());

      // Metadata JSON mapping
      const metadataJson: Record<string, any> = {
        cuaca: bcForm.cuaca,
        aksi: bcForm.aksi,
        hasil: bcForm.hasil
      };
      
      const cleanJenis = selectedReport.jenis_kejadian.toUpperCase();
      if (cleanJenis.includes("KAPAL") || cleanJenis.includes("LAUT")) {
        metadataJson.data_kapal = {
          nama_kapal: bcForm.kapal_nama,
          jenis_kapal: bcForm.kapal_jenis,
          warna_kapal: bcForm.kapal_warna,
          imo: bcForm.kapal_imo,
          call_sign: bcForm.kapal_call_sign,
          telepon_satelit: bcForm.kapal_telp
        };
      } else if (cleanJenis.includes("PESAWAT") || cleanJenis.includes("UDARA")) {
        metadataJson.data_pesawat = {
          nama_pesawat: bcForm.pesawat_nama,
          jenis_pesawat: bcForm.pesawat_jenis,
          warna_pesawat: bcForm.pesawat_warna,
          register: bcForm.pesawat_register,
          rute: bcForm.pesawat_rute,
          operator: bcForm.pesawat_operator
        };
      } else if (cleanJenis.includes("KPK") || cleanJenis.includes("MANUSIA")) {
        metadataJson.data_alat = {
          jenis_kendaraan: bcForm.alat_jenis,
          warna_kendaraan: bcForm.alat_warna,
          nopol: bcForm.alat_nopol,
          pemilik: bcForm.alat_pemilik
        };
      }

      // Save to database
      const updatedPayload = {
        waktu: bcForm.waktu,
        lokasi_teks: bcForm.lokasi_teks,
        koordinat_lat: bcForm.koordinat_lat ? parseFloat(bcForm.koordinat_lat) : null,
        koordinat_lng: bcForm.koordinat_lng ? parseFloat(bcForm.koordinat_lng) : null,
        korban: `Total Korban: ${bcForm.korban_total || '-'} | S: ${bcForm.korban_selamat || '-'} | MD: ${bcForm.korban_meninggal || '-'} | DP: ${bcForm.korban_hilang || '-'}`,
        korban_total: bcForm.korban_total ? parseInt(bcForm.korban_total) : null,
        korban_selamat: bcForm.korban_selamat ? parseInt(bcForm.korban_selamat) : null,
        korban_meninggal: bcForm.korban_meninggal ? parseInt(bcForm.korban_meninggal) : null,
        korban_hilang: bcForm.korban_hilang ? parseInt(bcForm.korban_hilang) : null,
        data_korban: validVictims,
        unsur_alut: unsurAlutJson,
        metadata_kejadian: metadataJson,
        kronologi: bcForm.kronologi,
        status: 'AKTIF', // Promote to AKTIF
        info_awal_text: previewText
      };

      await updateReport(selectedReport.id, updatedPayload);

      // Trigger/Fetch preview if empty
      let textToSend = previewText;
      if (!textToSend) {
        const manualData: Record<string, string> = {
          waktu: bcForm.waktu,
          lokasi_teks: bcForm.lokasi_teks,
          KOORDINAT: bcForm.koordinat_lat && bcForm.koordinat_lng ? `${bcForm.koordinat_lat}, ${bcForm.koordinat_lng}` : '',
          JUMLAH_KORBAN_TOTAL: bcForm.korban_total,
          KORBAN_SELAMAT: bcForm.korban_selamat,
          KORBAN_MENINGGAL: bcForm.korban_meninggal,
          KORBAN_HILANG: bcForm.korban_hilang,
          KRONOLOGI: bcForm.kronologi,
          UNSUR_SAR: bcForm.unsur_sar_str,
          ALUT_PALSAR: bcForm.alut_palsar_str,
          CUACA: bcForm.cuaca,
          AKSI: bcForm.aksi,
          HASIL: bcForm.hasil
        };
        const res = await generateInfoAwal(selectedReport.id, manualData);
        textToSend = res.text;
      }

      // Broadcast to WhatsApp and Telegram Groups
      await sendBroadcast(selectedReport.id, textToSend);

      queryClient.invalidateQueries({ queryKey: ['reports'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
      setIsBroadcastModalOpen(false);
      setSelectedReport(null);
      alert('Info Awal Laporan berhasil diperdalam dan disiarkan ke Grup WhatsApp & Telegram.');
    } catch (err) {
      console.error("Gagal menyimpan & menyiarkan laporan:", err);
      alert('Terjadi kesalahan saat menyiarkan laporan. Silakan periksa koneksi atau input Anda.');
    } finally {
      setIsBroadcasting(false);
    }
  };

  const handleOpenCreate = () => {
    resetForm();
    setModalMode('create');
    setIsModalOpen(true);
  };


  const handleOpenDetail = (report: any) => {
    markReportAsRead(String(report.id));
    setSelectedReport(report);
    setModalMode('detail');
    setIsModalOpen(true);
  };

  const handleDelete = (id: number, noLaporan: string) => {
    if (window.confirm(`Apakah Anda yakin ingin menghapus laporan ${noLaporan}? Tindakan ini tidak dapat dibatalkan.`)) {
      deleteMutation.mutate(id);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (modalMode === 'create') {
      createMutation.mutate(formData);
    } else if (modalMode === 'edit' && selectedReport) {
      updateMutation.mutate({ id: selectedReport.id, data: formData });
    }
  };

  const getSourceLabel = (nomor: string) => {
    if (!nomor) return 'Web Manual';
    if (nomor.startsWith('@') || nomor.includes('tg_') || nomor.length < 10) return 'Telegram Bot';
    return 'WhatsApp Bot';
  };

  // Filter reports
  const filteredReports = reports.filter((report: any) => {
    const matchesFilter = filter === 'ALL' ? true : report.status === filter;
    const matchesType = typeFilter === 'ALL' ? true : report.jenis_kejadian === typeFilter;
    
    let matchesDate = true;
    if (dateFilter !== 'ALL') {
      const reportDate = report.created_at ? new Date(report.created_at) : null;
      if (!reportDate) {
        matchesDate = false;
      } else {
        const now = new Date();
        const diffTime = Math.abs(now.getTime() - reportDate.getTime());
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        
        if (dateFilter === 'TODAY') {
          matchesDate = reportDate.toDateString() === now.toDateString();
        } else if (dateFilter === 'WEEK') {
          matchesDate = diffDays <= 7;
        } else if (dateFilter === 'MONTH') {
          matchesDate = diffDays <= 30;
        }
      }
    }
    
    const searchLower = searchQuery.toLowerCase();
    const matchesSearch = 
      (report.no_laporan || '').toLowerCase().includes(searchLower) ||
      (report.jenis_kejadian || '').toLowerCase().includes(searchLower) ||
      (report.lokasi_teks || '').toLowerCase().includes(searchLower) ||
      (report.pelapor_nama || '').toLowerCase().includes(searchLower);
      
    return matchesFilter && matchesType && matchesDate && matchesSearch;
  });

  // Export Filtered Reports as CSV
  const handleExportCSV = () => {
    if (filteredReports.length === 0) {
      alert("Tidak ada data laporan untuk diekspor.");
      return;
    }

    const headers = ["No Laporan", "Jenis Kejadian", "Waktu", "Lokasi", "Pelapor", "Nomor Pelapor", "Korban", "Kronologi", "Status"];
    const rows = filteredReports.map((r: any) => [
      r.no_laporan || '',
      r.jenis_kejadian || '',
      r.waktu || '',
      r.lokasi_teks || '',
      r.pelapor_nama || '',
      r.pelapor_nomor || '',
      r.korban || '',
      (r.kronologi || '').replace(/\n/g, ' '),
      r.status || ''
    ]);

    const csvContent = "data:text/csv;charset=utf-8," 
      + [headers.join(","), ...rows.map((row: any[]) => row.map((val: any) => `"${String(val).replace(/"/g, '""')}"`).join(","))].join("\n");
    
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `laporan_sar_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-6 w-full">
      {newReportAlert && (
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          className="p-3.5 bg-slate-900 border border-slate-800 rounded-xl text-white font-semibold text-xs flex items-center justify-between shadow-sm"
        >
          <div className="flex items-center gap-3">
            <span className="w-2 h-2 rounded-full bg-orange-500 block animate-pulse" />
            <span>{newReportAlert.message}</span>
          </div>
          <button
            onClick={() => setNewReportAlert(null)}
            className="p-1 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors bg-transparent border-none cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </motion.div>
      )}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Laporan Masuk</h1>
          <p className="text-gray-500 mt-1">Kelola, detailkan, dan validasi laporan kejadian darurat.</p>
        </div>
        <div className="flex items-center gap-2.5">
          <button 
            onClick={handleExportCSV}
            className="px-3.5 py-2 bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 text-xs font-semibold rounded-xl transition-all shadow-xs flex items-center gap-1.5 cursor-pointer"
          >
            <FileText className="w-3.5 h-3.5 text-gray-500" />
            <span>Ekspor CSV</span>
          </button>
          <button 
            onClick={handleOpenCreate}
            className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold rounded-xl transition-all shadow-xs flex items-center gap-1.5 cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Buat Laporan Manual</span>
          </button>
        </div>
      </div>

      {/* FILTER & SEARCH PANEL */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-gray-100 flex flex-col md:flex-row md:items-center gap-4 justify-between">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input 
              type="text" 
              placeholder="Cari kejadian, nomor, atau lokasi..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2.5 bg-gray-50 border-none rounded-xl text-sm focus:ring-2 focus:ring-orange-500/20 focus:bg-white transition-all outline-none text-gray-700"
            />
          </div>

          <div className="flex items-center gap-3">
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs font-bold text-gray-650 outline-none focus:ring-2 focus:ring-orange-500/10 focus:bg-white cursor-pointer"
            >
              <option value="ALL">Semua Tipe</option>
              <option value="Laka Kapal">Laka Kapal</option>
              <option value="Laka Pesawat">Laka Pesawat</option>
              <option value="KMM">KMM (Kondisi Membahayakan)</option>
              <option value="Bencana">Bencana Alam</option>
              <option value="KPK">KPK (Kecelakaan Khusus)</option>
            </select>

            <select
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value)}
              className="px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs font-bold text-gray-650 outline-none focus:ring-2 focus:ring-orange-500/10 focus:bg-white cursor-pointer"
            >
              <option value="ALL">Semua Waktu</option>
              <option value="TODAY">Hari Ini</option>
              <option value="WEEK">7 Hari Terakhir</option>
              <option value="MONTH">30 Hari Terakhir</option>
            </select>
          </div>

          <div className="flex items-center gap-2 overflow-x-auto pb-1 md:pb-0">
            <button 
              className={`px-4 py-2 text-xs font-bold uppercase tracking-wider rounded-xl transition-all border ${
                filter === 'ALL' 
                  ? 'bg-gray-100 border-gray-200 text-gray-800 shadow-sm' 
                  : 'text-gray-500 border-transparent hover:bg-gray-50'
              }`}
              onClick={() => setFilter('ALL')}
            >
              Semua
            </button>
            <button 
              className={`px-4 py-2 text-xs font-bold uppercase tracking-wider rounded-xl transition-all border flex items-center gap-1.5 ${
                filter === 'PENDING' 
                  ? 'bg-orange-50 border-orange-200 text-orange-700 shadow-sm' 
                  : 'text-gray-500 border-transparent hover:bg-gray-50'
              }`}
              onClick={() => setFilter('PENDING')}
            >
              <Clock className="w-4 h-4" />
              Menunggu Validasi
            </button>
            <button 
              className={`px-4 py-2 text-xs font-bold uppercase tracking-wider rounded-xl transition-all border flex items-center gap-1.5 ${
                filter === 'AKTIF' 
                  ? 'bg-red-50 border-red-200 text-red-700 shadow-sm' 
                  : 'text-gray-500 border-transparent hover:bg-gray-50'
              }`}
              onClick={() => setFilter('AKTIF')}
            >
              <Activity className="w-4 h-4 text-red-500" />
              Aktif / Valid
            </button>
          </div>
        </div>

        {/* REPORTS TABLE */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-50/50">
                <th className="py-4 px-6 text-xs font-bold text-gray-500 uppercase tracking-wider border-b border-gray-100">Kejadian</th>
                <th className="py-4 px-6 text-xs font-bold text-gray-500 uppercase tracking-wider border-b border-gray-100">Lokasi</th>
                <th className="py-4 px-6 text-xs font-bold text-gray-500 uppercase tracking-wider border-b border-gray-100">Sumber</th>
                <th className="py-4 px-6 text-xs font-bold text-gray-500 uppercase tracking-wider border-b border-gray-100">Status</th>
                <th className="py-4 px-6 text-xs font-bold text-gray-500 uppercase tracking-wider border-b border-gray-100 text-right">Aksi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {isLoading ? (
                Array(5).fill(0).map((_, i) => (
                  <tr key={i}>
                    <td colSpan={5} className="py-5 px-6">
                      <SkeletonLoader className="w-full h-12" />
                    </td>
                  </tr>
                ))
              ) : isError ? (
                <tr>
                  <td colSpan={5} className="py-12">
                    <ErrorState message="Gagal memuat data laporan insiden." onRetry={refetch} />
                  </td>
                </tr>
              ) : filteredReports.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-12">
                    <EmptyState message="Tidak ada laporan darurat yang ditemukan." />
                  </td>
                </tr>
              ) : (
                filteredReports.map((report: any) => (
                  <tr key={report.id} className="hover:bg-gray-50/30 transition-colors">
                    <td className="py-4 px-6">
                      <div className="flex items-center gap-3.5">
                        <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 shadow-sm border ${
                          report.status === 'PENDING' 
                            ? 'bg-orange-50 border-orange-100 text-orange-600' 
                            : report.status === 'AKTIF' 
                            ? 'bg-red-50 border-red-100 text-red-600' 
                            : 'bg-green-50 border-green-100 text-green-600'
                        }`}>
                          <AlertTriangle className="w-5 h-5" />
                        </div>
                        <div className="min-w-0">
                          <div className="font-bold text-gray-800 text-sm truncate">
                            {report.jenis_kejadian} - {report.no_laporan}
                          </div>
                          <div className="text-[11px] text-gray-400 flex items-center gap-1 mt-0.5 font-medium">
                            <Clock className="w-3 h-3" /> {report.waktu}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="py-4 px-6">
                      <span className="text-sm font-semibold text-gray-700">{report.lokasi_teks}</span>
                    </td>
                    <td className="py-4 px-6">
                      <span className="text-xs font-bold text-gray-500 uppercase bg-gray-100/70 border border-gray-200/50 px-2.5 py-1 rounded-lg">
                        {getSourceLabel(report.pelapor_nomor)}
                      </span>
                    </td>
                    <td className="py-4 px-6">
                      <select
                        value={report.status}
                        onChange={(e) => handleStatusChange(report.id, e.target.value, report.no_laporan)}
                        className={`px-2.5 py-1 rounded-lg text-xs font-bold border outline-none cursor-pointer transition-all shadow-sm ${
                          report.status === 'PENDING' 
                            ? 'bg-orange-50 border-orange-200 text-orange-700 focus:ring-2 focus:ring-orange-500/10' 
                            : report.status === 'AKTIF' 
                            ? 'bg-red-50 border-red-200 text-red-700 focus:ring-2 focus:ring-red-500/10' 
                            : report.status === 'TIDAK_AKTIF' 
                            ? 'bg-gray-50 border-gray-200 text-gray-500 focus:ring-2 focus:ring-gray-500/10' 
                            : 'bg-red-50 border-red-200 text-red-600 focus:ring-2 focus:ring-red-500/10'
                        }`}
                      >
                        <option value="PENDING" className="text-orange-700 font-bold bg-white">Menunggu Validasi</option>
                        <option value="AKTIF" className="text-red-700 font-bold bg-white">Aktif / Valid</option>
                        <option value="TIDAK_AKTIF" className="text-gray-500 font-bold bg-white">Tidak Aktif</option>
                        <option value="SALAH_LAPORAN" className="text-red-600 font-bold bg-white">Salah Laporan</option>
                      </select>
                    </td>
                    <td className="py-4 px-6 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button 
                          onClick={() => handleOpenBroadcast(report)}
                          className="p-2 text-gray-400 hover:text-orange-600 hover:bg-orange-50 rounded-xl transition-all border border-transparent hover:border-orange-100"
                          title="Pendalaman & Kirim Grup (Info Awal)"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button 
                          onClick={() => handleOpenDetail(report)}
                          className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-xl transition-all border border-transparent hover:border-blue-100"
                          title="Lihat Detail"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        <button 
                          onClick={() => handleDelete(report.id, report.no_laporan)}
                          className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-xl transition-all border border-transparent hover:border-red-100"
                          title="Hapus Laporan"
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

      {/* POPUP MODAL: CRUD FORM & DETAILS */}
      <AnimatePresence>
        {isModalOpen && (
          <>
            {/* Backdrop */}
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.5 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsModalOpen(false)}
              className="fixed inset-0 bg-black z-40"
            />
            
            {/* Modal Dialog */}
            <motion.div 
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="fixed inset-0 m-auto w-[600px] h-fit max-h-[85vh] bg-white rounded-3xl shadow-2xl border border-gray-100 z-50 overflow-hidden flex flex-col"
            >
              {/* Modal Header */}
              <div className="p-5 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-10 h-10 rounded-xl bg-orange-50 border border-orange-100 flex items-center justify-center text-orange-600">
                    <FileText className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-gray-800 text-base">
                      {modalMode === 'create' && 'Buat Laporan Baru'}
                      {modalMode === 'edit' && `Sunting Laporan: ${selectedReport?.no_laporan}`}
                      {modalMode === 'detail' && `Detail Laporan: ${selectedReport?.no_laporan}`}
                    </h3>
                    <p className="text-[11px] text-gray-500 mt-0.5">
                      {modalMode === 'detail' ? 'Informasi kejadian terekstraksi oleh AI' : 'Isi kolom data di bawah dengan benar'}
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
                {modalMode === 'detail' && selectedReport ? (
                  /* --- DETAIL VIEW --- */
                  <div className="space-y-4 text-sm">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="p-3 bg-gray-50 rounded-xl border border-gray-100 flex items-start gap-3">
                        <User className="w-4 h-4 text-orange-600 mt-0.5 shrink-0" />
                        <div>
                          <p className="text-[10px] text-gray-400 font-bold uppercase">Nama Pelapor</p>
                          <p className="font-bold text-gray-800 mt-0.5">{selectedReport.pelapor_nama}</p>
                        </div>
                      </div>
                      <div className="p-3 bg-gray-50 rounded-xl border border-gray-100 flex items-start gap-3">
                        <Phone className="w-4 h-4 text-orange-600 mt-0.5 shrink-0" />
                        <div>
                          <p className="text-[10px] text-gray-400 font-bold uppercase">Nomor Pelapor</p>
                          <p className="font-bold text-gray-800 mt-0.5 font-mono">{selectedReport.pelapor_nomor}</p>
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-4">
                      <div className="p-3 bg-gray-50 rounded-xl border border-gray-100 flex items-start gap-3">
                        <AlertTriangle className="w-4 h-4 text-orange-600 mt-0.5 shrink-0" />
                        <div className="min-w-0">
                          <p className="text-[10px] text-gray-400 font-bold uppercase truncate">Jenis Kejadian</p>
                          <p className="font-bold text-gray-800 mt-0.5 truncate">{selectedReport.jenis_kejadian}</p>
                        </div>
                      </div>
                      <div className="p-3 bg-gray-50 rounded-xl border border-gray-100 flex items-start gap-3">
                        <Calendar className="w-4 h-4 text-orange-600 mt-0.5 shrink-0" />
                        <div className="min-w-0">
                          <p className="text-[10px] text-gray-400 font-bold uppercase truncate">Waktu Kejadian</p>
                          <p className="font-bold text-gray-800 mt-0.5 truncate">{selectedReport.waktu}</p>
                        </div>
                      </div>
                      <div className="p-3 bg-gray-50 rounded-xl border border-gray-100 flex items-start gap-3">
                        <MapPin className="w-4 h-4 text-orange-600 mt-0.5 shrink-0" />
                        <div className="min-w-0">
                          <p className="text-[10px] text-gray-400 font-bold uppercase truncate">Lokasi Kejadian</p>
                          <p className="font-bold text-gray-800 mt-0.5 truncate">{selectedReport.lokasi_teks}</p>
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="p-3 bg-gray-50 rounded-xl border border-gray-100 flex items-start gap-3">
                        <Users2 className="w-4 h-4 text-orange-600 mt-0.5 shrink-0" />
                        <div>
                          <p className="text-[10px] text-gray-400 font-bold uppercase">Data Korban</p>
                          <p className="font-bold text-gray-800 mt-0.5">{selectedReport.korban}</p>
                        </div>
                      </div>
                      <div className="p-3 bg-gray-50 rounded-xl border border-gray-100 flex items-start gap-3">
                        <Info className="w-4 h-4 text-orange-600 mt-0.5 shrink-0" />
                        <div>
                          <p className="text-[10px] text-gray-400 font-bold uppercase">Status Laporan</p>
                          <p className="font-bold text-gray-800 mt-0.5 uppercase tracking-wide">{selectedReport.status}</p>
                        </div>
                      </div>
                    </div>

                    <div className="p-3.5 bg-gray-50 rounded-xl border border-gray-100 space-y-1">
                      <p className="text-[10px] text-gray-400 font-bold uppercase">Kronologi Detail</p>
                      <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">{selectedReport.kronologi}</p>
                    </div>

                    {selectedReport.gmaps_link && (
                      <div className="p-3 bg-orange-50 text-orange-800 rounded-xl border border-orange-100 flex gap-2">
                        <Info className="w-4 h-4 text-orange-600 shrink-0 mt-0.5" />
                        <div className="text-xs">
                          <p className="font-bold">Informasi Geospasial</p>
                          <a href={selectedReport.gmaps_link} target="_blank" rel="noopener noreferrer" className="underline mt-1 block font-semibold text-orange-700 hover:text-orange-950">
                            Buka Lokasi di Google Maps &rarr;
                          </a>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  /* --- CREATE & EDIT FORM VIEWS --- */
                  <form id="reportForm" onSubmit={handleSubmit} className="space-y-4 text-xs">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-1.5">
                        <label className="block font-bold text-gray-700">Nama Pelapor</label>
                        <input
                          type="text"
                          required
                          value={formData.pelapor_nama}
                          onChange={(e) => setFormData({ ...formData, pelapor_nama: e.target.value })}
                          placeholder="Contoh: Bang Andra"
                          className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none text-gray-800"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="block font-bold text-gray-700">Nomor Telepon/ID Pelapor</label>
                        <input
                          type="text"
                          required
                          value={formData.pelapor_nomor}
                          onChange={(e) => setFormData({ ...formData, pelapor_nomor: e.target.value })}
                          placeholder="Contoh: 08123456789"
                          className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none text-gray-800"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-4">
                      <div className="space-y-1.5">
                        <label className="block font-bold text-gray-700">Jenis Kejadian</label>
                        <select
                          value={formData.jenis_kejadian}
                          onChange={(e) => setFormData({ ...formData, jenis_kejadian: e.target.value })}
                          className="w-full px-2.5 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none text-gray-800"
                        >
                          <option value="Laka Kapal">Laka Kapal</option>
                          <option value="Laka Pesawat">Laka Pesawat</option>
                          <option value="KMM">KMM (Kondisi Membahayakan Manusia)</option>
                          <option value="Bencana">Bencana</option>
                          <option value="KPK">KPK (Kecelakaan dengan Penanganan Khusus)</option>
                        </select>
                      </div>
                      <div className="space-y-1.5">
                        <label className="block font-bold text-gray-700">Waktu Kejadian</label>
                        <input
                          type="text"
                          required
                          value={formData.waktu}
                          onChange={(e) => setFormData({ ...formData, waktu: e.target.value })}
                          placeholder="Contoh: Tadi subuh"
                          className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none text-gray-800"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="block font-bold text-gray-700">Lokasi Kejadian</label>
                        <input
                          type="text"
                          required
                          value={formData.lokasi_teks}
                          onChange={(e) => setFormData({ ...formData, lokasi_teks: e.target.value })}
                          placeholder="Contoh: Perairan Senoa"
                          className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none text-gray-800"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-1.5">
                        <label className="block font-bold text-gray-700">Jumlah/Kondisi Korban</label>
                        <input
                          type="text"
                          required
                          value={formData.korban}
                          onChange={(e) => setFormData({ ...formData, korban: e.target.value })}
                          placeholder="Contoh: 1 orang pingsan"
                          className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none text-gray-800"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="block font-bold text-gray-700">Status Laporan</label>
                        <select
                          value={formData.status}
                          onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                          className="w-full px-2.5 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none text-gray-800"
                        >
                          <option value="PENDING">PENDING (Menunggu Validasi)</option>
                          <option value="AKTIF">AKTIF (Valid & Broadcasted)</option>
                          <option value="TIDAK_AKTIF">TIDAK AKTIF</option>
                          <option value="SALAH_LAPORAN">SALAH LAPORAN</option>
                        </select>
                      </div>
                    </div>

                    <div className="space-y-1.5">
                      <label className="block font-bold text-gray-700">Kronologi Kejadian</label>
                      <textarea
                        required
                        rows={4}
                        value={formData.kronologi}
                        onChange={(e) => setFormData({ ...formData, kronologi: e.target.value })}
                        placeholder="Uraikan kronologi kejadian insiden selengkap mungkin..."
                        className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none text-gray-800 leading-normal resize-none"
                      />
                    </div>
                  </form>
                )}
              </div>

              {/* Modal Footer */}
              <div className="p-4 border-t border-gray-100 bg-gray-50 flex items-center justify-end gap-2.5">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 border border-gray-200 hover:bg-gray-100 text-gray-600 font-semibold text-xs rounded-xl transition-all"
                >
                  Tutup
                </button>
                {modalMode !== 'detail' && (
                  <button
                    type="submit"
                    form="reportForm"
                    disabled={createMutation.isPending || updateMutation.isPending}
                    className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white font-semibold text-xs rounded-xl shadow transition-all flex items-center gap-1.5 disabled:bg-gray-200 disabled:cursor-not-allowed"
                  >
                    {(createMutation.isPending || updateMutation.isPending) ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" /> Menyimpan...
                      </>
                    ) : (
                      'Simpan Perubahan'
                    )}
                  </button>
                )}
              </div>
            </motion.div>
          </>
        )}

        {isBroadcastModalOpen && selectedReport && (
          <>
            {/* Backdrop */}
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.5 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsBroadcastModalOpen(false)}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
            />
            
            {/* Modal Dialog */}
            <motion.div 
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="fixed inset-0 m-auto w-[1100px] h-[90vh] bg-white rounded-3xl shadow-2xl border border-gray-150 z-50 overflow-hidden flex flex-col"
            >
              {/* Modal Header */}
              <div className="p-5 border-b border-gray-100 bg-[#111827] text-white flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-orange-600 flex items-center justify-center text-white shadow-md shadow-orange-500/20">
                    <Send className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-base flex items-center gap-2">
                      Pendalaman Info Awal & Diseminasi Grup
                      <span className="text-xs bg-orange-500/20 text-orange-300 border border-orange-500/30 px-2.5 py-0.5 rounded-full font-mono">
                        {selectedReport.no_laporan}
                      </span>
                    </h3>
                    <p className="text-xs text-gray-400 mt-0.5">
                      Perdalam rincian operasional koordinat, korban, alut, dan unsur lalu siarkan laporan resmi ke Grup WA & Telegram.
                    </p>
                  </div>
                </div>
                <button 
                  onClick={() => setIsBroadcastModalOpen(false)}
                  className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded-xl transition-all"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Modal Body (Dual Column) */}
              <div className="flex-1 overflow-hidden flex divide-x divide-gray-150">
                
                {/* Left Column: Scrollable Consolidated Form Inputs (60%) */}
                <div className="w-7/12 h-full flex flex-col bg-gray-50/50">
                  
                  {/* Title Bar */}
                  <div className="px-6 py-4 border-b border-gray-150 bg-white flex items-center justify-between shrink-0 shadow-sm">
                    <span className="text-xs font-black uppercase tracking-wider text-gray-700">Form Pendalaman Data Operasional</span>
                    <span className="text-[9px] bg-orange-50 text-orange-700 font-bold px-2 py-0.5 rounded-full border border-orange-105">Lengkapi Seksi 1-4</span>
                  </div>

                  {/* Single Consolidated Scroll Container */}
                  <div className="flex-1 overflow-y-auto p-6 space-y-6">
                    
                    {/* SECTION 1: DASAR & LOKASI */}
                    <div className="space-y-4">
                      <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm space-y-4">
                        <h4 className="font-extrabold text-gray-800 text-xs uppercase tracking-wider text-orange-600 border-b border-gray-50 pb-2">1. Waktu & Lokasi Kejadian</h4>
                        
                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-1.5">
                            <label className="block text-xs font-bold text-gray-700">Waktu Kejadian</label>
                            <input
                              type="text"
                              value={bcForm.waktu}
                              onChange={(e) => setBcForm({ ...bcForm, waktu: e.target.value })}
                              placeholder="Contoh: Minggu, 24 Mei 2026 Pukul 11:23 WIB"
                              className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none text-gray-800"
                            />
                          </div>
                          <div className="space-y-1.5">
                            <label className="block text-xs font-bold text-gray-700">Lokasi Teks</label>
                            <input
                              type="text"
                              value={bcForm.lokasi_teks}
                              onChange={(e) => setBcForm({ ...bcForm, lokasi_teks: e.target.value })}
                              placeholder="Contoh: Perairan Jemaja, Kabupaten Anambas"
                              className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none text-gray-800"
                            />
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-1.5">
                            <label className="block text-xs font-bold text-gray-700">Latitude (Koordinat Desimal)</label>
                            <input
                              type="number"
                              step="any"
                              value={bcForm.koordinat_lat}
                              onChange={(e) => setBcForm({ ...bcForm, koordinat_lat: e.target.value })}
                              placeholder="Contoh: 2.8896"
                              className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none text-gray-800 font-mono"
                            />
                          </div>
                          <div className="space-y-1.5">
                            <label className="block text-xs font-bold text-gray-700">Longitude (Koordinat Desimal)</label>
                            <input
                              type="number"
                              step="any"
                              value={bcForm.koordinat_lng}
                              onChange={(e) => setBcForm({ ...bcForm, koordinat_lng: e.target.value })}
                              placeholder="Contoh: 105.2871"
                              className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none text-gray-800 font-mono"
                            />
                          </div>
                        </div>
                      </div>

                      <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm space-y-3">
                        <h4 className="font-extrabold text-gray-800 text-xs uppercase tracking-wider text-orange-600 border-b border-gray-50 pb-2">Kronologi Awal</h4>
                        <textarea
                          rows={5}
                          value={bcForm.kronologi}
                          onChange={(e) => setBcForm({ ...bcForm, kronologi: e.target.value })}
                          placeholder="Uraikan peristiwa awal kejadian musibah..."
                          className="w-full px-3.5 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none text-gray-800 leading-normal resize-none"
                        />
                      </div>
                    </div>

                    {/* SECTION 2: KEADAAN KORBAN */}
                    <div className="space-y-4">
                      <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm space-y-4">
                        <h4 className="font-extrabold text-gray-800 text-xs uppercase tracking-wider text-orange-600 border-b border-gray-50 pb-2">2. Keadaan Korban (Breakdown)</h4>
                        
                        <div className="grid grid-cols-4 gap-3">
                          <div className="space-y-1.5">
                            <label className="block text-[11px] font-bold text-gray-700">Total Korban</label>
                            <input
                              type="number"
                              value={bcForm.korban_total}
                              onChange={(e) => setBcForm({ ...bcForm, korban_total: e.target.value })}
                              placeholder="Org"
                              className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none text-gray-800 font-bold"
                            />
                          </div>
                          <div className="space-y-1.5">
                            <label className="block text-[11px] font-bold text-green-700">S (Selamat)</label>
                            <input
                              type="number"
                              value={bcForm.korban_selamat}
                              onChange={(e) => setBcForm({ ...bcForm, korban_selamat: e.target.value })}
                              placeholder="Org"
                              className="w-full px-3 py-2 bg-green-50/50 border border-green-200 rounded-xl text-xs focus:ring-1 focus:ring-green-500 focus:bg-white outline-none text-green-800 font-bold"
                            />
                          </div>
                          <div className="space-y-1.5">
                            <label className="block text-[11px] font-bold text-red-700">MD (Meninggal)</label>
                            <input
                              type="number"
                              value={bcForm.korban_meninggal}
                              onChange={(e) => setBcForm({ ...bcForm, korban_meninggal: e.target.value })}
                              placeholder="Org"
                              className="w-full px-3 py-2 bg-red-50/50 border border-red-200 rounded-xl text-xs focus:ring-1 focus:ring-red-500 focus:bg-white outline-none text-red-800 font-bold"
                            />
                          </div>
                          <div className="space-y-1.5">
                            <label className="block text-[11px] font-bold text-orange-700">DP (Hilang)</label>
                            <input
                              type="number"
                              value={bcForm.korban_hilang}
                              onChange={(e) => setBcForm({ ...bcForm, korban_hilang: e.target.value })}
                              placeholder="Org"
                              className="w-full px-3 py-2 bg-orange-50/50 border border-orange-200 rounded-xl text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none text-orange-800 font-bold"
                            />
                          </div>
                        </div>
                      </div>

                      {/* List Detail Korban */}
                      <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm space-y-4">
                        <div className="flex items-center justify-between border-b border-gray-50 pb-2">
                          <h4 className="font-extrabold text-gray-800 text-xs uppercase tracking-wider text-orange-600">Daftar Rincian Identitas Korban</h4>
                          <button
                            type="button"
                            onClick={handleAddVictim}
                            className="px-2.5 py-1 bg-orange-50 hover:bg-orange-100 text-orange-700 text-[10px] font-extrabold rounded-lg border border-orange-100 flex items-center gap-1 transition-all"
                          >
                            <Plus className="w-3.5 h-3.5" /> Tambah Korban
                          </button>
                        </div>

                        <div className="space-y-3.5 max-h-[300px] overflow-y-auto pr-1">
                          {bcVictims.map((vic, index) => (
                            <div key={index} className="p-3 bg-gray-50 rounded-xl border border-gray-150 relative space-y-2.5">
                              <div className="flex items-center justify-between">
                                <span className="text-[10px] font-extrabold text-gray-500 uppercase tracking-wide">Korban Ke-{index+1}</span>
                                {bcVictims.length > 1 && (
                                  <button
                                    type="button"
                                    onClick={() => handleRemoveVictim(index)}
                                    className="text-red-500 hover:text-red-700 p-0.5 rounded transition-all hover:bg-red-50"
                                  >
                                    <X className="w-4 h-4" />
                                  </button>
                                )}
                              </div>
                              <div className="grid grid-cols-2 gap-2">
                                <input
                                  type="text"
                                  value={vic.nama}
                                  onChange={(e) => handleUpdateVictim(index, 'nama', e.target.value)}
                                  placeholder="Nama Korban"
                                  className="px-2 py-1.5 bg-white border border-gray-200 rounded-lg text-[11px] outline-none focus:ring-1 focus:ring-orange-500 w-full"
                                />
                                <select
                                  value={vic.jenis_kelamin}
                                  onChange={(e) => handleUpdateVictim(index, 'jenis_kelamin', e.target.value)}
                                  className="px-2 py-1.5 bg-white border border-gray-200 rounded-lg text-[11px] outline-none focus:ring-1 focus:ring-orange-500 w-full"
                                >
                                  <option value="Laki-laki">Laki-laki</option>
                                  <option value="Perempuan">Perempuan</option>
                                </select>
                              </div>
                              <div className="grid grid-cols-3 gap-2">
                                <input
                                  type="text"
                                  value={vic.umur}
                                  onChange={(e) => handleUpdateVictim(index, 'umur', e.target.value)}
                                  placeholder="Umur (e.g. 8 thn)"
                                  className="px-2 py-1.5 bg-white border border-gray-200 rounded-lg text-[11px] outline-none w-full"
                                />
                                <input
                                  type="text"
                                  value={vic.alamat}
                                  onChange={(e) => handleUpdateVictim(index, 'alamat', e.target.value)}
                                  placeholder="Alamat"
                                  className="px-2 py-1.5 bg-white border border-gray-200 rounded-lg text-[11px] outline-none w-full col-span-2"
                                />
                              </div>
                              <input
                                  type="text"
                                  value={vic.ciri_ciri || ''}
                                  onChange={(e) => handleUpdateVictim(index, 'ciri_ciri', e.target.value)}
                                  placeholder="Ciri-ciri khusus korban (bila ada)"
                                  className="px-2 py-1.5 bg-white border border-gray-200 rounded-lg text-[11px] outline-none w-full"
                                />
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    {/* SECTION 3: DATA KHUSUS SPESIFIK */}
                    <div className="space-y-4">
                      {(selectedReport.jenis_kejadian.toUpperCase().includes("KAPAL") || selectedReport.jenis_kejadian.toUpperCase().includes("LAUT")) && (
                        <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm space-y-4">
                          <h4 className="font-extrabold text-gray-800 text-xs uppercase tracking-wider text-orange-600 border-b border-gray-50 pb-2">3. Rincian Data Kapal (LAKA KAPAL)</h4>
                          
                          <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                              <label className="block text-xs font-bold text-gray-700">Nama Kapal</label>
                              <input
                                type="text"
                                value={bcForm.kapal_nama}
                                onChange={(e) => setBcForm({ ...bcForm, kapal_nama: e.target.value })}
                                placeholder="Contoh: MV SS 2"
                                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none"
                              />
                            </div>
                            <div className="space-y-1.5">
                              <label className="block text-xs font-bold text-gray-700">Jenis Kapal</label>
                              <input
                                type="text"
                                value={bcForm.kapal_jenis}
                                onChange={(e) => setBcForm({ ...bcForm, kapal_jenis: e.target.value })}
                                placeholder="Contoh: Kapal Kargo"
                                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none"
                              />
                            </div>
                          </div>

                          <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                              <label className="block text-xs font-bold text-gray-700">Warna Kapal</label>
                              <input
                                type="text"
                                value={bcForm.kapal_warna}
                                onChange={(e) => setBcForm({ ...bcForm, kapal_warna: e.target.value })}
                                placeholder="Contoh: Hitam Kuning"
                                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:ring-1 focus:ring-orange-500"
                              />
                            </div>
                            <div className="space-y-1.5">
                              <label className="block text-xs font-bold text-gray-700">IMO Kapal</label>
                              <input
                                type="text"
                                value={bcForm.kapal_imo}
                                onChange={(e) => setBcForm({ ...bcForm, kapal_imo: e.target.value })}
                                placeholder="Contoh: 9158123"
                                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:ring-1 focus:ring-orange-500"
                              />
                            </div>
                          </div>

                          <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                              <label className="block text-xs font-bold text-gray-700">Call Sign</label>
                              <input
                                type="text"
                                value={bcForm.kapal_call_sign}
                                onChange={(e) => setBcForm({ ...bcForm, kapal_call_sign: e.target.value })}
                                placeholder="Contoh: XYNX"
                                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs"
                              />
                            </div>
                            <div className="space-y-1.5">
                              <label className="block text-xs font-bold text-gray-700">Telepon Satelit</label>
                              <input
                                type="text"
                                value={bcForm.kapal_telp}
                                onChange={(e) => setBcForm({ ...bcForm, kapal_telp: e.target.value })}
                                placeholder="Contoh: +88 164170530"
                                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs font-mono"
                              />
                            </div>
                          </div>
                        </div>
                      )}

                      {(selectedReport.jenis_kejadian.toUpperCase().includes("PESAWAT") || selectedReport.jenis_kejadian.toUpperCase().includes("UDARA")) && (
                        <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm space-y-4">
                          <h4 className="font-extrabold text-gray-800 text-xs uppercase tracking-wider text-orange-600 border-b border-gray-50 pb-2">3. Rincian Data Pesawat (LAKA PESAWAT)</h4>
                          
                          <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                              <label className="block text-xs font-bold text-gray-700">Nama/Tipe Pesawat</label>
                              <input
                                type="text"
                                value={bcForm.pesawat_nama}
                                onChange={(e) => setBcForm({ ...bcForm, pesawat_nama: e.target.value })}
                                placeholder="Contoh: Boeing 737"
                                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs"
                              />
                            </div>
                            <div className="space-y-1.5">
                              <label className="block text-xs font-bold text-gray-700">Jenis Pesawat</label>
                              <input
                                type="text"
                                value={bcForm.pesawat_jenis}
                                onChange={(e) => setBcForm({ ...bcForm, pesawat_jenis: e.target.value })}
                                placeholder="Contoh: Pesawat Penumpang"
                                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs"
                              />
                            </div>
                          </div>

                          <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                              <label className="block text-xs font-bold text-gray-700">Warna/Registrasi</label>
                              <input
                                type="text"
                                value={bcForm.pesawat_warna}
                                onChange={(e) => setBcForm({ ...bcForm, pesawat_warna: e.target.value })}
                                placeholder="Contoh: Biru Putih"
                                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs"
                              />
                            </div>
                            <div className="space-y-1.5">
                              <label className="block text-xs font-bold text-gray-700">Register / Call Sign</label>
                              <input
                                type="text"
                                value={bcForm.pesawat_register}
                                onChange={(e) => setBcForm({ ...bcForm, pesawat_register: e.target.value })}
                                placeholder="Contoh: PK-ABC"
                                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs font-mono"
                              />
                            </div>
                          </div>

                          <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                              <label className="block text-xs font-bold text-gray-700">Rute</label>
                              <input
                                type="text"
                                value={bcForm.pesawat_rute}
                                onChange={(e) => setBcForm({ ...bcForm, pesawat_rute: e.target.value })}
                                placeholder="Contoh: Jakarta - Natuna"
                                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs"
                              />
                            </div>
                            <div className="space-y-1.5">
                              <label className="block text-xs font-bold text-gray-700">Operator</label>
                              <input
                                type="text"
                                value={bcForm.pesawat_operator}
                                onChange={(e) => setBcForm({ ...bcForm, pesawat_operator: e.target.value })}
                                placeholder="Contoh: Sriwijaya Air"
                                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs"
                              />
                            </div>
                          </div>
                        </div>
                      )}

                      {(!selectedReport.jenis_kejadian.toUpperCase().includes("KAPAL") && !selectedReport.jenis_kejadian.toUpperCase().includes("PESAWAT") && !selectedReport.jenis_kejadian.toUpperCase().includes("LAUT") && !selectedReport.jenis_kejadian.toUpperCase().includes("UDARA")) && (
                        <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm space-y-4">
                          <h4 className="font-extrabold text-gray-800 text-xs uppercase tracking-wider text-orange-600 border-b border-gray-50 pb-2">3. Rincian Data Sarana/Kendaraan (KPK / LANTAS)</h4>
                          
                          <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                              <label className="block text-xs font-bold text-gray-700">Jenis Kendaraan</label>
                              <input
                                type="text"
                                value={bcForm.alat_jenis}
                                onChange={(e) => setBcForm({ ...bcForm, alat_jenis: e.target.value })}
                                placeholder="Contoh: Pompong / Sepeda Motor"
                                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs"
                              />
                            </div>
                            <div className="space-y-1.5">
                              <label className="block text-xs font-bold text-gray-700">Warna Kendaraan</label>
                              <input
                                type="text"
                                value={bcForm.alat_warna}
                                onChange={(e) => setBcForm({ ...bcForm, alat_warna: e.target.value })}
                                placeholder="Contoh: Hijau Putih"
                                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs"
                              />
                            </div>
                          </div>

                          <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                              <label className="block text-xs font-bold text-gray-700">Nomor Polisi / Lambung</label>
                              <input
                                type="text"
                                value={bcForm.alat_nopol}
                                onChange={(e) => setBcForm({ ...bcForm, alat_nopol: e.target.value })}
                                placeholder="Contoh: BP 1234 NN"
                                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs font-mono"
                              />
                            </div>
                            <div className="space-y-1.5">
                              <label className="block text-xs font-bold text-gray-700">Pemilik</label>
                              <input
                                type="text"
                                value={bcForm.alat_pemilik}
                                onChange={(e) => setBcForm({ ...bcForm, alat_pemilik: e.target.value })}
                                placeholder="Contoh: Bpk Nurul Huda"
                                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs"
                              />
                            </div>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* SECTION 4: OPERASIONAL & CUACA */}
                    <div className="space-y-4">
                      <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm space-y-4">
                        <h4 className="font-extrabold text-gray-800 text-xs uppercase tracking-wider text-orange-600 border-b border-gray-50 pb-2">4. Unsur SAR & Alut Palsar Terlibat</h4>
                        
                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-1.5">
                            <label className="block text-xs font-bold text-gray-700 flex items-center justify-between">
                              <span>Unsur SAR Terlibat</span>
                              <span className="text-[10px] text-gray-400 font-normal">Satu unsur per baris</span>
                            </label>
                            <textarea
                              rows={4}
                              value={bcForm.unsur_sar_str}
                              onChange={(e) => setBcForm({ ...bcForm, unsur_sar_str: e.target.value })}
                              placeholder="Contoh:&#10;Kantor SAR Natuna&#10;BPBD Natuna&#10;Masyarakat"
                              className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none resize-none font-medium leading-normal"
                            />
                          </div>
                          <div className="space-y-1.5">
                            <label className="block text-xs font-bold text-gray-700 flex items-center justify-between">
                              <span>Alut & Palsar Digunakan</span>
                              <span className="text-[10px] text-gray-400 font-normal">Satu alut per baris</span>
                            </label>
                            <textarea
                              rows={4}
                              value={bcForm.alut_palsar_str}
                              onChange={(e) => setBcForm({ ...bcForm, alut_palsar_str: e.target.value })}
                              placeholder="Contoh:&#10;LCR&#10;RIB Anambas&#10;Peralatan Selam"
                              className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none resize-none font-medium leading-normal"
                            />
                          </div>
                        </div>
                      </div>

                      <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm space-y-4">
                        <h4 className="font-extrabold text-gray-800 text-xs uppercase tracking-wider text-orange-600 border-b border-gray-50 pb-2">Cuaca, Aksi, & Hasil</h4>
                        
                        <div className="space-y-1.5">
                          <label className="block text-xs font-bold text-gray-700">Kondisi Cuaca</label>
                          <input
                            type="text"
                            value={bcForm.cuaca}
                            onChange={(e) => setBcForm({ ...bcForm, cuaca: e.target.value })}
                            placeholder="Contoh: Cuaca Berawan Tebal, Suhu 26°C, Gelombang 0.5-1.25 M"
                            className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none"
                          />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-1.5">
                            <label className="block text-xs font-bold text-gray-700">Aksi yang Telah Dilakukan</label>
                            <textarea
                              rows={3}
                              value={bcForm.aksi}
                              onChange={(e) => setBcForm({ ...bcForm, aksi: e.target.value })}
                              placeholder="Contoh: Kantor SAR berkoordinasi dengan potensi SAR terdekat"
                              className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none resize-none"
                            />
                          </div>
                          <div className="space-y-1.5">
                            <label className="block text-xs font-bold text-gray-700">Hasil Pemantauan Awal</label>
                            <textarea
                              rows={3}
                              value={bcForm.hasil}
                              onChange={(e) => setBcForm({ ...bcForm, hasil: e.target.value })}
                              placeholder="Contoh: Masih dalam pencarian / Pemantauan..."
                              className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:ring-1 focus:ring-orange-500 focus:bg-white outline-none resize-none"
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Right Column: Markdown Live Preview & Send (40%) */}
                <div className="w-5/12 h-full flex flex-col bg-slate-900 text-slate-100">
                  <div className="p-4 border-b border-slate-800 bg-slate-950 flex items-center justify-between shrink-0">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                      <FileText className="w-4 h-4 text-orange-500" /> Pratinjau Info Awal Resmi
                    </span>
                    <button
                      type="button"
                      disabled={isPreviewLoading}
                      onClick={() => handleRefreshPreview(selectedReport.id)}
                      className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 text-[10px] font-bold rounded-lg border border-slate-700 flex items-center gap-1.5 transition-all disabled:opacity-50"
                    >
                      {isPreviewLoading ? <Loader2 className="w-3 h-3 animate-spin text-orange-500" /> : <Activity className="w-3 h-3" />}
                      Segarkan Preview
                    </button>
                  </div>

                  {/* Rendered Text Box (Editable Textarea) */}
                  <div className="flex-1 overflow-hidden relative bg-slate-950">
                    {isPreviewLoading && !previewText ? (
                      <div className="h-full w-full flex flex-col items-center justify-center gap-2 text-slate-500 absolute inset-0 z-10 bg-slate-950/80">
                        <Loader2 className="w-6 h-6 animate-spin text-orange-500" />
                        <span className="text-[10px] font-semibold tracking-wider uppercase animate-pulse">Menghimpun Laporan Info Awal...</span>
                      </div>
                    ) : null}
                    <textarea
                      value={previewText}
                      onChange={(e) => setPreviewText(e.target.value)}
                      placeholder="Klik 'Segarkan Preview' untuk memuat format info awal."
                      className="w-full h-full p-5 bg-slate-950 text-green-400 font-mono text-xs leading-relaxed resize-none outline-none border-none focus:ring-0 selection:bg-orange-600 selection:text-white"
                    />
                  </div>

                  {/* Submit / Action Panel */}
                  <div className="p-5 border-t border-slate-800 bg-slate-950 shrink-0 space-y-3">
                    <div className="p-3 bg-orange-950/40 border border-orange-500/20 rounded-2xl flex gap-2">
                      <ShieldAlert className="w-4 h-4 text-orange-500 shrink-0 mt-0.5" />
                      <p className="text-[10px] text-orange-300 leading-normal font-semibold">
                        Tindakan ini akan secara otomatis memperbarui rincian di PostgreSQL dan memicu diseminasi pesan ke grup WhatsApp & Telegram SAR Command Center.
                      </p>
                    </div>

                    <div className="flex gap-3">
                      <button
                        type="button"
                        onClick={() => setIsBroadcastModalOpen(false)}
                        className="px-4 py-3 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 font-bold text-xs rounded-xl transition-all"
                      >
                        Batal
                      </button>
                      <button
                        type="button"
                        disabled={isBroadcasting || isPreviewLoading}
                        onClick={handleSaveAndBroadcast}
                        className="flex-1 py-3 bg-orange-600 hover:bg-orange-700 text-white font-bold text-xs rounded-xl shadow-xs transition-all flex items-center justify-center gap-2 disabled:bg-slate-800 disabled:text-slate-500 disabled:cursor-not-allowed"
                      >
                        {isBroadcasting ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            <span>Menyiarkan Laporan...</span>
                          </>
                        ) : (
                          <>
                            <Send className="w-4 h-4" />
                            <span>Simpan & Siarkan Info Awal</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                </div>

              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function ReportsPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-orange-500" />
      </div>
    }>
      <ReportsPageContent />
    </Suspense>
  );
}
