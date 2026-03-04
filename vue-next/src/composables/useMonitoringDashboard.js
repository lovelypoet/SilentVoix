import { computed, onMounted, onUnmounted, ref } from 'vue'
import api from '../services/api'

const BASE_INTERVAL_MS = 30_000
const MAX_INTERVAL_MS = 120_000

const createDefaultState = () => ({
  health: {
    status: 'unknown',
    uptime_24h: 0,
    error_rate_5m: 0,
    latency_p95_ms: 0,
    throughput_rpm: 0,
  },
  alerts: {
    open_total: 0,
    critical: 0,
    warning: 0,
    latest: [],
  },
  model: {
    active_version: 'unavailable',
    previous_version: 'n/a',
    rollout_percent: 0,
    last_deploy_at: null,
  },
  runtime_services: [],
  traffic: {
    requests_last_5m: 0,
    requests_last_24h: 0,
    trend_delta_pct: 0,
  },
  data_quality: {
    missing_ratio: 0,
    schema_mismatch_count: 0,
    drop_rate: 0,
  },
  drift: {
    global_score: 0,
    top_shifted_features: [],
  },
  performance: {
    metric_name: 'accuracy',
    window: '24h',
    current_value: 0,
    trend: [],
    segment_regressions: [],
  },
  events: [],
  meta: {
    window: '24h',
    generated_at: null,
  },
})

export const useMonitoringDashboard = () => {
  const monitoring = ref(createDefaultState())
  const isLoading = ref(true)
  const refreshError = ref('')
  const lastUpdated = ref(null)
  const pollIntervalMs = ref(BASE_INTERVAL_MS)

  let pollTimer = null

  const healthTone = computed(() => {
    const status = monitoring.value?.health?.status || 'unknown'
    if (status === 'critical') return 'critical'
    if (status === 'warning') return 'warning'
    if (status === 'healthy') return 'healthy'
    return 'neutral'
  })

  const clearTimer = () => {
    if (pollTimer) {
      clearTimeout(pollTimer)
      pollTimer = null
    }
  }

  const queueNextPoll = () => {
    clearTimer()
    pollTimer = setTimeout(() => {
      fetchMonitoringData({ silent: true })
    }, pollIntervalMs.value)
  }

  const fetchMonitoringData = async ({ silent = false } = {}) => {
    if (!silent) {
      isLoading.value = true
    }

    try {
      refreshError.value = ''
      const response = await api.dashboard.monitoring()
      const payload = response?.data || createDefaultState()
      monitoring.value = {
        ...createDefaultState(),
        ...payload,
      }
      lastUpdated.value = new Date()
      pollIntervalMs.value = BASE_INTERVAL_MS
    } catch (error) {
      const status = error?.response?.status
      if (status === 401) {
        refreshError.value = 'Authentication expired. Please log in again.'
      } else if (status === 403) {
        refreshError.value = 'You do not have permission to view monitoring data.'
      } else {
        refreshError.value = 'Unable to refresh monitoring dashboard right now.'
      }
      pollIntervalMs.value = Math.min(MAX_INTERVAL_MS, pollIntervalMs.value * 2)
    } finally {
      isLoading.value = false
      queueNextPoll()
    }
  }

  onMounted(() => {
    fetchMonitoringData()
  })

  onUnmounted(() => {
    clearTimer()
  })

  return {
    monitoring,
    isLoading,
    refreshError,
    lastUpdated,
    healthTone,
    refresh: () => fetchMonitoringData(),
  }
}
