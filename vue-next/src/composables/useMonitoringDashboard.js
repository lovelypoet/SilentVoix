import { computed, onMounted, onUnmounted, ref } from 'vue'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'

const BASE_INTERVAL_MS = 30_000
const MIN_INTERVAL_MS = 10_000
const MAX_INTERVAL_MS = 120_000

// Stat-tile sparklines need a history, but the backend only reports current
// values for these fields (no server-side series). Rather than fabricate a
// trend, build a real one client-side from what each poll actually observes.
// Capped so a long-open tab doesn't grow this unbounded.
const HISTORY_LIMIT = 20
const HEALTH_METRICS = ['latency_p95_ms', 'error_rate_5m', 'throughput_rpm', 'uptime_24h']

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
  const authStore = useAuthStore()
  const monitoring = ref(createDefaultState())
  const isLoading = ref(true)
  const refreshError = ref('')
  const lastUpdated = ref(null)
  const pollIntervalMs = ref(BASE_INTERVAL_MS)
  const activeWindow = ref('24h')
  const healthHistory = ref(
    Object.fromEntries(HEALTH_METRICS.map((key) => [key, []]))
  )

  let pollTimer = null

  const applyUserDefaults = () => {
    const defaults = authStore.user?.operator_preferences?.dashboard_defaults
    const preferredWindow = String(defaults?.window || '24h')
    if (['1h', '6h', '24h', '7d'].includes(preferredWindow)) {
      activeWindow.value = preferredWindow
    } else {
      activeWindow.value = '24h'
    }

    const refreshSeconds = Number(defaults?.refresh_seconds || 30)
    const clampedMs = Math.min(MAX_INTERVAL_MS, Math.max(MIN_INTERVAL_MS, refreshSeconds * 1000))
    pollIntervalMs.value = clampedMs
  }

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
    // Stat-tile sparklines need a second point before they draw anything.
    // Rather than leave them empty for a full poll cycle, seed that second
    // reading quickly once, then fall back to the normal cadence.
    const hasSeedHistory = HEALTH_METRICS.every((key) => healthHistory.value[key].length >= 2)
    const delay = hasSeedHistory ? pollIntervalMs.value : Math.min(5000, pollIntervalMs.value)
    pollTimer = setTimeout(() => {
      fetchMonitoringData({ silent: true })
    }, delay)
  }

  const fetchMonitoringData = async ({ silent = false } = {}) => {
    if (!silent) {
      isLoading.value = true
    }

    try {
      refreshError.value = ''
      applyUserDefaults()
      const response = await api.dashboard.monitoring(activeWindow.value)
      const payload = response?.data || createDefaultState()
      monitoring.value = {
        ...createDefaultState(),
        ...payload,
      }
      lastUpdated.value = new Date()
      applyUserDefaults()

      const health = monitoring.value.health || {}
      for (const key of HEALTH_METRICS) {
        const value = Number(health[key])
        if (!Number.isFinite(value)) continue
        const series = healthHistory.value[key]
        series.push(value)
        if (series.length > HISTORY_LIMIT) series.shift()
      }
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
    applyUserDefaults()
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
    activeWindow,
    healthHistory,
    refresh: () => fetchMonitoringData(),
  }
}
