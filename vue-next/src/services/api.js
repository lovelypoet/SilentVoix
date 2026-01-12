import axios from 'axios';

// Use same base URL logic or default to /api since we have the proxy set up
const BASE_URL = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token if needed
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for clean error handling
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const detail = error.response?.data?.detail || error.message;
    console.error('API Error:', detail);
    return Promise.reject(error);
  }
);

export default {
  // ===================== Auth API =====================
  auth: {
    login: (email, password) => api.post('/auth/login', { email, password }),
    logout: () => api.post('/auth/logout'),
    me: () => api.get('/auth/me'),
  },

  // ===================== Gesture API =====================
  gestures: {
    getAll: () => api.get('/gestures'),
    create: (payload) => api.post('/gestures/', payload),
    delete: (sessionId) => api.delete(`/gestures/${sessionId}`),
    update: (sessionId, label) => api.put(`/gestures/${sessionId}?label=${label}`),
  },

  // ===================== Training API =====================
  training: {
    getResults: () => api.get('/training/'),
    getLatestResult: () => api.get('/training/latest'),
    getMetrics: () => api.get('/training/metrics/latest'),
    trigger: (dualHand = false) => api.post(`/training/trigger?dual_hand=${dualHand}`),
    run: (file, dualHand = false) => {
      const formData = new FormData();
      formData.append('file', file);
      return api.post(`/training/run?dual_hand=${dualHand}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
    },
    // Dual Hand
    triggerDual: () => api.post('/training/dual-hand/trigger'),
    runDual: (file) => {
      const formData = new FormData();
      formData.append('file', file);
      return api.post('/training/dual-hand/run', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
    },
    getDualData: () => api.get('/training/dual-hand/data'),
    getDataInfo: () => api.get('/training/data/info'),
    // Conversion
    convertToDual: (sessionId) => api.post(`/training/convert-to-dual-hand/${sessionId}`),
    checkConversion: (sessionId) => api.get(`/training/conversion-status/${sessionId}`),
  },

  // ===================== Audio API =====================
  audio: {
    getAll: () => api.get('/audio-files/'),
    upload: (file, uploader = 'unknown') => {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('uploader', uploader);
      return api.post('/audio-files/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
    },
    delete: (filename) => api.delete(`/audio-files/${filename}`),
    playESP32: (filename) => api.post(`/audio-files/${filename}/play`),
    playLaptop: (filename) => api.post(`/audio-files/${filename}/play-laptop`),
  },

  // ===================== WebSocket Helper =====================
  createWebSocket(path = '/ws') {
    const token = localStorage.getItem('access_token');
    // Replace http/https with ws/wss
    const wsUrl = BASE_URL.replace(/^http/, 'ws') + path + (token ? `?token=${token}` : '');
    return new WebSocket(wsUrl);
  }
};
