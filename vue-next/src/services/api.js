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
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    const detail = error.response?.data?.detail || error.message;
    console.error('API Error:', detail);
    return Promise.reject(error);
  }
);

export default {
  // ===================== Auth API =====================
  auth: {
    login: (email, password) => api.post('/auth/login', { email, password }),
    register: (email, password) => api.post('/auth/register', { email, password }),
    logout: () => api.post('/auth/logout'),
    me: () => api.get('/auth/me'),
    updateProfile: (payload) => api.put('/auth/me', payload), // Changed to PUT request for updating profile
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

  // ===================== Utils & TTS API =====================
  utils: {
    // Health
    health: () => api.get('/utils/health'),
    serialStatus: () => api.get('/utils/serial-status'),
    serialConfig: {
      update: (payload) => api.post('/utils/serial-config', payload),
      auto: () => api.post('/utils/serial-config', { auto_detect: true }),
    },
    collectorLogs: (mode = 'single', lines = 200) => api.get(`/utils/collector/logs?mode=${mode}&lines=${lines}`),
    // TTS
    tts: {
      speakOnGlove: (text) => api.post('/utils/test_tts_to_esp32', { text }),
      speakTest: (text, playOnLaptop = false) => {
        const token = localStorage.getItem('access_token')
        return api.post('/utils/tts/test', null, {
          params: {
            text,
            play_on_laptop: playOnLaptop
          },
          headers: token ? { Authorization: `Bearer ${token}` } : {}
        })
      },

      getLanguages: () => api.get('/utils/tts/languages'),
      setLanguage: (language) => api.post(`/utils/tts/language?language=${language}`),
      getConfig: () => api.get('/utils/tts/config'),
    }
  },

  // ===================== Capture Controls API =====================
  captureControls: {
    sensorCapture: {
      start: (mode = 'single', maxSamples = null) => {
        const params = new URLSearchParams({ mode })
        if (Number.isInteger(maxSamples) && maxSamples > 0) {
          params.set('max_samples', String(maxSamples))
        }
        return api.post(`/capture-controls/sensor-capture/start?${params.toString()}`)
      },
      stop: () => api.post('/capture-controls/sensor-capture/stop'),
      status: () => api.get('/capture-controls/sensor-capture/status'),
    }
  },

  // ===================== Sync API =====================
  sync: {
    sensorWindow: (mode = 'single', startMs, endMs, padMs = 0) =>
      api.get(`/sync/sensor-window?mode=${mode}&start_ms=${startMs}&end_ms=${endMs}&pad_ms=${padMs}`)
  },

  // ===================== WebSocket Helper =====================
  createWebSocket(path = '/ws') {
    const token = localStorage.getItem('access_token');
    let wsOrigin = '';
    if (BASE_URL && /^https?:\/\//.test(BASE_URL)) {
      wsOrigin = BASE_URL.replace(/^http/, 'ws');
    } else if (import.meta.env.DEV) {
      wsOrigin = `ws://${window.location.hostname}:8000`;
    } else {
      wsOrigin = window.location.origin.replace(/^http/, 'ws');
    }
    // /ws/stream is intentionally public; avoid auth query param so expired tokens
    // never break websocket handshake in the training UI.
    const includeToken = path !== '/ws/stream';
    const wsUrl = wsOrigin + path + (includeToken && token ? `?token=${token}` : '');
    return new WebSocket(wsUrl);
  }
};
