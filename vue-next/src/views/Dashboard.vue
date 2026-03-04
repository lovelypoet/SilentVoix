<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import { useMonitoringDashboard } from '../composables/useMonitoringDashboard'

const router = useRouter()

const {
  monitoring,
  isLoading,
  refreshError,
  lastUpdated,
  healthTone,
  refresh,
} = useMonitoringDashboard()

const overviewBadgeClass = computed(() => {
  if (healthTone.value === 'critical') return 'badge-critical'
  if (healthTone.value === 'warning') return 'badge-warning'
  if (healthTone.value === 'healthy') return 'badge-healthy'
  return 'badge-neutral'
})

const formattedLastUpdated = computed(() => {
  if (!lastUpdated.value) return 'Never'
  return lastUpdated.value.toLocaleString()
})

const latestAlerts = computed(() => monitoring.value?.alerts?.latest || [])
const topShiftedFeatures = computed(() => monitoring.value?.drift?.top_shifted_features || [])
const segmentRegressions = computed(() => monitoring.value?.performance?.segment_regressions || [])
const events = computed(() => monitoring.value?.events || [])
const performanceTrend = computed(() => monitoring.value?.performance?.trend || [])
const runtimeServices = computed(() => monitoring.value?.runtime_services || [])

const statusLabel = computed(() => {
  const raw = monitoring.value?.health?.status || 'unknown'
  return String(raw).toUpperCase()
})

const formatPercent = (value, digits = 2) => `${Number(value || 0).toFixed(digits)}%`
const formatNumber = (value, digits = 2) => Number(value || 0).toFixed(digits)

const eventTimestamp = (raw) => {
  if (!raw) return 'Unknown time'
  const parsed = new Date(raw)
  if (Number.isNaN(parsed.getTime())) return 'Unknown time'
  return parsed.toLocaleString()
}

const gotoModelLibrary = () => router.push('/model-library')
const gotoPlayground = () => router.push('/realtime-ai-playground')
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
      <div>
        <h1 class="text-3xl font-bold text-white">Model Monitoring</h1>
        <p class="text-sm text-slate-400">Production status, data quality, and prediction performance.</p>
      </div>
      <div class="flex items-center gap-3">
        <BaseBtn variant="secondary" @click="gotoModelLibrary">Open Model Library</BaseBtn>
        <BaseBtn variant="primary" @click="refresh">Refresh Now</BaseBtn>
      </div>
    </div>

    <BaseCard class="monitoring-overview">
      <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <p class="text-xs uppercase tracking-widest text-slate-400">Environment</p>
          <h2 class="text-2xl font-bold text-white mt-1">Production Monitor</h2>
          <p class="text-sm text-slate-300 mt-2">Window: {{ monitoring.meta?.window || '24h' }} | Last updated: {{ formattedLastUpdated }}</p>
        </div>
        <div class="flex items-center gap-2">
          <span class="status-dot" :class="overviewBadgeClass"></span>
          <span class="status-label" :class="overviewBadgeClass">{{ statusLabel }}</span>
        </div>
      </div>
      <p v-if="refreshError" class="text-rose-300 text-sm mt-3">{{ refreshError }}</p>
      <p v-if="isLoading" class="text-slate-400 text-sm mt-3">Loading monitoring data...</p>
    </BaseCard>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <BaseCard class="monitor-card">
        <p class="card-title">Active Alerts</p>
        <div class="grid grid-cols-3 gap-3 mt-3">
          <div>
            <p class="metric-label">Open</p>
            <p class="metric-value">{{ monitoring.alerts?.open_total ?? 0 }}</p>
          </div>
          <div>
            <p class="metric-label">Critical</p>
            <p class="metric-value text-rose-300">{{ monitoring.alerts?.critical ?? 0 }}</p>
          </div>
          <div>
            <p class="metric-label">Warning</p>
            <p class="metric-value text-amber-300">{{ monitoring.alerts?.warning ?? 0 }}</p>
          </div>
        </div>
        <div class="mt-3 space-y-2">
          <p v-for="alert in latestAlerts.slice(0, 2)" :key="alert.id || alert.timestamp" class="text-sm text-slate-300">
            {{ alert.title }}: {{ alert.message }}
          </p>
          <p v-if="latestAlerts.length === 0" class="text-sm text-slate-500">No active alerts.</p>
        </div>
      </BaseCard>

      <BaseCard class="monitor-card">
        <p class="card-title">Model Version & Rollout</p>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
          <div>
            <p class="metric-label">Active Version</p>
            <p class="metric-value mono">{{ monitoring.model?.active_version || 'unavailable' }}</p>
          </div>
          <div>
            <p class="metric-label">Previous Version</p>
            <p class="metric-value mono">{{ monitoring.model?.previous_version || 'n/a' }}</p>
          </div>
          <div>
            <p class="metric-label">Rollout</p>
            <p class="metric-value">{{ formatPercent(monitoring.model?.rollout_percent || 0, 0) }}</p>
          </div>
          <div>
            <p class="metric-label">Last Deploy</p>
            <p class="metric-value">{{ eventTimestamp(monitoring.model?.last_deploy_at) }}</p>
          </div>
        </div>
        <div class="mt-4 space-y-2">
          <p class="metric-label">Runtime Services</p>
          <div
            v-for="service in runtimeServices"
            :key="service.name"
            class="flex items-center justify-between text-sm"
          >
            <span class="text-slate-200">{{ service.name }}</span>
            <span :class="service.ok ? 'text-emerald-300' : 'text-rose-300'">
              {{ service.ok ? 'Healthy' : 'Unavailable' }}
            </span>
          </div>
          <p v-if="runtimeServices.length === 0" class="text-sm text-slate-500">Runtime checks disabled.</p>
        </div>
      </BaseCard>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <BaseCard class="monitor-card">
        <p class="metric-label">Latency p95</p>
        <p class="metric-value">{{ formatNumber(monitoring.health?.latency_p95_ms, 2) }} ms</p>
      </BaseCard>
      <BaseCard class="monitor-card">
        <p class="metric-label">Error Rate (5m)</p>
        <p class="metric-value">{{ formatPercent(monitoring.health?.error_rate_5m, 2) }}</p>
      </BaseCard>
      <BaseCard class="monitor-card">
        <p class="metric-label">Throughput</p>
        <p class="metric-value">{{ formatNumber(monitoring.health?.throughput_rpm, 2) }} rpm</p>
      </BaseCard>
      <BaseCard class="monitor-card">
        <p class="metric-label">Uptime (24h)</p>
        <p class="metric-value">{{ formatPercent(monitoring.health?.uptime_24h, 2) }}</p>
      </BaseCard>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <BaseCard class="monitor-card">
        <p class="card-title">Traffic Volume</p>
        <div class="grid grid-cols-3 gap-3 mt-3">
          <div>
            <p class="metric-label">Last 5m</p>
            <p class="metric-value">{{ monitoring.traffic?.requests_last_5m ?? 0 }}</p>
          </div>
          <div>
            <p class="metric-label">Last 24h</p>
            <p class="metric-value">{{ monitoring.traffic?.requests_last_24h ?? 0 }}</p>
          </div>
          <div>
            <p class="metric-label">Delta</p>
            <p class="metric-value">{{ formatPercent(monitoring.traffic?.trend_delta_pct, 2) }}</p>
          </div>
        </div>
      </BaseCard>

      <BaseCard class="monitor-card">
        <p class="card-title">Data Quality</p>
        <div class="grid grid-cols-3 gap-3 mt-3">
          <div>
            <p class="metric-label">Missing Ratio</p>
            <p class="metric-value">{{ formatPercent((monitoring.data_quality?.missing_ratio || 0) * 100, 2) }}</p>
          </div>
          <div>
            <p class="metric-label">Schema Mismatch</p>
            <p class="metric-value">{{ monitoring.data_quality?.schema_mismatch_count ?? 0 }}</p>
          </div>
          <div>
            <p class="metric-label">Drop Rate</p>
            <p class="metric-value">{{ formatPercent((monitoring.data_quality?.drop_rate || 0) * 100, 2) }}</p>
          </div>
        </div>
      </BaseCard>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <BaseCard class="monitor-card">
        <p class="card-title">Drift</p>
        <p class="text-sm text-slate-400 mt-1">Global score: {{ formatPercent((monitoring.drift?.global_score || 0) * 100, 2) }}</p>
        <div class="mt-3 space-y-2">
          <div
            v-for="item in topShiftedFeatures"
            :key="item.feature"
            class="flex items-center justify-between text-sm"
          >
            <span class="text-slate-200">{{ item.feature }}</span>
            <span class="text-amber-300">{{ formatPercent(item.shift, 2) }}</span>
          </div>
          <p v-if="topShiftedFeatures.length === 0" class="text-sm text-slate-500">No drift contributors yet.</p>
        </div>
      </BaseCard>

      <BaseCard class="monitor-card">
        <p class="card-title">Performance Trend ({{ monitoring.performance?.metric_name || 'metric' }})</p>
        <p class="text-sm text-slate-400 mt-1">Current: {{ formatPercent((monitoring.performance?.current_value || 0) * 100, 2) }}</p>
        <div class="trend-bars mt-3">
          <div
            v-for="point in performanceTrend.slice(-20)"
            :key="point.timestamp"
            class="trend-bar"
            :style="{ height: `${Math.max(8, Math.min(100, (Number(point.value || 0) * 100)))}%` }"
            :title="`${point.timestamp} | ${formatPercent((point.value || 0) * 100, 2)}`"
          ></div>
        </div>
        <div class="mt-3 space-y-1">
          <p v-for="segment in segmentRegressions.slice(0, 3)" :key="segment.segment" class="text-sm text-slate-300">
            {{ segment.segment }}: {{ formatPercent(segment.impact, 2) }} impact
          </p>
          <p v-if="segmentRegressions.length === 0" class="text-sm text-slate-500">No segment regressions available.</p>
        </div>
      </BaseCard>
    </div>

    <BaseCard class="monitor-card">
      <div class="flex items-center justify-between gap-3">
        <p class="card-title">Recent Monitoring Events</p>
        <BaseBtn variant="secondary" @click="gotoPlayground">Open Runtime Playground</BaseBtn>
      </div>
      <div class="mt-4 space-y-2">
        <div
          v-for="event in events.slice(0, 8)"
          :key="`${event.type}-${event.timestamp}`"
          class="event-row"
        >
          <div>
            <p class="text-sm text-slate-200">{{ event.message }}</p>
            <p class="text-xs text-slate-500">{{ event.type }}</p>
          </div>
          <p class="text-xs text-slate-500">{{ eventTimestamp(event.timestamp) }}</p>
        </div>
        <p v-if="events.length === 0" class="text-sm text-slate-500">No events recorded.</p>
      </div>
    </BaseCard>
  </div>
</template>

<style scoped>
.monitoring-overview {
  background: radial-gradient(1400px 460px at -10% -20%, rgba(20, 184, 166, 0.22), transparent 62%),
    radial-gradient(900px 360px at 120% -10%, rgba(251, 191, 36, 0.16), transparent 58%),
    linear-gradient(125deg, rgba(15, 23, 42, 0.92), rgba(30, 41, 59, 0.85));
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.monitor-card {
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.78), rgba(15, 23, 42, 0.48));
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.card-title {
  color: #f8fafc;
  font-size: 1rem;
  font-weight: 700;
}

.metric-label {
  color: #94a3b8;
  font-size: 0.75rem;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.metric-value {
  color: #f8fafc;
  font-size: 1.45rem;
  font-weight: 700;
  margin-top: 0.25rem;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 1rem;
}

.status-dot {
  width: 0.7rem;
  height: 0.7rem;
  border-radius: 9999px;
}

.status-label {
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 0.25rem 0.55rem;
  border-radius: 9999px;
  border: 1px solid transparent;
}

.badge-healthy {
  background: rgba(16, 185, 129, 0.2);
  color: #6ee7b7;
  border-color: rgba(16, 185, 129, 0.4);
}

.badge-warning {
  background: rgba(245, 158, 11, 0.2);
  color: #fcd34d;
  border-color: rgba(245, 158, 11, 0.4);
}

.badge-critical {
  background: rgba(244, 63, 94, 0.22);
  color: #fda4af;
  border-color: rgba(244, 63, 94, 0.4);
}

.badge-neutral {
  background: rgba(148, 163, 184, 0.2);
  color: #cbd5e1;
  border-color: rgba(148, 163, 184, 0.4);
}

.trend-bars {
  min-height: 120px;
  display: grid;
  grid-template-columns: repeat(20, minmax(0, 1fr));
  gap: 0.35rem;
  align-items: end;
}

.trend-bar {
  width: 100%;
  border-radius: 0.3rem;
  background: linear-gradient(180deg, rgba(20, 184, 166, 0.95), rgba(14, 116, 144, 0.9));
  min-height: 8px;
}

.event-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.55rem 0.25rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
}

.event-row:last-child {
  border-bottom: 0;
}

@media (max-width: 768px) {
  .trend-bars {
    grid-template-columns: repeat(10, minmax(0, 1fr));
  }
}
</style>
