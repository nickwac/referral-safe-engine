import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const ACCESS_TOKEN_KEY = 'admin_access_token';
const ADMIN_SESSION_KEY = 'admin_session';

let accessToken = localStorage.getItem(ACCESS_TOKEN_KEY) || '';

const api = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const setAccessToken = (token) => {
  accessToken = token || '';
  if (accessToken) {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  } else {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
  }
};

export const getAccessToken = () => accessToken;

export const saveAdminSession = (admin) => {
  localStorage.setItem(ADMIN_SESSION_KEY, JSON.stringify(admin));
};

export const getSavedAdminSession = () => {
  const raw = localStorage.getItem(ADMIN_SESSION_KEY);
  return raw ? JSON.parse(raw) : null;
};

export const clearAdminSession = () => {
  setAccessToken('');
  localStorage.removeItem(ADMIN_SESSION_KEY);
};

api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest?._retry && !String(originalRequest?.url || '').includes('/auth/')) {
      originalRequest._retry = true;
      try {
        const { data } = await api.post('/auth/refresh');
        setAccessToken(data.access_token);
        saveAdminSession({
          admin_id: data.admin_id,
          email: data.email,
          role: data.role,
          org_id: data.org_id,
          org_name: data.org_name,
        });
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
        return api(originalRequest);
      } catch (refreshError) {
        clearAdminSession();
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

export const loginAdmin = async ({ email, password }) => {
  const { data } = await api.post('/auth/login', { email, password });
  setAccessToken(data.access_token);
  saveAdminSession({
    admin_id: data.admin_id,
    email: data.email,
    role: data.role,
    org_id: data.org_id,
    org_name: data.org_name,
  });
  return data;
};

export const getCurrentAdmin = async () => {
  const { data } = await api.get('/auth/me');
  const next = {
    admin_id: data.admin_id,
    email: data.email,
    role: data.role,
    org_id: data.org_id,
    org_name: data.org_name,
  };
  saveAdminSession(next);
  return next;
};

export const logoutAdmin = async () => {
  try {
    await api.post('/auth/logout');
  } finally {
    clearAdminSession();
  }
};

export const getSessions = async () => {
  const { data } = await api.get('/auth/sessions');
  return data;
};

export const revokeSession = async (sessionId) => {
  const { data } = await api.delete(`/auth/sessions/${sessionId}`);
  return data;
};

export const revokeOtherSessions = async () => {
  const { data } = await api.post('/auth/sessions/revoke-others');
  return data;
};

export const getMetrics = async () => {
  const { data } = await api.get('/dashboard/metrics');
  return data;
};

export const getFraudFlags = async () => {
  const { data } = await api.get('/fraud/flags');
  return data;
};

export const getUserGraph = async (userId) => {
  const { data } = await api.get(`/user/${userId}/graph`);
  return data;
};

export const getUserProfile = async (userId) => {
  const { data } = await api.get(`/user/${userId}/profile`);
  return data;
};

export const updateUserStatus = async (userId, payload) => {
  const { data } = await api.put(`/user/${userId}/status`, payload);
  return data;
};

export const getRewardConfig = async () => {
  const { data } = await api.get('/reward/config');
  return data;
};

export const updateRewardConfig = async (config) => {
  const { data } = await api.put('/reward/config', config);
  return data;
};

export const triggerSeed = async () => {
  const { data } = await api.post('/seed');
  return data;
};

export const getWebsocketUrl = () => {
  const token = getAccessToken();
  if (!token) return null;
  const isSecure = window.location.protocol === 'https:';
  const wsProtocol = isSecure ? 'wss:' : 'ws:';
  const url = new URL(API_URL);
  return `${wsProtocol}//${url.host}/dashboard/stream?token=${encodeURIComponent(token)}`;
};

export const getRecentActivity = async () => {
  const { data } = await api.get('/dashboard/activity');
  return data;
};

export const searchUsers = async (q, limit = 10) => {
  const { data } = await api.get('/user/search', { params: { q, limit } });
  return data;
};

export const listUsers = async ({ limit = 25, offset = 0, status } = {}) => {
  const params = { limit, offset };
  if (status) params.status = status;
  const { data } = await api.get('/user', { params });
  return data;
};

export const getAuditLog = async ({ limit = 25, offset = 0, action, resource_type, actor_id } = {}) => {
  const params = { limit, offset };
  if (action) params.action = action;
  if (resource_type) params.resource_type = resource_type;
  if (actor_id) params.actor_id = actor_id;
  const { data } = await api.get('/admin/audit-log', { params });
  return data;
};

export const seedRewardConfig = async () => {
  const { data } = await api.post('/admin/seed-config');
  return data;
};

export const listOrganisations = async () => {
  const { data } = await api.get('/admin/orgs');
  return data;
};

export const createOrganisation = async (payload) => {
  const { data } = await api.post('/admin/orgs', payload);
  return data;
};

export default api;
