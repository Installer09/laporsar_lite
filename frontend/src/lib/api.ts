import axios from 'axios';
import { decodeJwt } from './utils';

const getApiUrl = () => {
  if (typeof window !== 'undefined') {
    return process.env.NEXT_PUBLIC_API_URL || '/api';
  }
  // Server-side (Node.js SSR inside Docker container):
  if (process.env.INTERNAL_BACKEND_URL) {
    return `${process.env.INTERNAL_BACKEND_URL}/api`;
  }
  return 'http://backend:8000/api';
};
const API_URL = getApiUrl();

export const getBackendUrl = () => {
  if (typeof window !== 'undefined') {
    return window.location.origin;
  }
  return process.env.INTERNAL_BACKEND_URL || 'http://backend:8000';
};

export const getWsUrl = (token?: string | null): string => {
  let wsUrl = '';
  if (process.env.NEXT_PUBLIC_WS_URL) {
    wsUrl = process.env.NEXT_PUBLIC_WS_URL;
  } else if (process.env.NEXT_PUBLIC_API_URL && process.env.NEXT_PUBLIC_API_URL.startsWith('http')) {
    wsUrl = process.env.NEXT_PUBLIC_API_URL.replace(/^http/, 'ws').replace(/\/api\/?$/, '/api/ws');
  } else if (typeof window !== 'undefined') {
    const isHttps = window.location.protocol === 'https:';
    const proto = isHttps ? 'wss:' : 'ws:';
    const isDevPort = window.location.port === '3000' && window.location.hostname === 'localhost';
    if (isDevPort) {
      wsUrl = `${proto}//${window.location.hostname}:8000/api/ws`;
    } else {
      wsUrl = `${proto}//${window.location.host}/api/ws`;
    }
  } else {
    wsUrl = 'ws://backend:8000/api/ws';
  }

  if (token) {
    const sep = wsUrl.includes('?') ? '&' : '?';
    return `${wsUrl}${sep}token=${encodeURIComponent(token)}`;
  }
  return wsUrl;
};

export const getTenantSlug = () => {
  if (typeof window !== 'undefined') {
    const host = window.location.hostname.toLowerCase();

    // Ignore tunnels, preview platforms, and local IP addresses
    if (
      host.includes('trycloudflare.com') ||
      host.includes('pages.dev') ||
      host.includes('vercel.app') ||
      host.includes('ngrok') ||
      /^\d+\.\d+\.\d+\.\d+$/.test(host) ||
      host.includes(':')
    ) {
      return null;
    }

    const parts = host.split('.');
    
    // Localhost development: e.g. jakarta.localhost (2 parts)
    if (host.endsWith('localhost')) {
      if (parts.length > 1) {
        const tenant = parts[0];
        if (tenant !== 'localhost' && tenant !== 'www' && tenant !== 'admin') {
          return tenant;
        }
      }
      return null;
    }
    
    // Production domains: e.g. jakarta.laporsar.id (3 parts)
    // If it's laporsar.id (2 parts), there is no subdomain.
    if (parts.length > 2) {
      const tenant = parts[0];
      if (tenant !== 'www' && tenant !== 'admin' && tenant !== 'laporsar' && !tenant.match(/^\d+$/)) {
        return tenant;
      }
    }
  }
  return null;
};

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const tenant = getTenantSlug();
  if (tenant) {
    config.headers['X-Tenant-Slug'] = tenant;
  }
  
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
      
      // Cross-domain fallback: if tenant is not resolved from subdomain/hostname,
      // extract tenant slug from JWT token claims to prevent tenant mismatch block.
      if (!tenant) {
        try {
          const payload = decodeJwt(token);
          if (payload && payload.tenant_slug) {
            config.headers['X-Tenant-Slug'] = payload.tenant_slug;
          }
        } catch (e) {
          console.error('Failed to decode token in request interceptor:', e);
        }
      }
    }
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      const isLoginRequest = error.config && error.config.url && error.config.url.endsWith('/auth/login');
      if (!isLoginRequest) {
        localStorage.removeItem('token');
        if (typeof window !== 'undefined') {
          const currentPath = window.location.pathname;
          const isPublic = currentPath === '/login' || currentPath === '/register' || currentPath === '/help-center';
          if (!isPublic && sessionStorage.getItem('logging_out') !== 'true') {
            window.location.href = '/login';
          }
        }
      }
    }
    return Promise.reject(error);
  }
);

export const getReports = async () => {
  const { data } = await api.get('/reports');
  return data;
};

export const createReport = async (reportData: any) => {
  const { data } = await api.post('/reports', reportData);
  return data;
};

export const updateReport = async (id: number, reportData: any) => {
  const { data } = await api.put(`/reports/${id}`, reportData);
  return data;
};

export const deleteReport = async (id: number) => {
  const { data } = await api.delete(`/reports/${id}`);
  return data;
};

export const getContacts = async () => {
  const { data } = await api.get('/contacts');
  return data;
};

export const updateContact = async (id: number, contactData: any) => {
  const { data } = await api.put(`/contacts/${id}`, contactData);
  return data;
};

export const deleteContact = async (id: number) => {
  const { data } = await api.delete(`/contacts/${id}`);
  return data;
};

export const getKnowledgeBase = async (params?: any) => {
  const { data } = await api.get('/knowledge/dictionary', { params });
  return data;
};

export const createDictionaryWord = async (wordData: any) => {
  const { data } = await api.post('/knowledge/dictionary', wordData);
  return data;
};

export const updateDictionaryWord = async (id: number, wordData: any, isGlobal: boolean = false) => {
  const { data } = await api.put(`/knowledge/dictionary/${id}?is_global=${isGlobal}`, wordData);
  return data;
};

export const deleteDictionaryWord = async ({ id, isGlobal }: { id: number; isGlobal: boolean }) => {
  const { data } = await api.delete(`/knowledge/dictionary/${id}?is_global=${isGlobal}`);
  return data;
};

export const vectorizeAllDictionary = async (forceAll: boolean = false) => {
  const { data } = await api.post(`/knowledge/dictionary/vectorize-all?force_all=${forceAll}`);
  return data;
};

export const getStats = async () => {
  const { data } = await api.get('/stats');
  return data;
};

// --- Settings & System ---

export const getSettings = async () => {
  const { data } = await api.get('/settings/config');
  return data;
};

export const getWidgetRequests = async () => {
  const { data } = await api.get('/settings/widget-requests');
  return data;
};

export const approveWidgetRequest = async (id: number) => {
  const { data } = await api.post(`/settings/widget-requests/${id}/approve`);
  return data;
};

export const rejectWidgetRequest = async (id: number) => {
  const { data } = await api.post(`/settings/widget-requests/${id}/reject`);
  return data;
};

export const createWidgetRequest = async (requestData: any) => {
  const { data } = await api.post('/settings/widget-requests', requestData);
  return data;
};

export const createWidgetRequestAdmin = async (requestData: any) => {
  const { data } = await api.post('/settings/widget-requests/admin', requestData);
  return data;
};

export const updateWidgetRequest = async (id: number, requestData: any) => {
  const { data } = await api.put(`/settings/widget-requests/${id}`, requestData);
  return data;
};

export const deleteWidgetRequest = async (id: number) => {
  const { data } = await api.delete(`/settings/widget-requests/${id}`);
  return data;
};

export const updateSettings = async (settingsArray: {key: string, value: string}[]) => {
  const { data } = await api.put('/settings/config', { settings: settingsArray });
  return data;
};

export const getLiveStatus = async () => {
  const { data } = await api.get('/settings/config/live-status');
  return data;
};

export const setupTelegramWebhook = async (baseUrl?: string, botToken?: string, tenantSlug?: string) => {
  const payload: { base_url?: string; bot_token?: string; tenant_slug?: string } = {};
  if (baseUrl) payload.base_url = baseUrl;
  if (botToken) payload.bot_token = botToken;
  if (tenantSlug) payload.tenant_slug = tenantSlug;
  const { data } = await api.post('/telegram/setup-webhook', payload);
  return data;
};

export const globalSearch = async (query: string) => {
  const { data } = await api.get(`/system/search?q=${encodeURIComponent(query)}`);
  return data;
};

export const exportDatabaseBackup = async () => {
  const response = await api.get('/system/backup', {
    responseType: 'blob',
  });
  return response.data;
};

export const importDatabaseRestore = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await api.post('/system/restore', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return data;
};

// --- Contacts & Dictionary Export/Import ---

export const exportContacts = async () => {
  const response = await api.get('/contacts/export', {
    responseType: 'blob',
  });
  return response.data;
};

export const importContacts = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await api.post('/contacts/import', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return data;
};

export const exportDictionary = async () => {
  const response = await api.get('/knowledge/dictionary/export', {
    responseType: 'blob',
  });
  return response.data;
};

export const importDictionary = async (file: File, isGlobal: boolean = false) => {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await api.post(`/knowledge/dictionary/import?is_global=${isGlobal}`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return data;
};


// --- Chat & Bot Manual Takeover ---

export const getChatSessions = async () => {
  const { data } = await api.get('/chat/sessions');
  return data;
};

export const getChatSession = async (sessionId: number) => {
  const { data } = await api.get(`/chat/sessions/${sessionId}`);
  return data;
};

export const sendOperatorMessage = async (sessionId: number, message: string) => {
  const { data } = await api.post(`/chat/sessions/${sessionId}/message`, { message });
  return data;
};

export const toggleAutopilot = async (sessionId: number, autopilot: boolean) => {
  const { data } = await api.put(`/chat/sessions/${sessionId}/autopilot`, { autopilot });
  return data;
};

export const deleteChatSession = async (sessionId: number) => {
  const { data } = await api.delete(`/chat/sessions/${sessionId}`);
  return data;
};

// --- Identity ---
export const getIdentity = async () => {
  const { data } = await api.get('/settings/identity');
  return data;
};

export const updateIdentity = async (identity: any) => {
  const { data } = await api.put('/settings/identity', identity);
  return data;
};

export const uploadIdentityKml = async (formData: FormData) => {
  const { data } = await api.post('/settings/identity/kml', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return data;
};

export const deleteIdentityKml = async () => {
  const { data } = await api.delete('/settings/identity/kml');
  return data;
};

export const uploadIdentityLogo = async (formData: FormData) => {
  const { data } = await api.post('/settings/identity/logo', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return data;
};

export const deleteIdentityLogo = async () => {
  const { data } = await api.delete('/settings/identity/logo');
  return data;
};

// --- Locations ---
export const getLocations = async () => {
  const { data } = await api.get('/settings/locations');
  return data;
};

export const createLocation = async (location: any) => {
  const { data } = await api.post('/settings/locations', location);
  return data;
};

export const updateLocation = async (id: number, location: any) => {
  const { data } = await api.put(`/settings/locations/${id}`, location);
  return data;
};

export const deleteLocation = async (id: number) => {
  const { data } = await api.delete(`/settings/locations/${id}`);
  return data;
};

export const uploadLocationIcon = async (formData: FormData) => {
  const { data } = await api.post('/settings/locations/icon', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return data;
};

// --- Classifications ---
export const getClassifications = async () => {
  const { data } = await api.get('/settings/classifications');
  return data;
};

export const createClassification = async (classification: any) => {
  const { data } = await api.post('/settings/classifications', classification);
  return data;
};

export const updateClassification = async (id: number, classification: any) => {
  const { data } = await api.put(`/settings/classifications/${id}`, classification);
  return data;
};

export const deleteClassification = async (id: number) => {
  const { data } = await api.delete(`/settings/classifications/${id}`);
  return data;
};

// --- Users ---
export const getUsers = async () => {
  const { data } = await api.get('/settings/users');
  return data;
};

export const createUser = async (user: any) => {
  const { data } = await api.post('/settings/users', user);
  return data;
};

export const updateUser = async (id: number, user: any) => {
  const { data } = await api.put(`/settings/users/${id}`, user);
  return data;
};

export const deleteUser = async (id: number) => {
  const { data } = await api.delete(`/settings/users/${id}`);
  return data;
};

// --- Ollama & AI Connection ---
export const getOllamaModels = async (baseUrl?: string) => {
  const { data } = await api.get('/settings/ollama-models', {
    params: baseUrl ? { base_url: baseUrl } : undefined,
  });
  return data;
};

export const testAiConnection = async (payload: { provider: string; api_key?: string; base_url?: string; engine_type?: 'llm' | 'embed' | 'stt' }) => {
  const { data } = await api.post('/settings/ai-test-connection', payload);
  return data;
};

// --- SOP Documents ---
export const getSopDocuments = async () => {
  const { data } = await api.get('/knowledge/sop');
  return data;
};

export const uploadSopDocument = async (formData: FormData) => {
  const { data } = await api.post('/knowledge/sop/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return data;
};

export const vectorizeSopDocument = async (docId: number, isGlobal: boolean = false) => {
  const { data } = await api.post(`/knowledge/sop/${docId}/vectorize?is_global=${isGlobal}`);
  return data;
};

export const deleteSopDocument = async (docId: number, isGlobal: boolean = false) => {
  const { data } = await api.delete(`/knowledge/sop/${docId}?is_global=${isGlobal}`);
  return data;
};

// --- Info Awal & Group Broadcast ---
export const generateInfoAwal = async (reportId: number, manualData: Record<string, string>) => {
  const { data } = await api.post(`/reports/${reportId}/generate-info-awal`, manualData);
  return data;
};

export const sendBroadcast = async (reportId: number, text: string) => {
  const { data } = await api.post(`/reports/${reportId}/send-broadcast`, { text });
  return data;
};

// --- Public APIs ---
export const getPublicMapReports = async () => {
  const { data } = await api.get('/public/reports/map');
  return data;
};

// --- Super Admin Tenant Management ---
export const getTenants = async () => {
  const { data } = await api.get('/admin/tenants');
  return data;
};

export const createTenant = async (tenantData: any) => {
  const { data } = await api.post('/admin/tenants', tenantData);
  return data;
};

export const updateTenantStatus = async (id: number, isActive: boolean) => {
  const { data } = await api.put(`/admin/tenants/${id}`, { is_active: isActive });
  return data;
};

export const updateTenant = async (id: number, tenantData: any) => {
  const { data } = await api.put(`/admin/tenants/${id}`, tenantData);
  return data;
};

export const deleteTenant = async (id: number) => {
  const { data } = await api.delete(`/admin/tenants/${id}`);
  return data;
};

export const testTenantConnection = async (id: number) => {
  const { data } = await api.post(`/admin/tenants/${id}/test`);
  return data;
};

export const getGlobalReports = async () => {
  const { data } = await api.get('/admin/reports');
  return data;
};

export const getNationalReports = async (params?: {
  status?: string;
  search?: string;
  jenis_kejadian?: string;
  tenant_slug?: string;
  skip?: number;
  limit?: number;
}) => {
  const { data } = await api.get('/national/reports', { params });
  return data;
};

export const getNationalStats = async () => {
  const { data } = await api.get('/national/stats');
  return data;
};

export const getPublicTenants = async () => {
  const { data } = await api.get('/public/tenants');
  return data;
};

export const registerUser = async (userData: any, tenantSlug: string) => {
  const { data } = await api.post('/auth/register', userData, {
    headers: {
      'X-Tenant-Slug': tenantSlug,
    },
  });
  return data;
};


// --- Storage Management APIs ---
export const getStorageStats = async () => {
  const { data } = await api.get('/storage/stats');
  return data;
};

export const listStorageFiles = async (params?: { category?: string; limit?: number; skip?: number }) => {
  const { data } = await api.get('/storage/files', { params });
  return data;
};

export const deleteStorageFile = async (filepath: string) => {
  const { data } = await api.delete(`/storage/files/${filepath}`);
  return data;
};

export const cleanupStorageFiles = async () => {
  const { data } = await api.post('/storage/cleanup');
  return data;
};



