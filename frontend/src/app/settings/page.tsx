'use client';

import { useState, useEffect, useRef } from 'react';
import { 
  Save, Settings2, Key, Database, MessageSquare, Loader2, 
  CheckCircle2, MapPin, Plus, Trash2, Edit2, Shield, 
  Radio, RefreshCw, Server, AlertCircle, Building2, 
  UserPlus, Users, FileText, Check, X, Info, Upload, Globe, ExternalLink,
  Eye, EyeOff, Calendar, Cpu, ArrowUpCircle, AlertTriangle, UploadCloud, Search,
  Lock
} from 'lucide-react';
import { decodeJwt } from '@/lib/utils';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  getSettings, updateSettings, getLiveStatus, setupTelegramWebhook, getIdentity, updateIdentity,
  uploadIdentityKml, deleteIdentityKml, uploadIdentityLogo, deleteIdentityLogo, getLocations, createLocation,
  updateLocation, deleteLocation, uploadLocationIcon, getBackendUrl,
  getClassifications, createClassification, updateClassification, deleteClassification,
  getUsers, createUser, updateUser, deleteUser, getOllamaModels, testAiConnection,
  exportDatabaseBackup, importDatabaseRestore, getWidgetRequests, approveWidgetRequest, rejectWidgetRequest,
  createWidgetRequestAdmin, updateWidgetRequest, deleteWidgetRequest, getSopDocuments,
  uploadSopDocument, vectorizeSopDocument, deleteSopDocument
} from '@/lib/api';
import dynamic from 'next/dynamic';
import { motion, AnimatePresence } from 'framer-motion';

const MapPicker = dynamic(() => import('@/components/MapPicker'), {
  ssr: false,
  loading: () => (
    <div className="h-[300px] w-full bg-slate-900/50 rounded-xl flex items-center justify-center">
      <Loader2 className="w-6 h-6 animate-spin text-slate-500" />
    </div>
  ),
});

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState('identity');
  const [isSuccess, setIsSuccess] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Sub-tab inside classifications_sop tab: 'classifications' | 'sop'
  const [classSopActiveTab, setClassSopActiveTab] = useState<'classifications' | 'sop'>('classifications');

  // SOP States
  const [sopSearchQuery, setSopSearchQuery] = useState('');
  const [sopFilterType, setSopFilterType] = useState('ALL');
  const [sopTitle, setSopTitle] = useState('');
  const [sopDocType, setSopDocType] = useState('SOP');
  const [sopFile, setSopFile] = useState<File | null>(null);
  const [sopIsGlobal, setSopIsGlobal] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [vectorizingDocId, setVectorizingDocId] = useState<number | null>(null);
  const [successMessage, setSuccessMessage] = useState('');
  const queryClient = useQueryClient();

  const [isBackingUp, setIsBackingUp] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);
  const [isSettingUpWebhook, setIsSettingUpWebhook] = useState(false);
  const [webhookBaseUrl, setWebhookBaseUrl] = useState('');
  const [selectedBackupFile, setSelectedBackupFile] = useState<File | null>(null);

  const [userRole, setUserRole] = useState<string | null>(null);
  const [tenantSlug, setTenantSlug] = useState<string | null>(null);

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

  const cleanRole = userRole ? String(userRole).toLowerCase().replace(/[\s_-]/g, '') : '';
  const isSuperAdmin = cleanRole === 'superadmin' || userRole === 'Super Admin';
  const isPusatOrGlobal = !tenantSlug || tenantSlug === 'pusat' || tenantSlug === 'global' || isSuperAdmin;

  useEffect(() => {
    if (userRole && userRole !== 'Super Admin' && (activeTab === 'ai' || activeTab === 'backup')) {
      setActiveTab('identity');
    }
    if (activeTab === 'classifications') {
      setActiveTab('classifications_sop');
    }
  }, [userRole, activeTab]);

  const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({});
  const togglePasswordVisibility = (key: string) => {
    setShowPasswords((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  // Modal States
  const [locationModalOpen, setLocationModalOpen] = useState(false);
  const [editingLocation, setEditingLocation] = useState<any>(null);
  const [locationForm, setLocationForm] = useState({
    name: '',
    type: 'Pos SAR',
    lat: 3.945,
    lng: 108.384,
    address: '',
    unsur: '',
    alut: '',
    icon: ''
  });

  const [classificationModalOpen, setClassificationModalOpen] = useState(false);
  const [editingClassification, setEditingClassification] = useState<any>(null);
  const [classificationForm, setClassificationForm] = useState({
    category: '',
    keywords: '',
    sop_document_id: null as number | null
  });

  const [userModalOpen, setUserModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<any>(null);
  const [userForm, setUserForm] = useState({
    name: '',
    email: '',
    phone: '',
    role: 'Operator',
    password: ''
  });

  const [widgetModalOpen, setWidgetModalOpen] = useState(false);
  const [editingWidget, setEditingWidget] = useState<any>(null);
  const [widgetForm, setWidgetForm] = useState({
    partner_name: '',
    website_url: '',
    official_email: '',
    official_phone: '',
    status: 'APPROVED'
  });

  // Test connection state
  const [testResult, setTestResult] = useState<{ status: 'idle' | 'testing' | 'success' | 'error'; message: string }>({
    status: 'idle',
    message: ''
  });
  const [cloudLlmModels, setCloudLlmModels] = useState<string[]>([]);
  const [cloudEmbedModels, setCloudEmbedModels] = useState<string[]>([]);
  const [cloudSttModels, setCloudSttModels] = useState<string[]>([]);

  // Query settings config
  const { data: settingsData, isLoading: isLoadingSettings } = useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
  });

  // Query identity
  const { data: identityData, isLoading: isLoadingIdentity } = useQuery({
    queryKey: ['identity'],
    queryFn: getIdentity,
  });

  // Query live status
  const { data: liveStatus, isLoading: isLoadingLiveStatus, refetch: refetchLiveStatus } = useQuery({
    queryKey: ['live-status'],
    queryFn: getLiveStatus,
    refetchInterval: 30000, // Sync status every 30s
  });

  // Query locations
  const { data: locationsData, isLoading: isLoadingLocations } = useQuery({
    queryKey: ['locations'],
    queryFn: getLocations,
  });

  // Query classifications
  const { data: classificationsData, isLoading: isLoadingClassifications } = useQuery({
    queryKey: ['classifications'],
    queryFn: getClassifications,
  });

  // Query SOP documents for relation in settings
  const { data: sopDocumentsData = [] } = useQuery({
    queryKey: ['sopDocuments'],
    queryFn: getSopDocuments,
  });

  // Query users
  const { data: usersData, isLoading: isLoadingUsers } = useQuery({
    queryKey: ['users'],
    queryFn: getUsers,
  });

  // Local Form state for main settings
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [identityForm, setIdentityForm] = useState({
    identitas_nama_instansi: '',
    identitas_motto: '',
    identitas_wilayah_kerja: '',
    identitas_kml_path: '',
    identitas_logo_path: ''
  });

  // Sync loaded configs into forms
  useEffect(() => {
    if (settingsData && Array.isArray(settingsData)) {
      const initialData: Record<string, string> = {};
      settingsData.forEach((item: any) => {
        initialData[item.key] = item.value || '';
      });
      setFormData(initialData);
    }
  }, [settingsData]);

  useEffect(() => {
    if (identityData) {
      setIdentityForm({
        identitas_nama_instansi: identityData.identitas_nama_instansi || '',
        identitas_motto: identityData.identitas_motto || '',
        identitas_wilayah_kerja: identityData.identitas_wilayah_kerja || '',
        identitas_kml_path: identityData.identitas_kml_path || '',
        identitas_logo_path: identityData.identitas_logo_path || ''
      });
    }
  }, [identityData]);

  // Query Ollama models dynamically if LLM or Embedding provider is Ollama
  const currentLlmProvider = formData.ai_llm_provider || 'ollama';
  const currentEmbedProvider = formData.ai_embed_provider || 'ollama';
  const currentLlmBaseUrl = formData.ai_llm_base_url || 'http://localhost:11434';
  const { data: ollamaModelsData } = useQuery({
    queryKey: ['ollama-models', currentLlmBaseUrl],
    queryFn: () => getOllamaModels(currentLlmBaseUrl),
    enabled: currentLlmProvider === 'ollama' || currentEmbedProvider === 'ollama',
  });

  // Mutations
  const updateSettingsMutation = useMutation({
    mutationFn: (data: { key: string; value: string }[]) => updateSettings(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      showSuccessToast('Pengaturan sistem berhasil disimpan!');
    },
  });

  const updateIdentityMutation = useMutation({
    mutationFn: (data: any) => updateIdentity(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['identity'] });
      showSuccessToast('Identitas kantor berhasil diperbarui!');
    },
  });

  const locationMutation = useMutation({
    mutationFn: (data: any) => {
      if (editingLocation) {
        return updateLocation(editingLocation.id, data);
      }
      return createLocation(data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['locations'] });
      setLocationModalOpen(false);
      setEditingLocation(null);
      showSuccessToast(editingLocation ? 'Lokasi berhasil diperbarui!' : 'Lokasi baru berhasil ditambahkan!');
    }
  });

  const deleteLocationMutation = useMutation({
    mutationFn: (id: number) => deleteLocation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['locations'] });
      showSuccessToast('Lokasi berhasil dihapus.');
    }
  });

  const classificationMutation = useMutation({
    mutationFn: (data: any) => {
      if (editingClassification) {
        return updateClassification(editingClassification.id, data);
      }
      return createClassification(data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['classifications'] });
      setClassificationModalOpen(false);
      setEditingClassification(null);
      showSuccessToast(editingClassification ? 'Klasifikasi diperbarui!' : 'Klasifikasi baru ditambahkan!');
    }
  });

  const deleteClassificationMutation = useMutation({
    mutationFn: (id: number) => deleteClassification(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['classifications'] });
      showSuccessToast('Klasifikasi berhasil dihapus.');
    }
  });

  // SOP Mutations
  const uploadSopMutation = useMutation({
    mutationFn: uploadSopDocument,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sopDocuments'] });
      setSopTitle('');
      setSopFile(null);
      setSopIsGlobal(false);
      setUploadError('');
      if (fileInputRef.current) fileInputRef.current.value = '';
      setUploadSuccess(true);
      setTimeout(() => setUploadSuccess(false), 4000);
    },
    onError: (error: any) => {
      const errMsg = error.response?.data?.detail || 'Gagal mengunggah file SOP.';
      setUploadError(errMsg);
    }
  });

  const vectorizeSopMutation = useMutation({
    mutationFn: ({ docId, isGlobal }: { docId: number; isGlobal: boolean }) => vectorizeSopDocument(docId, isGlobal),
    onSuccess: (data: any) => {
      queryClient.invalidateQueries({ queryKey: ['sopDocuments'] });
      setVectorizingDocId(null);
      alert(data.message || 'Dokumen berhasil diproses dan diindeks ke Vector Store!');
    },
    onError: (error: any) => {
      queryClient.invalidateQueries({ queryKey: ['sopDocuments'] });
      setVectorizingDocId(null);
      const errMsg = error.response?.data?.detail || 'Gagal memvektorkan dokumen.';
      alert(`Gagal Vektorasi: ${errMsg}`);
    }
  });

  const deleteSopMutation = useMutation({
    mutationFn: ({ docId, isGlobal }: { docId: number; isGlobal: boolean }) => deleteSopDocument(docId, isGlobal),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sopDocuments'] });
    },
    onError: (error: any) => {
      queryClient.invalidateQueries({ queryKey: ['sopDocuments'] });
      const errMsg = error.response?.data?.detail || 'Gagal menghapus dokumen SOP.';
      alert(`Gagal Menghapus: ${errMsg}`);
    }
  });

  // Drag & Drop Handlers for SOP
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      validateAndSetFile(file);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      validateAndSetFile(file);
    }
  };

  const validateAndSetFile = (file: File) => {
    setUploadError('');
    const allowedTypes = [
      'application/pdf',
      'text/plain',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/msword'
    ];
    const allowedExtensions = ['.pdf', '.txt', '.docx', '.doc'];
    const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();

    if (!allowedTypes.includes(file.type) && !allowedExtensions.includes(fileExt)) {
      setUploadError('Format file tidak didukung. Gunakan PDF, TXT, atau DOCX.');
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      setUploadError('Ukuran file melebihi batas 10MB.');
      return;
    }

    setSopFile(file);
    if (!sopTitle) {
      const baseName = file.name.substring(0, file.name.lastIndexOf('.')) || file.name;
      setSopTitle(baseName);
    }
  };

  const handleUploadSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!sopFile) {
      setUploadError('Pilih file terlebih dahulu.');
      return;
    }
    if (!sopTitle.trim()) {
      setUploadError('Masukkan judul dokumen.');
      return;
    }

    const formData = new FormData();
    formData.append('file', sopFile);
    formData.append('title', sopTitle.trim());
    formData.append('doc_type', sopDocType);
    formData.append('is_global', String(sopIsGlobal));

    uploadSopMutation.mutate(formData);
  };

  const handleTriggerVectorize = (docId: number, isGlobal: boolean) => {
    setVectorizingDocId(docId);
    vectorizeSopMutation.mutate({ docId, isGlobal });
  };

  const handleDeleteSop = (docId: number, title: string, isGlobal: boolean) => {
    if (window.confirm(`Apakah Anda yakin ingin menghapus dokumen SOP "${title}"? Tindakan ini tidak dapat dibatalkan.`)) {
      deleteSopMutation.mutate({ docId, isGlobal });
    }
  };

  // Helper Formats
  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '-';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('id-ID', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (e) {
      return dateStr;
    }
  };

  // Filter & Search Logic (SOP)
  const filteredSops = (sopDocumentsData || []).filter((item: any) => {
    const titleStr = (item.title || '').toLowerCase();
    const filenameStr = (item.filename || '').toLowerCase();
    const typeStr = item.doc_type || 'SOP';
    const searchLower = sopSearchQuery.toLowerCase();

    const matchesSearch = titleStr.includes(searchLower) || filenameStr.includes(searchLower);
    const matchesType = sopFilterType === 'ALL' ? true : typeStr.toUpperCase() === sopFilterType.toUpperCase();

    return matchesSearch && matchesType;
  });

  const userMutation = useMutation({
    mutationFn: (data: any) => {
      const payload = { ...data };
      if (editingUser) {
        if (!payload.password || !payload.password.trim()) {
          delete payload.password;
        }
        return updateUser(editingUser.id, payload);
      }
      return createUser(payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setUserModalOpen(false);
      setEditingUser(null);
      showSuccessToast(editingUser ? 'Data admin berhasil diperbarui!' : 'Administrator baru terdaftar!');
    }
  });

  const deleteUserMutation = useMutation({
    mutationFn: (id: number) => deleteUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      showSuccessToast('Pengguna berhasil dihapus.');
    }
  });

  const kmlUploadMutation = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append('file', file);
      return uploadIdentityKml(form);
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['identity'] });
      showSuccessToast('File batas KML berhasil diunggah!');
    }
  });

  const kmlDeleteMutation = useMutation({
    mutationFn: () => deleteIdentityKml(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['identity'] });
      showSuccessToast('File batas KML berhasil dihapus.');
    }
  });

  const logoUploadMutation = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append('file', file);
      return uploadIdentityLogo(form);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['identity'] });
      showSuccessToast('Logo berhasil diunggah!');
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Gagal mengunggah logo');
    }
  });

  const logoDeleteMutation = useMutation({
    mutationFn: () => deleteIdentityLogo(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['identity'] });
      showSuccessToast('Logo berhasil dihapus.');
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Gagal menghapus logo');
    }
  });

  const { data: widgetRequests = [] } = useQuery({
    queryKey: ['widgetRequests'],
    queryFn: getWidgetRequests,
    enabled: activeTab === 'widget'
  });

  const approveWidgetMutation = useMutation({
    mutationFn: (id: number) => approveWidgetRequest(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['widgetRequests'] });
      showSuccessToast('Pengajuan widget Lapor SAR berhasil disetujui.');
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Gagal menyetujui pengajuan');
    }
  });

  const rejectWidgetMutation = useMutation({
    mutationFn: (id: number) => rejectWidgetRequest(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['widgetRequests'] });
      showSuccessToast('Pengajuan widget Lapor SAR berhasil ditolak.');
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Gagal menolak pengajuan');
    }
  });

  const widgetMutation = useMutation({
    mutationFn: (data: any) => {
      if (editingWidget) {
        return updateWidgetRequest(editingWidget.id, data);
      }
      return createWidgetRequestAdmin(data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['widgetRequests'] });
      setWidgetModalOpen(false);
      setEditingWidget(null);
      showSuccessToast(editingWidget ? 'Data integrasi berhasil diperbarui!' : 'Integrasi widget baru berhasil didaftarkan!');
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Gagal menyimpan integrasi');
    }
  });

  const deleteWidgetMutation = useMutation({
    mutationFn: (id: number) => deleteWidgetRequest(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['widgetRequests'] });
      showSuccessToast('Integrasi widget berhasil dihapus.');
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Gagal menghapus integrasi');
    }
  });

  const openAddWidget = () => {
    setWidgetForm({
      partner_name: '',
      website_url: '',
      official_email: '',
      official_phone: '',
      status: 'APPROVED'
    });
    setEditingWidget(null);
    setWidgetModalOpen(true);
  };

  const openEditWidget = (req: any) => {
    setEditingWidget(req);
    setWidgetForm({
      partner_name: req.partner_name,
      website_url: req.website_url,
      official_email: req.official_email,
      official_phone: req.official_phone,
      status: req.status
    });
    setWidgetModalOpen(true);
  };

  const showSuccessToast = (message: string) => {
    setSuccessMessage(message);
    setIsSuccess(true);
    setTimeout(() => setIsSuccess(false), 3500);
  };

  const handleConfigChange = (key: string, value: string) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
    if (key === 'ai_llm_provider') {
      setCloudLlmModels([]);
      setFormData((prev) => ({ ...prev, ai_llm_model: '' }));
    } else if (key === 'ai_embed_provider') {
      setCloudEmbedModels([]);
      setFormData((prev) => ({ ...prev, ai_embed_model: '' }));
    } else if (key === 'ai_stt_provider') {
      setCloudSttModels([]);
      setFormData((prev) => ({ ...prev, ai_stt_model: '' }));
    }
  };

  const handleSaveMainConfigs = () => {
    const payload = Object.entries(formData).map(([key, value]) => ({ key, value }));
    updateSettingsMutation.mutate(payload);
  };

  const handleSetupTelegramWebhook = async () => {
    setIsSettingUpWebhook(true);
    try {
      const res = await setupTelegramWebhook(webhookBaseUrl);
      if (res.status === 'success') {
        showSuccessToast('Webhook Telegram berhasil terhubung!');
      } else {
        alert(`Gagal menghubungkan webhook: ${res.message || 'Error tidak dikenal'}`);
      }
    } catch (err: any) {
      alert(`Terjadi kesalahan: ${err.response?.data?.detail || err.message || 'Gagal menghubungi server'}`);
    } finally {
      setIsSettingUpWebhook(false);
      refetchLiveStatus();
    }
  };

  const handleSaveIdentity = () => {
    updateIdentityMutation.mutate(identityForm);
  };

  // Test AI Connection logic
  const handleTestAiConnection = async (type: 'llm' | 'embed' | 'stt') => {
    setTestResult({ status: 'testing', message: `Mencoba terhubung ke engine ${type.toUpperCase()}...` });
    const provider = formData[`ai_${type}_provider`] || 'ollama';
    let apiKey = formData[`ai_${type}_api_key`] || '';

    // Auto-fallback to LLM API key if provider matches and key is empty
    if (!apiKey && (type === 'embed' || type === 'stt')) {
      if (provider === formData.ai_llm_provider || ['gemini', 'openai', 'groq'].includes(provider)) {
        apiKey = formData.ai_llm_api_key || '';
      }
    }

    const baseUrl = provider === 'ollama'
      ? (formData.ai_llm_base_url || 'http://localhost:11434')
      : type === 'stt'
      ? (formData.ai_stt_base_url || 'http://localhost:8002')
      : '';

    try {
      const res = await testAiConnection({ provider, api_key: apiKey, base_url: baseUrl, engine_type: type });
      if (res.connected) {
        setTestResult({
          status: 'success',
          message: `Koneksi Berhasil! Provider ${provider.toUpperCase()} (${type.toUpperCase()}) merespon dengan baik. Model terdeteksi: ${res.models?.join(', ') || 'N/A'}`
        });
        if (res.models && res.models.length > 0) {
          if (type === 'llm') {
            setCloudLlmModels(res.models);
          } else if (type === 'embed') {
            setCloudEmbedModels(res.models);
          } else if (type === 'stt') {
            setCloudSttModels(res.models);
          }
        } else if (provider === 'claude' && type === 'llm') {
          setCloudLlmModels(['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', 'claude-3-opus-20240229']);
        }
      } else {
        setTestResult({
          status: 'error',
          message: `Gagal tersambung: ${res.message || 'Error tidak dikenal'}`
        });
      }
    } catch (err: any) {
      setTestResult({
        status: 'error',
        message: `Terjadi kesalahan jaringan: ${err.message || 'Gagal menghubungi backend'}`
      });
    }
  };

  // Backup & Restore handlers
  const handleDownloadBackup = async () => {
    setIsBackingUp(true);
    try {
      const blob = await exportDatabaseBackup();
      const url = window.URL.createObjectURL(new Blob([blob]));
      const link = document.createElement('a');
      link.href = url;
      
      const timestamp = new Date().toISOString().slice(0, 19).replace(/[-T:]/g, '_');
      link.setAttribute('download', `laporsar_backup_${timestamp}.zip`);
      
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      showSuccessToast('Ekspor cadangan database sukses!');
    } catch (err: any) {
      alert(`Gagal mengekspor backup: ${err.message || err}`);
    } finally {
      setIsBackingUp(false);
    }
  };

  const handleRestoreDatabase = async (file: File) => {
    if (!confirm("⚠️ PERINGATAN BAHAYA!\n\nProses pemulihan (restore) akan MENGHAPUS dan MENIMPA seluruh data Pos/Unit SAR, Klasifikasi, Kamus Jargon, Kontak, dan Laporan yang ada saat ini dengan data cadangan.\n\nApakah Anda yakin ingin melanjutkan restorasi?")) {
      return;
    }
    setIsRestoring(true);
    try {
      const res = await importDatabaseRestore(file);
      if (res.status === 'success') {
        showSuccessToast('Pemulihan database sukses penuh!');
        // Invalidate all queries to reload settings, locations, etc.
        queryClient.invalidateQueries();
        setSelectedBackupFile(null);
      } else {
        alert(`Gagal: ${res.message}`);
      }
    } catch (err: any) {
      alert(`Gagal memulihkan database: ${err.response?.data?.detail || err.message || err}`);
    } finally {
      setIsRestoring(false);
    }
  };

  // Form handlers for modals
  const openAddLocation = () => {
    setLocationForm({
      name: '',
      type: 'Pos SAR',
      lat: 3.945,
      lng: 108.384,
      address: '',
      unsur: '',
      alut: '',
      icon: '🏠'
    });
    setEditingLocation(null);
    setLocationModalOpen(true);
  };

  const openEditLocation = (loc: any) => {
    setEditingLocation(loc);
    setLocationForm({
      name: loc.name,
      type: loc.type,
      lat: loc.lat,
      lng: loc.lng,
      address: loc.address || '',
      unsur: loc.unsur || '',
      alut: loc.alut || '',
      icon: loc.icon || ''
    });
    setLocationModalOpen(true);
  };

  const openAddClassification = () => {
    setClassificationForm({ category: '', keywords: '', sop_document_id: null });
    setEditingClassification(null);
    setClassificationModalOpen(true);
  };

  const openEditClassification = (cls: any) => {
    setEditingClassification(cls);
    setClassificationForm({
      category: cls.category,
      keywords: cls.keywords || '',
      sop_document_id: cls.sop_document_id || null
    });
    setClassificationModalOpen(true);
  };

  const openAddUser = () => {
    setUserForm({ name: '', email: '', phone: '', role: 'Operator', password: '' });
    setEditingUser(null);
    setUserModalOpen(true);
  };

  const openEditUser = (usr: any) => {
    setEditingUser(usr);
    setUserForm({
      name: usr.name,
      email: usr.email,
      phone: usr.phone || '',
      role: usr.role,
      password: '' // Kept empty unless changing password
    });
    setUserModalOpen(true);
  };

  const tabCategories = [
    {
      title: 'Profil & Wilayah',
      items: [
        { id: 'identity', label: 'Identitas Kantor', icon: Building2 },
        { id: 'locations', label: 'Unit Pelaksana Teknis (UPT)', icon: MapPin },
      ]
    },
    {
      title: 'Mesin AI & RAG',
      items: [
        { id: 'classifications_sop', label: 'Klasifikasi & SOP RAG', icon: FileText },
        { id: 'ai', label: 'Konfigurasi Model AI', icon: Settings2 },
        { id: 'chatbot', label: 'Koneksi Chatbot', icon: MessageSquare },
        { id: 'widget', label: 'Widget Lapor SAR', icon: Key },
      ]
    },
    {
      title: 'Administrasi',
      items: [
        { id: 'users', label: 'Manajemen Pengguna', icon: Users },
        { id: 'backup', label: 'Cadangan Data', icon: Database },
      ]
    }
  ];

  const filteredTabCategories = tabCategories.map(category => {
    const items = category.items.filter(item => {
      if (userRole !== 'Super Admin' && (item.id === 'ai' || item.id === 'backup')) {
        return false;
      }
      return true;
    });
    return { ...category, items };
  }).filter(category => category.items.length > 0);

  return (
    <div className="space-y-6 w-full pb-16">
      {/* Toast Notification */}
      <AnimatePresence>
        {isSuccess && (
          <motion.div
            initial={{ opacity: 0, y: -50, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -20, scale: 0.9 }}
            className="fixed top-6 right-6 z-50 bg-emerald-600 text-white px-5 py-3 rounded-2xl shadow-xl flex items-center gap-3 border border-emerald-500"
          >
            <CheckCircle2 className="w-5 h-5" />
            <span className="font-semibold text-sm">{successMessage}</span>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight flex items-center gap-2">
            Pusat Pengaturan Sistem
          </h1>
          <p className="text-gray-500 mt-1">Konfigurasi dual-chatbot, koordinat wilayah operasional, klasifikasi, dan parameter RAG.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Navigation Sidebar */}
        <div className="lg:col-span-1 space-y-4">
          <div className="bg-white/80 backdrop-blur-md p-3.5 rounded-3xl border border-gray-100 shadow-sm space-y-4">
            {filteredTabCategories.map((category) => (
              <div key={category.title} className="space-y-1">
                <div className="px-3 py-1 text-[10px] font-extrabold text-gray-400 uppercase tracking-widest">{category.title}</div>
                {category.items.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => {
                      setActiveTab(tab.id);
                      setTestResult({ status: 'idle', message: '' });
                    }}
                    className={`w-full flex items-center gap-3 px-4 py-2.5 text-xs font-bold rounded-xl text-left transition-all duration-300 ${
                      activeTab === tab.id
                        ? 'bg-slate-900 text-white shadow-sm'
                        : 'text-gray-600 hover:bg-slate-100 hover:text-slate-900'
                    }`}
                  >
                    <tab.icon className={`w-4 h-4 transition-transform duration-300 ${activeTab === tab.id ? 'scale-110' : ''}`} />
                    {tab.label}
                  </button>
                ))}
              </div>
            ))}
          </div>

          {/* Quick System Badge */}
          <div className="bg-white/80 backdrop-blur-md p-5 rounded-3xl text-slate-700 shadow-sm border border-slate-100 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">Live Health Status</h3>
            <div className="space-y-2.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-600 flex items-center gap-1.5 font-medium"><Server className="w-3.5 h-3.5 text-slate-400" /> AI Engine (RAG)</span>
                <span className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                  liveStatus?.ollama?.connected ? 'bg-emerald-50 text-emerald-700 border border-emerald-200/50' : 'bg-rose-50 text-rose-700 border border-rose-200/50'
                }`}>
                  {liveStatus?.ollama?.connected ? 'Online' : 'Offline'}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-600 flex items-center gap-1.5 font-medium"><Radio className="w-3.5 h-3.5 text-slate-400" /> Telegram Bot</span>
                <span className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                  liveStatus?.telegram?.connected ? 'bg-emerald-50 text-emerald-700 border border-emerald-200/50' : 'bg-rose-50 text-rose-700 border border-rose-200/50'
                }`}>
                  {liveStatus?.telegram?.connected ? 'Online' : 'Offline'}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-600 flex items-center gap-1.5 font-medium"><MessageSquare className="w-3.5 h-3.5 text-slate-400" /> WhatsApp</span>
                <span className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                  liveStatus?.whatsapp?.connected ? 'bg-emerald-50 text-emerald-700 border border-emerald-200/50' : 'bg-rose-50 text-rose-700 border border-rose-200/50'
                }`}>
                  {liveStatus?.whatsapp?.connected ? 'Online' : 'Offline'}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-600 flex items-center gap-1.5 font-medium"><Radio className="w-3.5 h-3.5 text-slate-400" /> Whisper (STT)</span>
                <span className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                  liveStatus?.whisper?.connected ? 'bg-emerald-50 text-emerald-700 border border-emerald-200/50' : 'bg-rose-50 text-rose-700 border border-rose-200/50'
                }`}
                title={liveStatus?.whisper?.error || `${liveStatus?.whisper?.provider} (${liveStatus?.whisper?.model})`}
                >
                  {liveStatus?.whisper?.connected ? 'Online' : 'Offline'}
                </span>
              </div>
            </div>
            <button 
              onClick={() => refetchLiveStatus()} 
              disabled={isLoadingLiveStatus}
              className="w-full mt-2 py-2 bg-slate-50 hover:bg-slate-100 active:scale-95 text-slate-700 hover:text-slate-900 text-xs font-semibold rounded-xl flex items-center justify-center gap-2 transition-all border border-slate-200/80"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-slate-500 ${isLoadingLiveStatus ? 'animate-spin' : ''}`} />
              Segarkan Status
            </button>
          </div>
        </div>

        {/* Content Panel Area */}
        <div className="lg:col-span-3 space-y-6">
          <div className="bg-white rounded-3xl border border-gray-100 shadow-sm overflow-hidden min-h-[500px]">
            
            {/* TAB 1: IDENTITAS & WILAYAH KERJA */}
            {activeTab === 'identity' && (
              <div className="p-6 md:p-8 space-y-6">
                <div className="border-b border-gray-100 pb-5">
                  <h2 className="text-xl font-bold text-gray-900">Identitas & Wilayah Operasional</h2>
                  <p className="text-sm text-gray-500 mt-1">Branding Kantor SAR dan file batas wilayah koordinat (.KML) untuk overlay peta pelaporan.</p>
                </div>

                {isLoadingIdentity ? (
                  <div className="py-20 flex justify-center"><Loader2 className="w-8 h-8 animate-spin text-slate-500" /></div>
                ) : (
                  <div className="space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="md:col-span-2">
                        <label className="block text-sm font-semibold text-gray-700 mb-1.5">Nama Instansi / Kantor</label>
                        <input
                          type="text"
                          value={identityForm.identitas_nama_instansi}
                          onChange={(e) => setIdentityForm({ ...identityForm, identitas_nama_instansi: e.target.value })}
                          placeholder="Kantor Pencarian dan Pertolongan Natuna"
                          className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-2xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                        />
                      </div>
                      <div className="md:col-span-2">
                        <label className="block text-sm font-semibold text-gray-700 mb-1.5">Slogan / Motto Kantor</label>
                        <textarea
                          rows={2}
                          value={identityForm.identitas_motto}
                          onChange={(e) => setIdentityForm({ ...identityForm, identitas_motto: e.target.value })}
                          placeholder="We Are Family - Profesional, Modern, Teruji"
                          className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-2xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none resize-none"
                        />
                      </div>
                      <div className="md:col-span-2">
                        <label className="block text-sm font-semibold text-gray-700 mb-1.5">Cakupan Wilayah Kerja</label>
                        <input
                          type="text"
                          value={identityForm.identitas_wilayah_kerja}
                          onChange={(e) => setIdentityForm({ ...identityForm, identitas_wilayah_kerja: e.target.value })}
                          placeholder="Kabupaten Natuna, Kepulauan Riau, Indonesia"
                          className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-2xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                        />
                      </div>
                    </div>

                    {/* KML File Uploader */}
                    <div className="border border-dashed border-gray-200 rounded-3xl p-6 bg-gray-50/50 space-y-4">
                      <div className="flex items-start gap-4">
                        <div className="w-12 h-12 bg-slate-100 rounded-2xl flex items-center justify-center text-slate-800 flex-shrink-0">
                          <FileText className="w-6 h-6" />
                        </div>
                        <div>
                          <h4 className="text-sm font-bold text-gray-900">Peta Batas Wilayah Kerja (KML/KMZ)</h4>
                          <p className="text-xs text-gray-500 mt-0.5">Unggah file batas KML agar dashboard peta otomatis menampilkan koordinat batas wilayah hukum Kantor SAR Anda.</p>
                        </div>
                      </div>

                      {identityForm.identitas_kml_path ? (
                        <div className="bg-slate-100 border border-slate-200 p-4 rounded-2xl flex items-center justify-between">
                          <div className="flex items-center gap-2.5">
                            <Check className="w-4 h-4 text-slate-800 font-bold" />
                            <span className="text-xs font-semibold text-gray-700 truncate max-w-[280px]">
                              {identityForm.identitas_kml_path.split('/').pop()}
                            </span>
                          </div>
                          <button
                            onClick={() => kmlDeleteMutation.mutate()}
                            disabled={kmlDeleteMutation.isPending}
                            className="px-3 py-1.5 bg-rose-100 hover:bg-rose-200 text-rose-700 text-xs font-semibold rounded-xl transition-all"
                          >
                            Hapus File
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-3">
                          <input
                            type="file"
                            accept=".kml,.kmz"
                            id="kml-upload"
                            className="hidden"
                            onChange={(e) => {
                              const file = e.target.files?.[0];
                              if (file) kmlUploadMutation.mutate(file);
                            }}
                          />
                          <label
                            htmlFor="kml-upload"
                            className="px-4 py-2.5 bg-white border border-gray-200 text-gray-700 hover:bg-gray-50 font-bold text-xs rounded-xl shadow-sm cursor-pointer transition-all flex items-center gap-2"
                          >
                            {kmlUploadMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin text-slate-500" /> : <Plus className="w-4 h-4" />}
                            Pilih & Unggah File KML
                          </label>
                        </div>
                      )}
                    </div>

                    {/* Logo Instansi Uploader */}
                    <div className="border border-dashed border-gray-200 rounded-3xl p-6 bg-gray-50/50 space-y-4">
                      <div className="flex items-start gap-4">
                        <div className="w-12 h-12 bg-slate-100 rounded-2xl flex items-center justify-center text-slate-800 flex-shrink-0">
                          <Building2 className="w-6 h-6" />
                        </div>
                        <div>
                          <h4 className="text-sm font-bold text-gray-900">Logo Instansi / Kantor SAR</h4>
                          <p className="text-xs text-gray-500 mt-0.5">Unggah gambar logo kantor SAR Anda (format PNG, JPG, JPEG maks 2MB). Logo ini akan muncul di sidebar kiri utama.</p>
                        </div>
                      </div>

                      {identityForm.identitas_logo_path ? (
                        <div className="bg-slate-100 border border-slate-200 p-4 rounded-2xl flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <img 
                              src={`${getBackendUrl().replace(/\/api\/?$/, '')}/${identityForm.identitas_logo_path}`} 
                              alt="Logo Kantor" 
                              className="w-12 h-12 object-contain bg-white rounded-xl border border-slate-200 p-1" 
                            />
                            <div className="flex flex-col">
                              <span className="text-xs font-semibold text-gray-700">Logo Kustom Aktif</span>
                              <span className="text-[10px] text-gray-400 truncate max-w-[200px]">
                                {identityForm.identitas_logo_path.split('/').pop()}
                              </span>
                            </div>
                          </div>
                          <button
                            onClick={() => logoDeleteMutation.mutate()}
                            disabled={logoDeleteMutation.isPending}
                            className="px-3 py-1.5 bg-rose-100 hover:bg-rose-200 text-rose-700 text-xs font-semibold rounded-xl transition-all"
                          >
                            Hapus Logo
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-3">
                          <input
                            type="file"
                            accept="image/png, image/jpeg, image/jpg"
                            id="logo-upload"
                            className="hidden"
                            onChange={(e) => {
                              const file = e.target.files?.[0];
                              if (file) logoUploadMutation.mutate(file);
                            }}
                          />
                          <label
                            htmlFor="logo-upload"
                            className="px-4 py-2.5 bg-white border border-gray-200 text-gray-700 hover:bg-gray-50 font-bold text-xs rounded-xl shadow-sm cursor-pointer transition-all flex items-center gap-2"
                          >
                            {logoUploadMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin text-slate-500" /> : <Plus className="w-4 h-4" />}
                            Pilih & Unggah Logo Kantor
                          </label>
                        </div>
                      )}
                    </div>

                    <div className="flex justify-end pt-4">
                      <button
                        onClick={handleSaveIdentity}
                        disabled={updateIdentityMutation.isPending}
                        className="px-6 py-3 bg-slate-900 hover:bg-slate-800 text-white font-bold text-sm rounded-2xl hover:opacity-90 transition-all flex items-center gap-2 shadow-lg shadow-sm active:scale-95"
                      >
                        {updateIdentityMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                        Simpan Identitas Kantor
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: POS & UNIT SAR (CRUD + MapPicker!) */}
            {activeTab === 'locations' && (
              <div className="p-6 md:p-8 space-y-6">
                <div className="flex items-center justify-between border-b border-gray-100 pb-5">
                  <div>
                    <h2 className="text-xl font-bold text-gray-900">Unit Pelaksana Teknis (UPT SAR)</h2>
                    <p className="text-sm text-gray-500 mt-1">Daftar Kantor, Pos SAR, Pos AL, dan aset terdekat beserta Alut/Personil.</p>
                  </div>
                  <button
                    onClick={openAddLocation}
                    className="px-4 py-2.5 bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs rounded-xl flex items-center gap-2 transition-all shadow-md active:scale-95"
                  >
                    <Plus className="w-4 h-4" /> Tambah Pos/Unit
                  </button>
                </div>

                {isLoadingLocations ? (
                  <div className="py-20 flex justify-center"><Loader2 className="w-8 h-8 animate-spin text-slate-500" /></div>
                ) : !locationsData || locationsData.length === 0 ? (
                  <div className="text-center py-16 space-y-3">
                    <MapPin className="w-12 h-12 text-gray-300 mx-auto" />
                    <p className="text-sm font-semibold text-gray-500">Belum ada Pos atau Unit SAR terdaftar.</p>
                    <p className="text-xs text-gray-400">Tambahkan pos wilayah agar sistem RAG dapat menghitung heading & estimasi jarak kejadian terdekat.</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {locationsData.map((loc: any) => (
                      <div key={loc.id} className="p-5 border border-gray-100 hover:border-slate-200 hover:bg-slate-100/10 rounded-2xl transition-all flex flex-col justify-between space-y-4">
                        <div>
                          <div className="flex items-center justify-between">
                            <span className="px-2.5 py-1 bg-gray-100 text-gray-700 text-[10px] font-extrabold rounded-md uppercase flex items-center gap-1.5">
                              <span className="text-sm flex items-center">
                                {loc.icon && (loc.icon.startsWith('uploads/') || loc.icon.startsWith('http')) ? (
                                  <img 
                                    src={`${loc.icon.startsWith('http') ? '' : getBackendUrl() + '/'}${loc.icon}`} 
                                    alt="icon" 
                                    className="w-5 h-5 rounded-full object-cover" 
                                  />
                                ) : (
                                  loc.icon || (loc.type === 'Kantor SAR' ? '🏢' : loc.type === 'Pos SAR' ? '🏠' : '🛡️')
                                )}
                              </span>
                              <span>{loc.type}</span>
                            </span>
                            <div className="flex gap-1.5">
                              <button
                                onClick={() => openEditLocation(loc)}
                                className="p-1.5 hover:bg-gray-100 rounded-lg text-gray-500 hover:text-slate-900 transition-all"
                              >
                                <Edit2 className="w-4 h-4" />
                              </button>
                              <button
                                onClick={() => {
                                  if (confirm(`Apakah Anda yakin ingin menghapus ${loc.name}?`)) {
                                    deleteLocationMutation.mutate(loc.id);
                                  }
                                }}
                                className="p-1.5 hover:bg-gray-100 rounded-lg text-gray-500 hover:text-rose-600 transition-all"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </div>
                          <h3 className="font-bold text-gray-900 mt-2 text-sm md:text-base">{loc.name}</h3>
                          <p className="text-xs text-gray-400 flex items-center gap-1 mt-1"><MapPin className="w-3.5 h-3.5 flex-shrink-0 text-slate-500" /> {loc.address || 'Alamat tidak terisi'}</p>
                        </div>

                        <div className="border-t border-gray-100 pt-3 flex flex-wrap gap-2 text-[10px] text-gray-500">
                          {loc.unsur && (
                            <span className="px-2 py-0.5 bg-slate-50 border border-slate-100 rounded-md font-medium truncate max-w-[140px]">
                              👥 {loc.unsur}
                            </span>
                          )}
                          {loc.alut && (
                            <span className="px-2 py-0.5 bg-slate-50 border border-slate-100 rounded-md font-medium truncate max-w-[140px]">
                              ⛴️ {loc.alut}
                            </span>
                          )}
                          <span className="ml-auto font-mono text-[9px] text-gray-400 bg-gray-50 px-1.5 py-0.5 rounded">
                            {loc.lat.toFixed(4)}, {loc.lng.toFixed(4)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* TAB 4: KLASIFIKASI KEJADIAN & SOP RAG */}
            {activeTab === 'classifications_sop' && (
              <div className="space-y-0">
                {/* Visual sub-tabs inside Tab panel */}
                <div className="flex border-b border-gray-100 px-6 pt-5 bg-gray-50/20">
                  <button
                    onClick={() => setClassSopActiveTab('classifications')}
                    className={`pb-3 px-4 font-bold text-xs tracking-wide transition-all relative flex items-center gap-1.5 ${
                      classSopActiveTab === 'classifications'
                        ? 'text-slate-800'
                        : 'text-gray-400 hover:text-gray-600'
                    }`}
                  >
                    <FileText className="w-4 h-4" />
                    <span>1. Klasifikasi Kejadian</span>
                    {classSopActiveTab === 'classifications' && (
                      <motion.div
                        layoutId="classSopActiveTabUnderline"
                        className="absolute bottom-0 left-0 right-0 h-0.5 bg-slate-900"
                      />
                    )}
                  </button>
                  <button
                    onClick={() => setClassSopActiveTab('sop')}
                    className={`pb-3 px-4 font-bold text-xs tracking-wide transition-all relative flex items-center gap-1.5 ${
                      classSopActiveTab === 'sop'
                        ? 'text-slate-800'
                        : 'text-gray-400 hover:text-gray-600'
                    }`}
                  >
                    <UploadCloud className="w-4 h-4" />
                    <span>2. Dokumen SOP RAG</span>
                    {classSopActiveTab === 'sop' && (
                      <motion.div
                        layoutId="classSopActiveTabUnderline"
                        className="absolute bottom-0 left-0 right-0 h-0.5 bg-slate-900"
                      />
                    )}
                  </button>
                </div>

                <AnimatePresence mode="wait">
                  {classSopActiveTab === 'classifications' ? (
                    <motion.div
                      key="classifications-subtab"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      transition={{ duration: 0.15 }}
                      className="p-6 md:p-8 space-y-6"
                    >
                      <div className="flex items-center justify-between border-b border-gray-100 pb-5">
                        <div>
                          <h2 className="text-lg font-bold text-gray-900">Klasifikasi & Kata Kunci Kejadian</h2>
                          <p className="text-xs text-gray-500 mt-1">Kelola jenis musibah/bencana dan daftar kata kunci penentu deteksi klasifikasi otomatis.</p>
                        </div>
                        <button
                          onClick={openAddClassification}
                          className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs rounded-xl flex items-center gap-2 transition-all shadow-md active:scale-95"
                        >
                          <Plus className="w-4 h-4" /> Tambah Klasifikasi
                        </button>
                      </div>

                      {isLoadingClassifications ? (
                        <div className="py-20 flex justify-center"><Loader2 className="w-8 h-8 animate-spin text-slate-500" /></div>
                      ) : !classificationsData || classificationsData.length === 0 ? (
                        <div className="text-center py-16 space-y-3">
                          <FileText className="w-12 h-12 text-gray-300 mx-auto" />
                          <p className="text-sm font-semibold text-gray-500">Belum ada klasifikasi terdaftar.</p>
                        </div>
                      ) : (
                        <div className="space-y-3">
                          {classificationsData.map((cls: any) => (
                            <div key={cls.id} className="p-4 border border-gray-100 rounded-2xl hover:border-gray-250 hover:bg-gray-50/10 transition-all flex items-start justify-between gap-4">
                              <div className="space-y-1.5 flex-grow">
                                <h3 className="font-bold text-gray-900 text-sm md:text-base">{cls.category}</h3>
                                {cls.sop_document_id && (
                                  <div className="flex items-center gap-1.5 text-xs text-slate-500 font-medium">
                                    <FileText className="w-3.5 h-3.5 text-slate-400" />
                                    <span>SOP: <span className="text-slate-800 font-semibold">{sopDocumentsData.find((d: any) => d.id === cls.sop_document_id)?.title || `Dokumen SOP #${cls.sop_document_id}`}</span></span>
                                  </div>
                                )}
                                <div className="flex flex-wrap gap-1">
                                  {cls.keywords?.split(',').map((kw: string, i: number) => (
                                    <span key={i} className="px-2 py-0.5 bg-slate-100 border border-slate-200/50 text-slate-800 text-[10px] font-semibold rounded-md">
                                      {kw.trim()}
                                    </span>
                                  ))}
                                </div>
                              </div>
                              <div className="flex gap-1.5 flex-shrink-0">
                                <button
                                  onClick={() => openEditClassification(cls)}
                                  className="p-1.5 hover:bg-gray-50 rounded-xl text-gray-500 hover:text-slate-900 transition-all"
                                >
                                  <Edit2 className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  onClick={() => {
                                    if (confirm(`Apakah Anda yakin ingin menghapus klasifikasi ${cls.category}?`)) {
                                      deleteClassificationMutation.mutate(cls.id);
                                    }
                                  }}
                                  className="p-1.5 hover:bg-gray-50 rounded-xl text-gray-500 hover:text-rose-600 transition-all"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </motion.div>
                  ) : (
                    <motion.div
                      key="sop-subtab"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      transition={{ duration: 0.15 }}
                      className="p-6 md:p-8 space-y-6"
                    >
                      <div className="border-b border-gray-100 pb-5">
                        <h2 className="text-lg font-bold text-gray-900">Dokumen SOP & Regulasi (RAG)</h2>
                        <p className="text-xs text-gray-500 mt-1">Unggah panduan taktis, peraturan Basarnas, dan dokumen SOP untuk diindeks ke Vector Database RAG.</p>
                      </div>

                      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
                        {/* UPLOAD FORM CARD (LEFT COLUMN) */}
                        <div className="bg-white rounded-2xl border border-gray-150 shadow-sm p-5 space-y-4 lg:col-span-1">
                          <div className="flex items-center gap-2 pb-3 border-b border-gray-100">
                            <div className="p-2 bg-slate-100 rounded-xl text-slate-800">
                              <UploadCloud className="w-5 h-5" />
                            </div>
                            <div>
                              <h3 className="font-bold text-gray-800 text-xs">Unggah SOP Baru</h3>
                              <p className="text-[9px] text-gray-400 font-medium">Index file PDF, TXT, atau DOCX</p>
                            </div>
                          </div>

                          {uploadError && (
                            <div className="p-3 bg-red-50 text-red-700 border border-red-100 rounded-xl text-xs font-semibold flex items-start gap-2">
                              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                              <span>{uploadError}</span>
                            </div>
                          )}

                          {uploadSuccess && (
                            <div className="p-3 bg-green-50 text-green-700 border border-green-100 rounded-xl text-xs font-semibold flex items-center gap-2">
                              <CheckCircle2 className="w-4 h-4 shrink-0 text-green-600" />
                              <span>File berhasil diunggah!</span>
                            </div>
                          )}

                          <form onSubmit={handleUploadSubmit} className="space-y-4">
                            <div className="space-y-1.5">
                              <label className="block text-[10px] font-bold text-gray-700">Nama/Judul Dokumen</label>
                              <input
                                type="text"
                                required
                                value={sopTitle}
                                onChange={(e) => setSopTitle(e.target.value)}
                                placeholder="Contoh: SOP Penyelamatan Laut B"
                                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 focus:bg-white outline-none text-gray-800 font-semibold"
                              />
                            </div>

                            <div className="space-y-1.5">
                              <label className="block text-[10px] font-bold text-gray-700">Jenis / Kategori</label>
                              <select
                                value={sopDocType}
                                onChange={(e) => setSopDocType(e.target.value)}
                                className="w-full px-2.5 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 focus:bg-white outline-none text-gray-800 font-semibold"
                              >
                                <option value="SOP">SOP / PROSEDUR KERJA</option>
                                <option value="PANDUAN">PANDUAN TAKTIS</option>
                                <option value="REFERENSI">MATERI REFERENSI</option>
                                <option value="REGULASI">REGULASI & KEBIJAKAN</option>
                              </select>
                            </div>

                            {isPusatOrGlobal && (
                              <div className="p-2.5 bg-blue-50/50 border border-blue-100 rounded-2xl">
                                <label className="block text-[10px] font-bold text-gray-700 flex items-center gap-1.5 cursor-pointer">
                                  <input
                                    type="checkbox"
                                    checked={sopIsGlobal}
                                    onChange={(e) => setSopIsGlobal(e.target.checked)}
                                    className="w-3.5 h-3.5 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                                  />
                                  Jadikan SOP Dasar (Global)
                                </label>
                                <span className="text-[9px] text-gray-400 block leading-tight font-medium mt-1">
                                  Jika dicentang, dokumen ini akan diunggah ke repositori dasar nasional yang dapat dibaca seluruh UPT.
                                </span>
                              </div>
                            )}

                            {/* DRAG AND DROP ZONE */}
                            <div className="space-y-1.5">
                              <label className="block text-[10px] font-bold text-gray-700">File Dokumen</label>
                              <div
                                onDragOver={handleDragOver}
                                onDragLeave={handleDragLeave}
                                onDrop={handleDrop}
                                onClick={() => fileInputRef.current?.click()}
                                className={`border-2 border-dashed rounded-2xl p-4 text-center cursor-pointer transition-all flex flex-col items-center justify-center min-h-[120px] ${
                                  isDragging
                                    ? 'border-slate-900 bg-slate-100/50'
                                    : sopFile
                                    ? 'border-green-500 bg-green-50/20 hover:bg-green-50/30'
                                    : 'border-gray-200 hover:border-slate-400 hover:bg-gray-50'
                                }`}
                              >
                                <input
                                  type="file"
                                  ref={fileInputRef}
                                  onChange={handleFileChange}
                                  accept=".pdf,.txt,.docx,.doc"
                                  className="hidden"
                                />
                                {sopFile ? (
                                  <>
                                    <FileText className="w-8 h-8 text-green-600 mb-1.5" />
                                    <span className="text-[10px] font-bold text-gray-700 max-w-[150px] truncate block">
                                      {sopFile.name}
                                    </span>
                                    <span className="text-[9px] text-gray-400 font-semibold mt-0.5">
                                      {formatFileSize(sopFile.size)}
                                    </span>
                                    <button
                                      type="button"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        setSopFile(null);
                                        if (fileInputRef.current) fileInputRef.current.value = '';
                                      }}
                                      className="mt-2 text-[9px] text-red-500 hover:text-red-700 font-bold hover:underline"
                                    >
                                      Hapus File
                                    </button>
                                  </>
                                ) : (
                                  <>
                                    <UploadCloud className="w-8 h-8 text-gray-400 mb-1.5" />
                                    <span className="text-[10px] font-bold text-gray-600">
                                      Seret & Letakkan berkas
                                    </span>
                                    <span className="text-[9px] text-gray-400 mt-0.5">
                                      PDF, TXT, DOCX (Maks 10MB)
                                    </span>
                                  </>
                                )}
                              </div>
                            </div>

                            <button
                              type="submit"
                              disabled={uploadSopMutation.isPending || !sopFile}
                              className="w-full py-2.5 bg-slate-900 hover:bg-slate-800 text-white text-white font-bold text-xs rounded-xl shadow-md transition-all flex items-center justify-center gap-2 disabled:from-gray-300 disabled:to-gray-400 disabled:cursor-not-allowed active:scale-95"
                            >
                              {uploadSopMutation.isPending ? (
                                <>
                                  <Loader2 className="w-3.5 h-3.5 animate-spin" /> Mengunggah...
                                </>
                              ) : (
                                <>
                                  <ArrowUpCircle className="w-3.5 h-3.5" /> Unggah Dokumen
                                </>
                              )}
                            </button>
                          </form>
                        </div>

                        {/* SOP LIST & TABLE (RIGHT COLUMN) */}
                        <div className="bg-white rounded-2xl border border-gray-150 shadow-sm overflow-hidden lg:col-span-2 flex flex-col h-full min-h-[400px]">
                          {/* Table Filter Controls */}
                          <div className="p-3 border-b border-gray-100 flex flex-col sm:flex-row items-center gap-2 justify-between bg-gray-50/50">
                            <div className="relative flex-1 w-full max-w-xs">
                              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
                              <input 
                                type="text" 
                                placeholder="Cari nama dokumen SOP..." 
                                value={sopSearchQuery}
                                onChange={(e) => setSopSearchQuery(e.target.value)}
                                className="w-full pl-8 pr-3 py-1.5 bg-white border border-gray-200 rounded-xl text-[11px] focus:ring-2 focus:ring-slate-900/10 outline-none text-gray-700 font-medium"
                              />
                            </div>
                            <div className="flex items-center gap-1.5 w-full sm:w-auto overflow-x-auto">
                              <select
                                value={sopFilterType}
                                onChange={(e) => setSopFilterType(e.target.value)}
                                className="px-2 py-1.5 bg-white border border-gray-200 text-gray-700 text-[9px] font-bold rounded-xl outline-none"
                              >
                                <option value="ALL">SEMUA JENIS</option>
                                <option value="SOP">SOP</option>
                                <option value="PANDUAN">PANDUAN</option>
                                <option value="REFERENSI">REFERENSI</option>
                                <option value="REGULASI">REGULASI</option>
                              </select>
                            </div>
                          </div>

                          {/* SOP Table */}
                          <div className="overflow-x-auto flex-1">
                            <table className="w-full text-left border-collapse">
                              <thead>
                                <tr className="bg-gray-50/20">
                                  <th className="py-2.5 px-4 text-[9px] font-bold text-gray-500 uppercase tracking-wider border-b border-gray-100">Nama Dokumen</th>
                                  <th className="py-2.5 px-4 text-[9px] font-bold text-gray-500 uppercase tracking-wider border-b border-gray-100">Jenis</th>
                                  <th className="py-2.5 px-4 text-[9px] font-bold text-gray-500 uppercase tracking-wider border-b border-gray-100">Status RAG</th>
                                  <th className="py-2.5 px-4 text-[9px] font-bold text-gray-500 uppercase tracking-wider border-b border-gray-100 text-right">Aksi</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-gray-100">
                                {filteredSops.length === 0 ? (
                                  <tr>
                                    <td colSpan={4} className="py-8 text-center text-xs text-gray-400">
                                      Tidak ada dokumen SOP ditemukan.
                                    </td>
                                  </tr>
                                ) : (
                                  filteredSops.map((item: any) => (
                                    <tr key={item.id} className="hover:bg-gray-50/30 transition-colors">
                                      <td className="py-2.5 px-4 text-xs font-bold text-gray-900 leading-snug">
                                        <div className="flex flex-col">
                                          <div className="flex items-center gap-1.5 flex-wrap">
                                            <span className="truncate max-w-[150px]" title={item.title}>{item.title}</span>
                                            {item.is_global ? (
                                              <span className="inline-flex px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded text-[8px] font-bold border border-blue-100 uppercase tracking-wider scale-90">
                                                Pusat
                                              </span>
                                            ) : (
                                              <span className="inline-flex px-1.5 py-0.5 bg-emerald-50 text-emerald-600 rounded text-[8px] font-bold border border-emerald-100 uppercase tracking-wider scale-90">
                                                Lokal
                                              </span>
                                            )}
                                          </div>
                                          <span className="text-[9px] text-gray-400 font-semibold mt-0.5 flex items-center gap-1">
                                            <Calendar className="w-3 h-3 text-gray-300" />
                                            {formatDate(item.created_at)}
                                          </span>
                                        </div>
                                      </td>
                                      <td className="py-2.5 px-4">
                                        <span className={`inline-flex px-1.5 py-0.5 rounded text-[8px] font-bold tracking-wider ${
                                          item.doc_type === 'SOP'
                                            ? 'bg-slate-100 text-slate-800 border border-slate-200'
                                            : item.doc_type === 'PANDUAN'
                                            ? 'bg-blue-50 text-blue-700 border border-blue-100'
                                            : item.doc_type === 'REGULASI'
                                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-100'
                                            : 'bg-purple-50 text-purple-700 border border-purple-100'
                                        }`}>
                                          {item.doc_type || 'SOP'}
                                        </span>
                                      </td>
                                      <td className="py-2.5 px-4">
                                        {item.status === 'INDEXED' ? (
                                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-green-50 text-green-700 border border-green-100 rounded text-[8px] font-bold shadow-sm">
                                            <Check className="w-2.5 h-2.5 text-green-600 font-bold" /> RAG Aktif
                                          </span>
                                        ) : item.status === 'FAILED' ? (
                                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-red-50 text-red-700 border border-red-100 rounded text-[8px] font-bold shadow-sm">
                                            <AlertTriangle className="w-2.5 h-2.5 text-red-500" /> Gagal Vector
                                          </span>
                                        ) : (
                                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-gray-50 text-gray-500 border border-gray-150 rounded text-[8px] font-bold">
                                            <Info className="w-2.5 h-2.5 text-gray-400" /> Belum Vector
                                          </span>
                                        )}
                                      </td>
                                      <td className="py-2.5 px-4">
                                        <div className="flex items-center justify-end gap-1">
                                          {item.is_global && !isPusatOrGlobal ? (
                                            <span className="text-gray-400 flex items-center gap-1 text-[8px] font-bold px-1.5 py-0.5 bg-gray-50 border border-gray-100 rounded-lg animate-fade-in" title="SOP pusat bersifat Read-Only">
                                              <Lock className="w-2.5 h-2.5 text-gray-400" /> Terkunci (Pusat)
                                            </span>
                                          ) : (
                                            <>
                                              {item.status !== 'INDEXED' ? (
                                                <button
                                                  onClick={() => handleTriggerVectorize(item.id, item.is_global)}
                                                  disabled={vectorizingDocId === item.id}
                                                  className="px-2 py-0.5 bg-green-600 hover:bg-green-700 text-white font-bold text-[8px] rounded transition-all shadow-sm flex items-center gap-0.5 disabled:bg-gray-250"
                                                  title="Proses Vektor RAG"
                                                >
                                                  {vectorizingDocId === item.id ? (
                                                    <Loader2 className="w-2.5 h-2.5 animate-spin" />
                                                  ) : (
                                                    <>
                                                      <Cpu className="w-2.5 h-2.5" /> Vectorkan
                                                    </>
                                                  )}
                                                </button>
                                              ) : (
                                                <button
                                                  onClick={() => handleTriggerVectorize(item.id, item.is_global)}
                                                  disabled={vectorizingDocId === item.id}
                                                  className="px-2 py-0.5 bg-slate-100 hover:bg-slate-100 text-slate-800 border border-slate-200 font-bold text-[8px] rounded transition-all flex items-center gap-0.5"
                                                  title="Index Ulang Vector"
                                                >
                                                  {vectorizingDocId === item.id ? (
                                                    <Loader2 className="w-2.5 h-2.5 animate-spin" />
                                                  ) : (
                                                    <>
                                                      <Cpu className="w-2.5 h-2.5" /> Re-Vector
                                                    </>
                                                  )}
                                                </button>
                                              )}
                                              <button 
                                                onClick={() => handleDeleteSop(item.id, item.title, item.is_global)}
                                                disabled={vectorizingDocId === item.id}
                                                className="p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-all disabled:opacity-50"
                                                title="Hapus Dokumen"
                                              >
                                                <Trash2 className="w-3 h-3" />
                                              </button>
                                            </>
                                          )}
                                        </div>
                                      </td>
                                    </tr>
                                  ))
                                )}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )}

            {/* TAB 5: INTEGRASI CHATBOT & WEBHOOK */}
            {activeTab === 'chatbot' && (
              <div className="p-6 md:p-8 space-y-6">
                <div className="border-b border-gray-100 pb-5">
                  <h2 className="text-xl font-bold text-gray-900">Integrasi Webhook Chatbot</h2>
                  <p className="text-sm text-gray-500 mt-1">Konfigurasi API Token dan ID Grup Command Center untuk Telegram Bot dan Meta WhatsApp Cloud API.</p>
                </div>

                {isLoadingSettings ? (
                  <div className="py-20 flex justify-center"><Loader2 className="w-8 h-8 animate-spin text-slate-500" /></div>
                ) : (
                  <div className="space-y-6">
                    {/* Telegram Section */}
                    <div className="bg-gray-50/50 border border-gray-100 p-6 rounded-3xl space-y-4">
                      <h3 className="font-bold text-gray-900 text-sm md:text-base flex items-center gap-2 text-sky-600">
                        <MessageSquare className="w-5 h-5 text-sky-500" /> Telegram Bot Integration
                      </h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="md:col-span-2">
                          <label className="block text-xs font-bold text-gray-700 mb-1">Telegram Bot Token</label>
                          <div className="relative">
                            <input
                              type={showPasswords['telegram_token'] ? 'text' : 'password'}
                              value={formData.telegram_token || ''}
                              onChange={(e) => handleConfigChange('telegram_token', e.target.value)}
                              placeholder="Contoh: 1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ"
                              className="w-full pl-4 pr-10 py-3 bg-white border border-gray-200 rounded-xl text-xs font-mono focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                            />
                            <button
                              type="button"
                              onClick={() => togglePasswordVisibility('telegram_token')}
                              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors focus:outline-none"
                            >
                              {showPasswords['telegram_token'] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                            </button>
                          </div>
                        </div>
                        <div className="md:col-span-2">
                          <label className="block text-xs font-bold text-gray-700 mb-1">ID Grup Koordinasi SAR Telegram</label>
                          <input
                            type="text"
                            value={formData.telegram_group || ''}
                            onChange={(e) => handleConfigChange('telegram_group', e.target.value)}
                            placeholder="Contoh: -100123456789"
                            className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-xs font-mono focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                          />
                        </div>
                        <div className="md:col-span-2">
                          <label className="block text-xs font-bold text-gray-700 mb-1">Webhook Base URL (Opsional / untuk Ngrok)</label>
                          <input
                            type="text"
                            value={webhookBaseUrl}
                            onChange={(e) => setWebhookBaseUrl(e.target.value)}
                            placeholder="Contoh: https://plated-coach-womanless.ngrok-free.dev"
                            className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-xs font-mono focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                          />
                          <p className="text-[10px] text-gray-400 mt-1">
                            Kosongkan jika di server production. Isi jika Anda menggunakan tunnel seperti ngrok untuk local development (harus menggunakan HTTPS).
                          </p>
                        </div>
                        <div className="md:col-span-2 flex justify-start">
                          <button
                            type="button"
                            onClick={handleSetupTelegramWebhook}
                            disabled={isSettingUpWebhook || !formData.telegram_token}
                            className="px-4 py-2.5 bg-sky-500 hover:bg-sky-600 text-white font-semibold text-xs rounded-xl transition-all flex items-center gap-1.5 shadow-md shadow-sky-500/10 active:scale-95 disabled:opacity-50"
                          >
                            {isSettingUpWebhook ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <Globe className="w-3.5 h-3.5" />
                            )}
                            Hubungkan Webhook Telegram
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* WhatsApp Section */}
                    <div className="bg-gray-50/50 border border-gray-100 p-6 rounded-3xl space-y-4">
                      <h3 className="font-bold text-gray-900 text-sm md:text-base flex items-center gap-2 text-emerald-600">
                        <MessageSquare className="w-5 h-5 text-emerald-500" /> WhatsApp Cloud API Integration
                      </h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <label className="block text-xs font-bold text-gray-700 mb-1">WhatsApp Phone Number ID</label>
                          <input
                            type="text"
                            value={formData.wa_phone_id || ''}
                            onChange={(e) => handleConfigChange('wa_phone_id', e.target.value)}
                            placeholder="Phone Number ID dari Meta Developer Portal"
                            className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-xs font-mono focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-bold text-gray-700 mb-1">WhatsApp Verify Token (Webhook)</label>
                          <div className="relative">
                            <input
                              type={showPasswords['wa_verify_token'] ? 'text' : 'password'}
                              value={formData.wa_verify_token || ''}
                              onChange={(e) => handleConfigChange('wa_verify_token', e.target.value)}
                              placeholder="Contoh: laporsar-verify-secret"
                              className="w-full pl-4 pr-10 py-3 bg-white border border-gray-200 rounded-xl text-xs font-mono focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                            />
                            <button
                              type="button"
                              onClick={() => togglePasswordVisibility('wa_verify_token')}
                              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors focus:outline-none"
                            >
                              {showPasswords['wa_verify_token'] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                            </button>
                          </div>
                        </div>
                        <div className="md:col-span-2">
                          <label className="block text-xs font-bold text-gray-700 mb-1">WhatsApp Graph API Access Token</label>
                          <textarea
                            rows={2}
                            value={formData.wa_token || ''}
                            onChange={(e) => handleConfigChange('wa_token', e.target.value)}
                            placeholder="Meta Graph API System User Token (Permanent)"
                            className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-xs font-mono focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none resize-none"
                          />
                        </div>
                        <div className="md:col-span-2">
                          <label className="block text-xs font-bold text-gray-700 mb-1">ID Grup Koordinasi WhatsApp</label>
                          <input
                            type="text"
                            value={formData.wa_group || ''}
                            onChange={(e) => handleConfigChange('wa_group', e.target.value)}
                            placeholder="ID grup WhatsApp (JID) tujuan forward laporan"
                            className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-xs font-mono focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                          />
                        </div>
                      </div>
                    </div>

                    <div className="flex justify-end pt-4">
                      <button
                        onClick={handleSaveMainConfigs}
                        disabled={updateSettingsMutation.isPending}
                        className="px-6 py-3 bg-slate-900 hover:bg-slate-800 text-white font-bold text-sm rounded-2xl hover:opacity-90 transition-all flex items-center gap-2 shadow-lg shadow-sm active:scale-95"
                      >
                        {updateSettingsMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                        Simpan Integrasi Webhook
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB 6: MODEL AI & DUAL-RAG */}
            {activeTab === 'ai' && (
              <div className="p-6 md:p-8 space-y-6">
                <div className="border-b border-gray-100 pb-5">
                  <h2 className="text-xl font-bold text-gray-900">Konfigurasi Model AI & Dual-RAG</h2>
                  <p className="text-sm text-gray-500 mt-1">Hubungkan engine LLM lokal (Ollama) atau Cloud API (Gemini, Claude, OpenAI) dengan basis RAG Vector Store.</p>
                </div>

                {isLoadingSettings ? (
                  <div className="py-20 flex justify-center"><Loader2 className="w-8 h-8 animate-spin text-slate-500" /></div>
                ) : (
                  <div className="space-y-8">
                    
                    {/* A. LLM Engine Section */}
                    <div className="bg-gray-50/50 border border-gray-100 p-6 rounded-3xl space-y-4">
                      <h3 className="font-bold text-gray-900 text-sm md:text-base flex items-center gap-2 text-slate-800">
                        <Server className="w-5 h-5 text-slate-500" /> LLM Engine (Otak Utama NLP)
                      </h3>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <label className="block text-xs font-bold text-gray-700 mb-1">Provider LLM</label>
                          <select
                            value={formData.ai_llm_provider || 'ollama'}
                            onChange={(e) => handleConfigChange('ai_llm_provider', e.target.value)}
                            className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                          >
                            <option value="ollama">Ollama (Lokal & Gratis)</option>
                            <option value="gemini">Google Gemini API</option>
                            <option value="openai">OpenAI API</option>
                            <option value="claude">Anthropic Claude API</option>
                            <option value="groq">Groq AI (Cepat & Open Source)</option>
                          </select>
                        </div>

                        <div>
                          <label className="block text-xs font-bold text-gray-700 mb-1">Model LLM</label>
                          {formData.ai_llm_provider === 'ollama' ? (
                            ollamaModelsData?.models && ollamaModelsData.models.length > 0 ? (
                              <select
                                value={formData.ai_llm_model || ''}
                                onChange={(e) => handleConfigChange('ai_llm_model', e.target.value)}
                                className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                              >
                                <option value="">-- Pilih Model Ollama Lokal --</option>
                                {ollamaModelsData.models.map((m: string) => (
                                  <option key={m} value={m}>{m}</option>
                                ))}
                              </select>
                            ) : (
                              <input
                                type="text"
                                value={formData.ai_llm_model || ''}
                                onChange={(e) => handleConfigChange('ai_llm_model', e.target.value)}
                                placeholder="Ketik manual model Ollama (misal: llama3)..."
                                className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                              />
                            )
                          ) : cloudLlmModels && cloudLlmModels.length > 0 ? (
                            <select
                              value={formData.ai_llm_model || ''}
                              onChange={(e) => handleConfigChange('ai_llm_model', e.target.value)}
                              className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                            >
                              <option value="">-- Pilih Model dari Provider --</option>
                              {cloudLlmModels.map((m: string) => (
                                <option key={m} value={m}>{m}</option>
                              ))}
                            </select>
                          ) : (
                            <input
                              type="text"
                              value={formData.ai_llm_model || ''}
                              onChange={(e) => handleConfigChange('ai_llm_model', e.target.value)}
                              placeholder="Ketik manual, atau tekan 'Uji Koneksi' untuk memuat model..."
                              className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                            />
                          )}
                        </div>

                        <div className="md:col-span-2">
                          <label className="block text-xs font-bold text-gray-700 mb-1">Ollama Host URL (Hanya untuk Ollama)</label>
                          <input
                            type="text"
                            value={formData.ai_llm_base_url || 'http://localhost:11434'}
                            onChange={(e) => handleConfigChange('ai_llm_base_url', e.target.value)}
                            placeholder="http://localhost:11434"
                            className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-xs font-mono focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                          />
                        </div>

                        {formData.ai_llm_provider !== 'ollama' && (
                          <div className="md:col-span-2">
                            <label className="block text-xs font-bold text-gray-700 mb-1">API Key Cloud Provider</label>
                            <input
                              type="password"
                              value={formData.ai_llm_api_key || ''}
                              onChange={(e) => handleConfigChange('ai_llm_api_key', e.target.value)}
                              placeholder="Masukkan API key rahasia Anda"
                              className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-xs font-mono focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                            />
                          </div>
                        )}
                      </div>

                      <div className="flex justify-start">
                        <button
                          type="button"
                          onClick={() => handleTestAiConnection('llm')}
                          disabled={testResult.status === 'testing'}
                          className="px-4 py-2 bg-slate-100 hover:bg-slate-200 active:scale-95 text-slate-700 text-xs font-extrabold rounded-xl border border-slate-200 flex items-center gap-2 transition-all shadow-sm"
                        >
                          {testResult.status === 'testing' ? <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-500" /> : <CheckCircle2 className="w-3.5 h-3.5 text-slate-800" />}
                          Uji Koneksi Engine LLM
                        </button>
                      </div>
                    </div>

                    {/* B. Embedding & Vector Store (RAG) */}
                    <div className="bg-gray-50/50 border border-gray-100 p-6 rounded-3xl space-y-4">
                      <h3 className="font-bold text-gray-900 text-sm md:text-base flex items-center gap-2 text-violet-600">
                        <Database className="w-5 h-5 text-violet-500" /> Embedding & Vector Store (RAG)
                      </h3>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <label className="block text-xs font-bold text-gray-700 mb-1">Provider Embedding</label>
                          <select
                            value={formData.ai_embed_provider || 'ollama'}
                            onChange={(e) => handleConfigChange('ai_embed_provider', e.target.value)}
                            className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                          >
                            <option value="ollama">Ollama (Lokal & Gratis)</option>
                            <option value="gemini">Google Gemini Embedding</option>
                            <option value="openai">OpenAI Embedding</option>
                            <option value="groq">Groq AI Embedding (Cepat)</option>
                          </select>
                        </div>

                        <div>
                          <label className="block text-xs font-bold text-gray-700 mb-1">Model Embedding</label>
                          {formData.ai_embed_provider === 'ollama' ? (
                            ollamaModelsData?.models && ollamaModelsData.models.length > 0 ? (
                              <select
                                value={formData.ai_embed_model || ''}
                                onChange={(e) => handleConfigChange('ai_embed_model', e.target.value)}
                                className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                              >
                                <option value="">-- Pilih Model Ollama Lokal --</option>
                                {ollamaModelsData.models.map((m: string) => (
                                  <option key={m} value={m}>{m}</option>
                                ))}
                              </select>
                            ) : (
                              <input
                                type="text"
                                value={formData.ai_embed_model || ''}
                                onChange={(e) => handleConfigChange('ai_embed_model', e.target.value)}
                                placeholder="Ketik model Ollama (misal: nomic-embed-text)..."
                                className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                              />
                            )
                          ) : cloudEmbedModels && cloudEmbedModels.length > 0 ? (
                            <select
                              value={formData.ai_embed_model || ''}
                              onChange={(e) => handleConfigChange('ai_embed_model', e.target.value)}
                              className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                            >
                              <option value="">-- Pilih Model Embedding dari Provider --</option>
                              {cloudEmbedModels.map((m: string) => (
                                <option key={m} value={m}>{m}</option>
                              ))}
                            </select>
                          ) : formData.ai_embed_provider === 'gemini' ? (
                            <select
                              value={formData.ai_embed_model || 'text-embedding-004'}
                              onChange={(e) => handleConfigChange('ai_embed_model', e.target.value)}
                              className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                            >
                              <option value="text-embedding-004">text-embedding-004 (Rekomendasi)</option>
                              <option value="embedding-001">embedding-001</option>
                            </select>
                          ) : formData.ai_embed_provider === 'openai' ? (
                            <select
                              value={formData.ai_embed_model || 'text-embedding-3-small'}
                              onChange={(e) => handleConfigChange('ai_embed_model', e.target.value)}
                              className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                            >
                              <option value="text-embedding-3-small">text-embedding-3-small (Rekomendasi)</option>
                              <option value="text-embedding-3-large">text-embedding-3-large</option>
                              <option value="text-embedding-ada-002">text-embedding-ada-002 (Legacy)</option>
                            </select>
                          ) : formData.ai_embed_provider === 'groq' ? (
                            <select
                              value={formData.ai_embed_model || 'bge-large-en-v1.5'}
                              onChange={(e) => handleConfigChange('ai_embed_model', e.target.value)}
                              className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                            >
                              <option value="bge-large-en-v1.5">bge-large-en-v1.5 (Rekomendasi)</option>
                            </select>
                          ) : (
                            <input
                              type="text"
                              value={formData.ai_embed_model || ''}
                              onChange={(e) => handleConfigChange('ai_embed_model', e.target.value)}
                              placeholder="Ketik manual atau klik 'Uji Koneksi Engine Embedding'..."
                              className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                            />
                          )}
                        </div>

                        {['openai', 'groq', 'gemini'].includes(formData.ai_embed_provider || '') && (
                          <div className="md:col-span-2">
                            <label className="block text-xs font-bold text-gray-700 mb-1">API Key Cloud Embedding (Kosongkan jika sama dengan LLM Key)</label>
                            <input
                              type="password"
                              value={formData.ai_embed_api_key || ''}
                              onChange={(e) => handleConfigChange('ai_embed_api_key', e.target.value)}
                              placeholder="API Key khusus Embedding (opsional)"
                              className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-xs font-mono focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                            />
                          </div>
                        )}
                      </div>

                      <div className="flex justify-start">
                        <button
                          type="button"
                          onClick={() => handleTestAiConnection('embed')}
                          disabled={testResult.status === 'testing'}
                          className="px-4 py-2 bg-slate-100 hover:bg-slate-200 active:scale-95 text-slate-700 text-xs font-extrabold rounded-xl border border-slate-200 flex items-center gap-2 transition-all shadow-sm"
                        >
                          {testResult.status === 'testing' ? <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-500" /> : <CheckCircle2 className="w-3.5 h-3.5 text-slate-800" />}
                          Uji Koneksi Engine Embedding
                        </button>
                      </div>
                    </div>

                    {/* C. Speech-to-Text (STT / Audio Whisper) */}
                    <div className="bg-gray-50/50 border border-gray-100 p-6 rounded-3xl space-y-4">
                      <h3 className="font-bold text-gray-900 text-sm md:text-base flex items-center gap-2 text-indigo-600">
                        <Radio className="w-5 h-5 text-indigo-500" /> Speech-to-Text (STT / Audio Whisper)
                      </h3>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <label className="block text-xs font-bold text-gray-700 mb-1">Provider STT</label>
                          <select
                            value={formData.ai_stt_provider || 'ollama'}
                            onChange={(e) => handleConfigChange('ai_stt_provider', e.target.value)}
                            className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                          >
                            <option value="ollama">Ollama (Lokal & Gratis)</option>
                            <option value="local_whisper">Whisper Server Mandiri (Local/Docker Container)</option>
                            <option value="openai">OpenAI API (Cloud)</option>
                            <option value="groq">Groq AI (Cepat - Cloud)</option>
                            <option value="gemini">Google Gemini API (Cloud)</option>
                          </select>
                        </div>

                        <div>
                          <label className="block text-xs font-bold text-gray-700 mb-1">Model STT</label>
                          {formData.ai_stt_provider === 'ollama' ? (
                            ollamaModelsData?.models && ollamaModelsData.models.length > 0 ? (
                              <select
                                value={formData.ai_stt_model || ''}
                                onChange={(e) => handleConfigChange('ai_stt_model', e.target.value)}
                                className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                              >
                                <option value="">-- Pilih Model Ollama Lokal --</option>
                                {ollamaModelsData.models.map((m: string) => (
                                  <option key={m} value={m}>{m}</option>
                                ))}
                              </select>
                            ) : (
                              <input
                                type="text"
                                value={formData.ai_stt_model || ''}
                                onChange={(e) => handleConfigChange('ai_stt_model', e.target.value)}
                                placeholder="Ketik model STT Ollama..."
                                className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                              />
                            )
                          ) : cloudSttModels && cloudSttModels.length > 0 ? (
                            <select
                              value={formData.ai_stt_model || ''}
                              onChange={(e) => handleConfigChange('ai_stt_model', e.target.value)}
                              className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                            >
                              <option value="">-- Pilih Model STT dari Provider --</option>
                              {cloudSttModels.map((m: string) => (
                                <option key={m} value={m}>{m}</option>
                              ))}
                            </select>
                          ) : formData.ai_stt_provider === 'openai' ? (
                            <select
                              value={formData.ai_stt_model || 'whisper-1'}
                              onChange={(e) => handleConfigChange('ai_stt_model', e.target.value)}
                              className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                            >
                              <option value="whisper-1">whisper-1 (Rekomendasi)</option>
                            </select>
                          ) : formData.ai_stt_provider === 'groq' ? (
                            <select
                              value={formData.ai_stt_model || 'whisper-large-v3'}
                              onChange={(e) => handleConfigChange('ai_stt_model', e.target.value)}
                              className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                            >
                              <option value="whisper-large-v3">whisper-large-v3 (Tercepat & Akurat)</option>
                              <option value="whisper-large-v3-turbo">whisper-large-v3-turbo (Super Cepat)</option>
                            </select>
                          ) : formData.ai_stt_provider === 'gemini' ? (
                            <select
                              value={formData.ai_stt_model || 'gemini-1.5-flash'}
                              onChange={(e) => handleConfigChange('ai_stt_model', e.target.value)}
                              className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                            >
                              <option value="gemini-1.5-flash">gemini-1.5-flash (Gratis/Murah Multimodal)</option>
                              <option value="gemini-2.0-flash">gemini-2.0-flash (Generasi Baru)</option>
                              <option value="gemini-1.5-pro">gemini-1.5-pro (Akurat Multimodal)</option>
                            </select>
                          ) : formData.ai_stt_provider === 'local_whisper' ? (
                            <select
                              value={formData.ai_stt_model || 'medium'}
                              onChange={(e) => handleConfigChange('ai_stt_model', e.target.value)}
                              className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                            >
                              <option value="medium">medium (Rekomendasi - Akurat & Cepat)</option>
                              <option value="large-v3">large-v3 (Sangat Akurat - Butuh RAM Besar)</option>
                              <option value="small">small (Cepat - Akurasi Standar)</option>
                              <option value="base">base (Sangat Cepat - Uji Coba)</option>
                            </select>
                          ) : (
                            <input
                              type="text"
                              value={formData.ai_stt_model || ''}
                              onChange={(e) => handleConfigChange('ai_stt_model', e.target.value)}
                              placeholder="Ketik manual atau klik 'Uji Koneksi Engine STT'..."
                              className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                            />
                          )}
                        </div>

                        {formData.ai_stt_provider === 'local_whisper' && (
                          <div className="md:col-span-2">
                            <label className="block text-xs font-bold text-gray-700 mb-1">Whisper Server URL</label>
                            <input
                              type="text"
                              value={formData.ai_stt_base_url || 'http://localhost:8002'}
                              onChange={(e) => handleConfigChange('ai_stt_base_url', e.target.value)}
                              placeholder="http://localhost:8002"
                              className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-xs font-mono focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                            />
                          </div>
                        )}

                        {['openai', 'groq', 'gemini'].includes(formData.ai_stt_provider || '') && (
                          <div className="md:col-span-2">
                            <label className="block text-xs font-bold text-gray-700 mb-1">API Key Cloud STT (Kosongkan jika sama dengan LLM Key)</label>
                            <input
                              type="password"
                              value={formData.ai_stt_api_key || ''}
                              onChange={(e) => handleConfigChange('ai_stt_api_key', e.target.value)}
                              placeholder="API Key khusus STT (opsional)"
                              className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-xs font-mono focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                            />
                          </div>
                        )}
                      </div>

                      <div className="flex justify-start">
                        <button
                          type="button"
                          onClick={() => handleTestAiConnection('stt')}
                          disabled={testResult.status === 'testing'}
                          className="px-4 py-2 bg-slate-100 hover:bg-slate-200 active:scale-95 text-slate-700 text-xs font-extrabold rounded-xl border border-slate-200 flex items-center gap-2 transition-all shadow-sm"
                        >
                          {testResult.status === 'testing' ? <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-500" /> : <CheckCircle2 className="w-3.5 h-3.5 text-slate-800" />}
                          Uji Koneksi Engine STT
                        </button>
                      </div>
                    </div>

                    {/* Connection Test Message Board */}
                    {testResult.status !== 'idle' && (
                      <div className={`p-4 rounded-2xl flex items-start gap-3 border text-xs font-semibold ${
                        testResult.status === 'success' 
                          ? 'bg-emerald-50 border-emerald-100 text-emerald-800' 
                          : testResult.status === 'error'
                          ? 'bg-rose-50 border-rose-100 text-rose-800'
                          : 'bg-slate-100 border-slate-200 text-slate-900'
                      }`}>
                        {testResult.status === 'testing' ? (
                          <Loader2 className="w-4 h-4 animate-spin flex-shrink-0" />
                        ) : testResult.status === 'success' ? (
                          <Check className="w-4 h-4 text-emerald-600 flex-shrink-0 font-extrabold" />
                        ) : (
                          <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                        )}
                        <span>{testResult.message}</span>
                      </div>
                    )}

                    <div className="flex justify-end pt-4">
                      <button
                        onClick={handleSaveMainConfigs}
                        disabled={updateSettingsMutation.isPending}
                        className="px-6 py-3 bg-slate-900 hover:bg-slate-800 text-white font-bold text-sm rounded-2xl hover:opacity-90 transition-all flex items-center gap-2 shadow-lg shadow-sm active:scale-95"
                      >
                        {updateSettingsMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                        Simpan Seluruh Konfigurasi AI
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB 7: MANAJEMEN ADMINISTRATOR */}
            {activeTab === 'users' && (
              <div className="p-6 md:p-8 space-y-6">
                <div className="flex items-center justify-between border-b border-gray-100 pb-5">
                  <div>
                    <h2 className="text-xl font-bold text-gray-900">Manajemen Pengguna & Hak Akses</h2>
                    <p className="text-sm text-gray-500 mt-1">Daftar operator dan super administrator yang berwenang mengakses Pusat Kendali Lapor SAR.</p>
                  </div>
                  <button
                    onClick={openAddUser}
                    className="px-4 py-2.5 bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs rounded-xl flex items-center gap-2 transition-all shadow-md active:scale-95"
                  >
                    <UserPlus className="w-4 h-4" /> Tambah Pengguna
                  </button>
                </div>

                {isLoadingUsers ? (
                  <div className="py-20 flex justify-center"><Loader2 className="w-8 h-8 animate-spin text-slate-500" /></div>
                ) : !usersData || usersData.length === 0 ? (
                  <div className="text-center py-16 space-y-3">
                    <Users className="w-12 h-12 text-gray-300 mx-auto" />
                    <p className="text-sm font-semibold text-gray-500">Belum ada pengguna terdaftar.</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {usersData.map((usr: any) => (
                      <div key={usr.id} className="p-5 border border-gray-100 rounded-2xl flex items-center justify-between gap-4">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 bg-slate-100 rounded-xl flex items-center justify-center text-slate-800 flex-shrink-0 font-bold">
                            {usr.name.charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <h3 className="font-bold text-gray-900 text-sm">{usr.name}</h3>
                            <p className="text-xs text-gray-500 mt-0.5">{usr.email} {usr.phone ? `• ${usr.phone}` : ''}</p>
                          </div>
                        </div>

                        <div className="flex items-center gap-3 flex-shrink-0">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            usr.role === 'Super Admin' 
                              ? 'bg-rose-50 border border-rose-100 text-rose-700' 
                              : 'bg-sky-50 border border-sky-100 text-sky-700'
                          }`}>
                            {usr.role}
                          </span>
                          <span className={`w-2.5 h-2.5 rounded-full ${usr.is_active ? 'bg-emerald-500' : 'bg-gray-300'}`} title={usr.is_active ? 'Aktif' : 'Nonaktif'}></span>
                          
                          <div className="flex gap-1.5 border-l border-gray-100 pl-3">
                            <button
                              onClick={() => openEditUser(usr)}
                              className="p-1.5 hover:bg-gray-50 rounded-lg text-gray-500 hover:text-slate-900 transition-all"
                            >
                              <Edit2 className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => {
                                if (confirm(`Apakah Anda yakin ingin menghapus user ${usr.name}?`)) {
                                  deleteUserMutation.mutate(usr.id);
                                }
                              }}
                              className="p-1.5 hover:bg-gray-50 rounded-lg text-gray-500 hover:text-rose-600 transition-all"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* TAB 8: BACKUP & RESTORE DATA */}
            {activeTab === 'backup' && (
              <div className="p-6 md:p-8 space-y-6">
                <div className="border-b border-gray-100 pb-5">
                  <h2 className="text-xl font-bold text-gray-900">Backup & Pemulihan Database</h2>
                  <p className="text-sm text-gray-500 mt-1">Ekspor seluruh database operasional Anda ke file cadangan yang aman, atau pulihkan data dari file backup sebelumnya.</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Backup Card */}
                  <div className="border border-gray-150 p-6 rounded-3xl bg-white shadow-sm hover:shadow-md transition-all flex flex-col justify-between space-y-4">
                    <div className="space-y-2">
                      <div className="w-12 h-12 bg-slate-100 rounded-2xl flex items-center justify-center text-slate-800">
                        <Database className="w-6 h-6" />
                      </div>
                      <h3 className="text-base font-bold text-gray-900">Pencadangan Data (Database Backup)</h3>
                      <p className="text-xs text-gray-500 leading-relaxed">
                        Unduh seluruh data pos/unit SAR, klasifikasi, kamus jargon, kontak, dan daftar laporan operasional ke dalam satu file ZIP terkompresi. Simpan file ini di lokasi yang aman sebagai cadangan.
                      </p>
                    </div>

                    <button
                      onClick={handleDownloadBackup}
                      disabled={isBackingUp}
                      className="w-full py-3 bg-slate-900 hover:bg-slate-800 text-white disabled:opacity-55 active:scale-98 text-white font-bold text-xs rounded-xl flex items-center justify-center gap-2 transition-all shadow-md active:scale-95"
                    >
                      {isBackingUp ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Save className="w-4 h-4" />
                      )}
                      Ekspor & Unduh Cadangan Data
                    </button>
                  </div>

                  {/* Restore Card */}
                  <div className="border border-rose-100 p-6 rounded-3xl bg-rose-50/15 shadow-sm hover:shadow-md transition-all flex flex-col justify-between space-y-4">
                    <div className="space-y-2">
                      <div className="w-12 h-12 bg-rose-100 rounded-2xl flex items-center justify-center text-rose-600">
                        <AlertCircle className="w-6 h-6" />
                      </div>
                      <h3 className="text-base font-bold text-gray-900">Pemulihan Data (Database Restore)</h3>
                      <p className="text-xs text-rose-700/80 leading-relaxed">
                        **PERINGATAN BAHAYA**: Memulihkan database dari file cadangan akan **menghapus dan menimpa** seluruh data aktif yang ada saat ini secara permanen. Pastikan Anda mengunggah file ZIP backup resmi yang valid.
                      </p>
                    </div>

                    <div className="space-y-3">
                      <input
                        type="file"
                        accept=".zip"
                        id="db-restore-upload"
                        className="hidden"
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) setSelectedBackupFile(file);
                        }}
                      />
                      {selectedBackupFile ? (
                        <div className="p-3 bg-rose-50 border border-rose-100 rounded-2xl flex items-center justify-between text-xs">
                          <span className="font-semibold text-gray-700 truncate max-w-[180px]">
                            {selectedBackupFile.name}
                          </span>
                          <button
                            onClick={() => setSelectedBackupFile(null)}
                            className="p-1 hover:bg-rose-100 rounded-full text-rose-600 transition-colors"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      ) : (
                        <label
                          htmlFor="db-restore-upload"
                          className="w-full py-3 bg-white border border-rose-200 border-dashed hover:bg-rose-50/30 text-rose-700 font-bold text-xs rounded-xl shadow-sm cursor-pointer transition-all flex items-center justify-center gap-2"
                        >
                          Pilih Berkas ZIP Cadangan
                        </label>
                      )}

                      <button
                        onClick={() => selectedBackupFile && handleRestoreDatabase(selectedBackupFile)}
                        disabled={!selectedBackupFile || isRestoring}
                        className="w-full py-3 bg-rose-600 hover:bg-rose-700 disabled:bg-gray-300 disabled:text-gray-500 text-white font-bold text-xs rounded-xl flex items-center justify-center gap-2 transition-all shadow-md active:scale-95"
                      >
                        {isRestoring ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <RefreshCw className="w-4 h-4" />
                        )}
                        Pulihkan Data Sekarang
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 9: WIDGET LAPOR SAR INTEGRATIONS */}
            {activeTab === 'widget' && (
              <div className="p-6 md:p-8 space-y-6">
                <div className="border-b border-gray-100 pb-5">
                  <h2 className="text-xl font-bold text-gray-900">Manajemen Integrasi Widget Lapor SAR</h2>
                  <p className="text-sm text-gray-500 mt-1">Setujui pengajuan API Key dari situs luar untuk menempelkan widget obrolan darurat Lapor SAR.</p>
                </div>

                {/* Daftar Pengajuan */}
                <div className="bg-white border border-gray-150 rounded-3xl overflow-hidden shadow-sm">
                  <div className="px-6 py-4 border-b border-gray-100 bg-gray-50/50 flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div>
                      <h3 className="text-sm font-bold text-gray-800">Daftar Pengajuan API Key</h3>
                    </div>
                    <div className="flex items-center gap-3">
                      <button
                        onClick={openAddWidget}
                        className="px-3 py-2 bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs rounded-xl flex items-center gap-1.5 transition-all shadow-md active:scale-95"
                      >
                        <Plus className="w-3.5 h-3.5" /> Tambah Integrasi
                      </button>
                      <span className="text-xs text-gray-500 font-semibold">Total: {widgetRequests.length}</span>
                    </div>
                  </div>

                  {widgetRequests.length === 0 ? (
                    <div className="p-12 text-center text-gray-400 space-y-3">
                      <Key className="w-12 h-12 text-gray-300 mx-auto" />
                      <div>
                        <p className="text-xs font-bold text-gray-700">Belum Ada Pengajuan Widget</p>
                        <p className="text-[10px] max-w-xs mx-auto leading-relaxed mt-1">Semua permohonan API Key dari instansi eksternal akan muncul di sini untuk verifikasi manual.</p>
                      </div>
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left border-collapse">
                        <thead>
                          <tr className="border-b border-gray-100 text-[10px] font-bold text-gray-500 uppercase bg-gray-50/30">
                            <th className="px-6 py-3.5">Nama Instansi / Website</th>
                            <th className="px-6 py-3.5">Domain Website</th>
                            <th className="px-6 py-3.5">Kontak Resmi</th>
                            <th className="px-6 py-3.5">Status</th>
                            <th className="px-6 py-3.5">API Key</th>
                            <th className="px-6 py-3.5 text-right">Aksi</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100 text-xs text-gray-700">
                          {widgetRequests.map((req: any) => (
                            <tr key={req.id} className="hover:bg-gray-50/50 transition-colors">
                              <td className="px-6 py-4 font-bold text-gray-900">{req.partner_name}</td>
                              <td className="px-6 py-4 font-mono text-gray-600 flex items-center gap-1">
                                <Globe className="w-3.5 h-3.5 text-gray-400" />
                                <span>{req.website_url}</span>
                              </td>
                              <td className="px-6 py-4 space-y-1">
                                <div className="text-gray-500">Email: <span className="font-medium text-gray-800">{req.official_email}</span></div>
                                <div className="text-gray-500">WhatsApp: <span className="font-medium text-gray-800">{req.official_phone}</span></div>
                              </td>
                              <td className="px-6 py-4">
                                <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-[10px] font-bold ${
                                  req.status === 'APPROVED' ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' :
                                  req.status === 'REJECTED' ? 'bg-rose-50 text-rose-700 border border-rose-100' :
                                  'bg-amber-50 text-amber-700 border border-amber-100'
                                }`}>
                                  {req.status === 'APPROVED' ? 'Disetujui' :
                                   req.status === 'REJECTED' ? 'Ditolak' : 'Menunggu'}
                                </span>
                              </td>
                              <td className="px-6 py-4">
                                {req.api_key ? (
                                  <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 px-2.5 py-1.5 rounded-xl w-max font-mono text-[11px] text-gray-800 shadow-sm">
                                    <span>{req.api_key}</span>
                                    <button
                                      onClick={() => {
                                        navigator.clipboard.writeText(req.api_key);
                                        showSuccessToast('API Key berhasil disalin ke clipboard.');
                                      }}
                                      className="text-slate-800 hover:text-slate-800 font-bold p-1 hover:bg-slate-100 rounded-lg transition-colors text-[10px]"
                                      title="Salin API Key"
                                    >
                                      Salin
                                    </button>
                                  </div>
                                ) : (
                                  <span className="text-gray-400 italic">Belum dibuat</span>
                                )}
                              </td>
                              <td className="px-6 py-4 text-right">
                                <div className="flex items-center justify-end gap-2">
                                  {req.status === 'PENDING' && (
                                    <>
                                      <button
                                        onClick={() => approveWidgetMutation.mutate(req.id)}
                                        disabled={approveWidgetMutation.isPending || rejectWidgetMutation.isPending}
                                        className="px-2.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-[10px] rounded-xl shadow-sm transition-all active:scale-95 flex items-center gap-1"
                                      >
                                        {approveWidgetMutation.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Setujui'}
                                      </button>
                                      <button
                                        onClick={() => rejectWidgetMutation.mutate(req.id)}
                                        disabled={approveWidgetMutation.isPending || rejectWidgetMutation.isPending}
                                        className="px-2.5 py-1.5 bg-rose-600 hover:bg-rose-700 text-white font-bold text-[10px] rounded-xl shadow-sm transition-all active:scale-95 flex items-center gap-1"
                                      >
                                        {rejectWidgetMutation.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Tolak'}
                                      </button>
                                    </>
                                  )}
                                  <button
                                    onClick={() => openEditWidget(req)}
                                    className="p-1.5 hover:bg-gray-100 rounded-lg text-gray-500 hover:text-slate-900 transition-all"
                                    title="Edit Integrasi"
                                  >
                                    <Edit2 className="w-3.5 h-3.5" />
                                  </button>
                                  <button
                                    onClick={() => {
                                      if (confirm(`Apakah Anda yakin ingin menghapus integrasi widget untuk ${req.partner_name}? Tindakan ini akan membatalkan API Key secara permanen.`)) {
                                        deleteWidgetMutation.mutate(req.id);
                                      }
                                    }}
                                    className="p-1.5 hover:bg-gray-100 rounded-lg text-gray-500 hover:text-rose-600 transition-all"
                                    title="Hapus / Cabut Integrasi"
                                  >
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            )}

          </div>
        </div>
      </div>

      {/* ============================================================== */}
      {/* MODALS AREA */}
      {/* ============================================================== */}

      {/* A. Location Modal */}
      {locationModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-xl w-full border border-gray-100 shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="px-6 py-5 border-b border-gray-100 flex items-center justify-between bg-slate-50/80">
              <h3 className="font-extrabold text-gray-900 text-base md:text-lg">
                {editingLocation ? `Edit ${editingLocation.name}` : 'Tambah Pos/Unit SAR Baru'}
              </h3>
              <button onClick={() => setLocationModalOpen(false)} className="p-1.5 hover:bg-gray-200 rounded-full transition-all text-gray-400">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2">
                  <label className="block text-xs font-bold text-gray-700 mb-1">Nama Pos / Kantor SAR</label>
                  <input
                    type="text"
                    value={locationForm.name}
                    onChange={(e) => setLocationForm({ ...locationForm, name: e.target.value })}
                    placeholder="Contoh: Pos SAR Ranai"
                    className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">Tipe Unit</label>
                  <select
                    value={locationForm.type}
                    onChange={(e) => {
                      const newType = e.target.value;
                      let newIcon = locationForm.icon;
                      if (!locationForm.icon || ['🏢', '🏠', '🛡️'].includes(locationForm.icon)) {
                        if (newType === 'Kantor SAR') newIcon = '🏢';
                        else if (newType === 'Pos SAR') newIcon = '🏠';
                        else if (newType === 'Unit Siaga SAR') newIcon = '🛡️';
                      }
                      setLocationForm({ ...locationForm, type: newType, icon: newIcon });
                    }}
                    className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                  >
                    <option value="Kantor SAR">Kantor SAR</option>
                    <option value="Pos SAR">Pos SAR</option>
                    <option value="Unit Siaga SAR">Unit Siaga SAR</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">Alamat Pos / Wilayah</label>
                  <input
                    type="text"
                    value={locationForm.address}
                    onChange={(e) => setLocationForm({ ...locationForm, address: e.target.value })}
                    placeholder="Alamat lengkap pos"
                    className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                  />
                </div>
                <div className="col-span-2">
                  <label className="block text-xs font-bold text-gray-700 mb-1">Ikon / Gambar Kustom</label>
                  
                  {/* Visual Preview & Selector */}
                  <div className="flex items-center gap-4 p-4 bg-gray-50 border border-gray-200 rounded-2xl">
                    <div className="flex flex-col items-center justify-center shrink-0">
                      {locationForm.icon && (locationForm.icon.startsWith('uploads/') || locationForm.icon.startsWith('http')) ? (
                        <div className="relative group">
                          <img 
                            src={`${locationForm.icon.startsWith('http') ? '' : getBackendUrl() + '/'}${locationForm.icon}`} 
                            alt="Custom Icon" 
                            className="w-16 h-16 rounded-full object-cover border-2 border-slate-900 shadow-md animate-in fade-in zoom-in duration-200"
                          />
                          <button
                            type="button"
                            onClick={() => {
                              // Reset to default emoji based on type
                              let defEmoji = '🏠';
                              if (locationForm.type === 'Kantor SAR') defEmoji = '🏢';
                              else if (locationForm.type === 'Unit Siaga SAR') defEmoji = '🛡️';
                              setLocationForm({ ...locationForm, icon: defEmoji });
                            }}
                            className="absolute -top-1 -right-1 bg-red-500 text-white p-1 rounded-full hover:bg-red-600 transition-all shadow-sm active:scale-90"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ) : (
                        <div className="w-16 h-16 rounded-full bg-white border border-gray-200 shadow-sm flex items-center justify-center text-3xl">
                          {locationForm.icon || '🏠'}
                        </div>
                      )}
                      <span className="text-[10px] text-gray-400 mt-1 font-semibold uppercase tracking-wider">Preview</span>
                    </div>

                    <div className="flex-1 space-y-3">
                      {/* Upload File Input & Button */}
                      <div>
                        <input
                          type="file"
                          accept="image/*"
                          id="location-icon-upload"
                          className="hidden"
                          onChange={async (e) => {
                            const file = e.target.files?.[0];
                            if (file) {
                              try {
                                const formData = new FormData();
                                formData.append('file', file);
                                const result = await uploadLocationIcon(formData);
                                if (result && result.url) {
                                  setLocationForm({ ...locationForm, icon: result.url });
                                }
                              } catch (err: any) {
                                alert(err.response?.data?.detail || "Gagal mengunggah file gambar.");
                              }
                            }
                          }}
                        />
                        <label
                          htmlFor="location-icon-upload"
                          className="inline-flex items-center gap-1.5 px-4 py-2 border border-slate-200 hover:border-slate-300 hover:bg-slate-100/50 text-slate-800 text-xs font-bold rounded-xl transition-all cursor-pointer shadow-sm active:scale-95"
                        >
                          <Upload className="w-3.5 h-3.5" />
                          Unggah Gambar Kustom
                        </label>
                        <p className="text-[10px] text-gray-400 mt-1">Format: PNG/JPG/WEBP. Rekomendasi rasio 1:1.</p>
                      </div>

                      {/* Emoji fallback/quick selection list */}
                      <div className="space-y-1">
                        <span className="text-[10px] font-bold text-gray-500 block">Atau pilih emoji standar:</span>
                        <div className="flex flex-wrap items-center gap-1 bg-white border border-gray-150 rounded-xl p-1 w-fit">
                          {['🏢', '🏠', '🛡️', '⚓', '🛥️', '🚁', '🚑', '🚨', '🚒'].map((emoji) => (
                            <button
                              key={emoji}
                              type="button"
                              onClick={() => setLocationForm({ ...locationForm, icon: emoji })}
                              className={`w-7 h-7 rounded-lg flex items-center justify-center hover:bg-gray-100 hover:shadow-sm active:scale-95 transition-all text-sm ${
                                locationForm.icon === emoji ? 'bg-slate-100 text-slate-800 ring-1 ring-slate-900/20 font-bold' : 'text-gray-600'
                              }`}
                            >
                              {emoji}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Leaflet Map coordinates picker! */}
                <div className="col-span-2">
                  <label className="block text-xs font-bold text-gray-700 mb-2">Pilih Lokasi Koordinat (Leaflet Map Picker)</label>
                  <MapPicker
                    initialLat={locationForm.lat}
                    initialLng={locationForm.lng}
                    onChange={(lat, lng, address) => {
                      setLocationForm(prev => ({
                        ...prev,
                        lat,
                        lng,
                        address: address || prev.address
                      }));
                    }}
                  />
                </div>

                <div className="col-span-2">
                  <label className="block text-xs font-bold text-gray-700 mb-1">Personil Terkait (Koma pisahkan)</label>
                  <input
                    type="text"
                    value={locationForm.unsur}
                    onChange={(e) => setLocationForm({ ...locationForm, unsur: e.target.value })}
                    placeholder="Contoh: Tim Rescuer 1, Tim Medis, Pos AL"
                    className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                  />
                </div>

                <div className="col-span-2">
                  <label className="block text-xs font-bold text-gray-700 mb-1">Alut / Palsar Pendukung (Koma pisahkan)</label>
                  <input
                    type="text"
                    value={locationForm.alut}
                    onChange={(e) => setLocationForm({ ...locationForm, alut: e.target.value })}
                    placeholder="Contoh: RIB 01, LCR, Palsar Selam, Alat Evakuasi"
                    className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                  />
                </div>
              </div>
            </div>

            <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-3 bg-gray-50">
              <button
                type="button"
                onClick={() => setLocationModalOpen(false)}
                className="px-4 py-2 border border-gray-200 hover:bg-gray-100 text-gray-700 text-xs font-bold rounded-xl transition-all"
              >
                Batalkan
              </button>
              <button
                type="button"
                onClick={() => locationMutation.mutate(locationForm)}
                disabled={locationMutation.isPending}
                className="px-5 py-2 bg-slate-900 hover:bg-slate-800 disabled:bg-slate-300 text-white text-xs font-bold rounded-xl transition-all shadow-md active:scale-95 flex items-center gap-1.5"
              >
                {locationMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                {editingLocation ? 'Perbarui Lokasi' : 'Tambahkan Lokasi'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* B. Classification Modal */}
      {classificationModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full border border-gray-100 shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="px-6 py-5 border-b border-gray-100 flex items-center justify-between bg-slate-50/80">
              <h3 className="font-extrabold text-gray-900 text-base">
                {editingClassification ? 'Edit Klasifikasi Kejadian' : 'Tambah Klasifikasi Kejadian Baru'}
              </h3>
              <button onClick={() => setClassificationModalOpen(false)} className="p-1.5 hover:bg-gray-200 rounded-full transition-all text-gray-400">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Kategori / Nama Kejadian</label>
                <input
                  type="text"
                  value={classificationForm.category}
                  onChange={(e) => setClassificationForm({ ...classificationForm, category: e.target.value })}
                  placeholder="Contoh: Kondisi Membahayakan Manusia"
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Kata Kunci Deteksi (Koma pisahkan)</label>
                <textarea
                  rows={4}
                  value={classificationForm.keywords}
                  onChange={(e) => setClassificationForm({ ...classificationForm, keywords: e.target.value })}
                  placeholder="Contoh: tenggelam, hanyut, tersesat, gigit ular, sumur, runtuh"
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none resize-none"
                />
                <p className="text-[10px] text-gray-400 mt-1 flex items-center gap-1"><Info className="w-3.5 h-3.5 text-slate-500" /> Kata kunci digunakan untuk memetakan pesan awal dari pelapor ke kategori kejadian ini secara otomatis.</p>
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Dokumen SOP Penanganan (Opsional)</label>
                <select
                  value={classificationForm.sop_document_id || ''}
                  onChange={(e) => setClassificationForm({ ...classificationForm, sop_document_id: e.target.value ? parseInt(e.target.value) : null })}
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none text-gray-800 font-medium"
                >
                  <option value="">-- Pilih Dokumen SOP --</option>
                  {sopDocumentsData.map((doc: any) => (
                    <option key={doc.id} value={doc.id}>
                      {doc.title} {doc.is_global ? '(Pusat)' : ''}
                    </option>
                  ))}
                </select>
                <p className="text-[10px] text-gray-400 mt-1 flex items-center gap-1">
                  <Info className="w-3.5 h-3.5 text-slate-500" /> Hubungkan klasifikasi kejadian ini dengan dokumen SOP penanganannya yang telah diunggah.
                </p>
              </div>
            </div>

            <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-3 bg-gray-50">
              <button
                type="button"
                onClick={() => setClassificationModalOpen(false)}
                className="px-4 py-2 border border-gray-200 hover:bg-gray-100 text-gray-700 text-xs font-bold rounded-xl transition-all"
              >
                Batalkan
              </button>
              <button
                type="button"
                onClick={() => classificationMutation.mutate(classificationForm)}
                disabled={classificationMutation.isPending}
                className="px-5 py-2 bg-slate-900 hover:bg-slate-800 disabled:bg-slate-300 text-white text-xs font-bold rounded-xl transition-all shadow-md active:scale-95 flex items-center gap-1.5"
              >
                {classificationMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                {editingClassification ? 'Simpan' : 'Tambahkan'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* C. User Modal */}
      {userModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full border border-gray-100 shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="px-6 py-5 border-b border-gray-100 flex items-center justify-between bg-slate-50/80">
              <h3 className="font-extrabold text-gray-900 text-base">
                {editingUser ? `Edit Data ${editingUser.name}` : 'Registrasi Administrator Baru'}
              </h3>
              <button onClick={() => setUserModalOpen(false)} className="p-1.5 hover:bg-gray-200 rounded-full transition-all text-gray-400">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Nama Lengkap</label>
                <input
                  type="text"
                  value={userForm.name}
                  onChange={(e) => setUserForm({ ...userForm, name: e.target.value })}
                  placeholder="Nama Lengkap Operator"
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Email</label>
                <input
                  type="email"
                  value={userForm.email}
                  onChange={(e) => setUserForm({ ...userForm, email: e.target.value })}
                  placeholder="operator@basarnas.go.id"
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Nomor Kontak (WhatsApp)</label>
                <input
                  type="text"
                  value={userForm.phone}
                  onChange={(e) => setUserForm({ ...userForm, phone: e.target.value })}
                  placeholder="081234567890"
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">Role / Peran</label>
                  <select
                    value={userForm.role}
                    onChange={(e) => setUserForm({ ...userForm, role: e.target.value })}
                    className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                  >
                    <option value="Admin">Admin (Kantor / Unit)</option>
                    <option value="Operator">Operator</option>
                    <option value="User">User / Tamu</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">
                    {editingUser ? 'Password Baru (Opsional)' : 'Password'}
                  </label>
                  <input
                    type="password"
                    value={userForm.password}
                    onChange={(e) => setUserForm({ ...userForm, password: e.target.value })}
                    placeholder={editingUser ? 'Kosongkan jika sama' : '••••••••'}
                    className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                  />
                </div>
              </div>
            </div>

            <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-3 bg-gray-50">
              <button
                type="button"
                onClick={() => setUserModalOpen(false)}
                className="px-4 py-2 border border-gray-200 hover:bg-gray-100 text-gray-700 text-xs font-bold rounded-xl transition-all"
              >
                Batalkan
              </button>
              <button
                type="button"
                onClick={() => userMutation.mutate(userForm)}
                disabled={userMutation.isPending}
                className="px-5 py-2 bg-slate-900 hover:bg-slate-800 disabled:bg-slate-300 text-white text-xs font-bold rounded-xl transition-all shadow-md active:scale-95 flex items-center gap-1.5"
              >
                {userMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                {editingUser ? 'Simpan Data' : 'Registrasikan'}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* D. Widget Integration Modal */}
      {widgetModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full border border-gray-100 shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="px-6 py-5 border-b border-gray-100 flex items-center justify-between bg-slate-50/80">
              <h3 className="font-extrabold text-gray-900 text-base">
                {editingWidget ? `Edit Integrasi: ${editingWidget.partner_name}` : 'Tambah Integrasi Widget Baru'}
              </h3>
              <button onClick={() => setWidgetModalOpen(false)} className="p-1.5 hover:bg-gray-200 rounded-full transition-all text-gray-400">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Nama Instansi / Website</label>
                <input
                  type="text"
                  value={widgetForm.partner_name}
                  onChange={(e) => setWidgetForm({ ...widgetForm, partner_name: e.target.value })}
                  placeholder="Contoh: BPBD Kabupaten Natuna"
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Domain Website (Tanpa Protocol/WWW)</label>
                <input
                  type="text"
                  value={widgetForm.website_url}
                  onChange={(e) => setWidgetForm({ ...widgetForm, website_url: e.target.value })}
                  placeholder="Contoh: bpbd.natunakab.go.id"
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Email Resmi</label>
                <input
                  type="email"
                  value={widgetForm.official_email}
                  onChange={(e) => setWidgetForm({ ...widgetForm, official_email: e.target.value })}
                  placeholder="Contoh: info@bpbd.natunakab.go.id"
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Nomor Kontak WhatsApp Resmi</label>
                <input
                  type="text"
                  value={widgetForm.official_phone}
                  onChange={(e) => setWidgetForm({ ...widgetForm, official_phone: e.target.value })}
                  placeholder="Contoh: 081234567890"
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Status Verifikasi</label>
                <select
                  value={widgetForm.status}
                  onChange={(e) => setWidgetForm({ ...widgetForm, status: e.target.value })}
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all outline-none font-semibold text-gray-700"
                >
                  <option value="APPROVED" className="text-emerald-700 font-semibold bg-emerald-50">Disetujui (Aktifkan API Key)</option>
                  <option value="PENDING" className="text-amber-700 font-semibold bg-amber-50">Menunggu (Pending)</option>
                  <option value="REJECTED" className="text-rose-700 font-semibold bg-rose-50">Ditolak (Nonaktif)</option>
                </select>
              </div>
            </div>

            <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-3 bg-gray-50">
              <button
                type="button"
                onClick={() => setWidgetModalOpen(false)}
                className="px-4 py-2 border border-gray-200 hover:bg-gray-100 text-gray-700 text-xs font-bold rounded-xl transition-all"
              >
                Batalkan
              </button>
              <button
                type="button"
                onClick={() => widgetMutation.mutate(widgetForm)}
                disabled={widgetMutation.isPending}
                className="px-5 py-2 bg-slate-900 hover:bg-slate-800 disabled:bg-slate-300 text-white text-xs font-bold rounded-xl transition-all shadow-md active:scale-95 flex items-center gap-1.5"
              >
                {widgetMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                {editingWidget ? 'Simpan Perubahan' : 'Daftarkan Integrasi'}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
