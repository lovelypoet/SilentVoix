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
    const detail = error.response?.data?.detail || error.response?.data?.message || error.message;
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
    getSummary: () => api.get('/gestures/summary'),
    create: (payload) => api.post('/gestures/', payload),
    delete: (sessionId) => api.delete(`/gestures/${sessionId}`),
    update: (sessionId, label) => api.put(`/gestures/${sessionId}?label=${label}`),
  },

  // ===================== Training API (Deprecated — lateFusion only) =====================
  training: {
    getDataInfo: () => api.get('/training/data/info'),
    lateFusion: {
      run: (mode = 'single', gloveWeight = 0.8) =>
        api.post(`/training/late-fusion/run?mode=${mode}&glove_weight=${gloveWeight}`),
      getJob: (jobId) =>
        api.get(`/training/late-fusion/jobs/${jobId}`),
      getLatest: (mode = 'single') =>
        api.get(`/training/late-fusion/latest?mode=${mode}`),
      predict: (payload) =>
        api.post('/training/late-fusion/predict', payload),
      downloadLatestArtifact: (mode = 'single', artifact = 'report') =>
        api.get(`/training/late-fusion/latest/artifact?mode=${mode}&artifact=${artifact}`, { responseType: 'blob' })
    },
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
    latestSensorFrame: () => api.get('/gesture/latest'),
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

  fusionPreprocess: {
    health: () => api.get('/fusion-preprocess/health'),
    analyzeCsv: (payload) => api.post('/fusion-preprocess/jobs/analyze', payload),
    analyzeUpload: (payload) => {
      const formData = new FormData()
      formData.append('source_file', payload.source_file)
      if (payload.options?.trim_start_ms !== null && payload.options?.trim_start_ms !== undefined) {
        formData.append('trim_start_ms', String(payload.options.trim_start_ms))
      }
      if (payload.options?.trim_end_ms !== null && payload.options?.trim_end_ms !== undefined) {
        formData.append('trim_end_ms', String(payload.options.trim_end_ms))
      }
      if (payload.options?.max_abs_sensor_delta_ms !== null && payload.options?.max_abs_sensor_delta_ms !== undefined) {
        formData.append('max_abs_sensor_delta_ms', String(payload.options.max_abs_sensor_delta_ms))
      }
      formData.append('require_sensor_match', payload.options?.require_sensor_match ? 'true' : 'false')
      formData.append('export_label', payload.options?.export_label || 'processed')
      formData.append('notes', payload.options?.notes || '')
      formData.append('csv_file', payload.csv_file)
      if (payload.video_file) {
        formData.append('video_file', payload.video_file)
      }
      return api.post('/fusion-preprocess/jobs/analyze-upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
    },
    getJob: (jobId) => api.get(`/fusion-preprocess/jobs/${jobId}`),
    saveJobOutput: (jobId, payload = {}) => api.post(`/fusion-preprocess/jobs/${jobId}/save`, payload)
  },

  // ===================== Admin CSV Library API =====================
  admin: {
    csvLibrary: {
      listFiles: (includeArchived = false) =>
        api.get(`/admin/csv-library/files?include_archived=${includeArchived ? 'true' : 'false'}`),
      listCompatible: (pipeline = 'early', mode = 'single', includeArchived = false) =>
        api.get(`/admin/csv-library/compatible?pipeline=${pipeline}&mode=${mode}&include_archived=${includeArchived ? 'true' : 'false'}`),
      selection: {
        get: (pipeline = 'early', mode = 'single') =>
          api.get(`/admin/csv-library/selection?pipeline=${pipeline}&mode=${mode}`),
        getAll: () =>
          api.get('/admin/csv-library/selection/all'),
        set: (name, pipeline = 'early', mode = 'single', modality = null) =>
          api.post('/admin/csv-library/selection', { name, pipeline, mode, modality })
      },
      preview: (name, limit = 100, offset = 0) =>
        api.get(`/admin/csv-library/files/${name}/preview?limit=${limit}&offset=${offset}`),
      stats: (name) =>
        api.get(`/admin/csv-library/files/${name}/stats`),
      compatibility: (name, pipeline = 'early', mode = 'single') =>
        api.get(`/admin/csv-library/files/${name}/compatibility?pipeline=${pipeline}&mode=${mode}`),
      review: (name, decision, notes = '') =>
        api.post(`/admin/csv-library/files/${name}/review`, { decision, notes }),
      reorder: (names) =>
        api.post('/admin/csv-library/files/reorder', { names }),
      archive: (name) =>
        api.post(`/admin/csv-library/files/${name}/archive`),
      deletePermanent: (name, confirmName) =>
        api.delete(`/admin/csv-library/files/${name}`, { data: { confirm_name: confirmName } }),
      download: (name) =>
        api.get(`/admin/csv-library/files/${name}/download`, { responseType: 'blob' }),
      getInsights: () =>
        api.get('/admin/csv-library/insights')
    }
  },

  // ===================== Dashboard API =====================
  dashboard: {
    legacy: () => api.get('/dashboard'),
    monitoring: (window = null) =>
      api.get('/dashboard/monitoring', window ? { params: { window } } : undefined),
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
  },

  // ===================== Realtime AI Playground API =====================
  modelLibrary: {
    uploadModel: (modelFile, metadataFile, modelClassFile = null, isStateDict = false) => {
      const formData = new FormData();
      formData.append('model_file', modelFile);
      formData.append('metadata_file', metadataFile);
      if (isStateDict) {
        formData.append('is_state_dict', 'true');
      }
      if (modelClassFile) {
        formData.append('model_class_file', modelClassFile);
      }
      return api.post('/model-library/models/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
    },
    listModels: () => api.get('/model-library/models'),
    reorderModels: (modelIds) => api.post('/model-library/models/reorder', { model_ids: modelIds }),
    getActiveModel: () => api.get('/model-library/models/active'),
    activateModel: (modelId) => api.post(`/model-library/models/${modelId}/activate`),
    runtimeCheckModel: (modelId) => api.get(`/model-library/models/${modelId}/runtime-check`),
    deleteModel: (modelId) => api.delete(`/model-library/models/${modelId}`),
    downloadModelArtifact: (modelId, kind = 'model') =>
      api.get(`/model-library/models/${modelId}/download?kind=${kind}`, { responseType: 'blob' }),
    predictCv: (payload) =>
      api.post('/model-library/predict/cv', payload),
    predictSensor: (payload) =>
      api.post('/model-library/predict/sensor', payload),
    predictIntegrated: (imageData) =>
      api.post('/predict/integrated', { image_data: imageData }),
    getIntegratedDetector: () =>
      api.get('/predict/integrated/detector'),
    setIntegratedDetector: (modelId) =>
      api.post(`/predict/integrated/detector/${modelId}`)
  },
  // ===================== Model Feedback API =====================
  modelFeedback: {
    submit: (payload) => api.post('/model-library/feedback', payload),
    getStats: (modelId) => api.get(`/model-library/feedback/stats/${modelId}`),
  }
};
