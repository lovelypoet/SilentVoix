<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { PhTimer, PhWarningCircle, PhArrowsLeftRight, PhShieldCheck } from '@phosphor-icons/vue'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import BasePageHeader from '../components/base/BasePageHeader.vue'
import BaseStatTile from '../components/base/BaseStatTile.vue'
import { useMonitoringDashboard } from '../composables/useMonitoringDashboard'

const router = useRouter()

const {
  monitoring,
  isLoading,
  refreshError,
  lastUpdated,
  healthTone,
  healthHistory,
  refresh,
} = useMonitoringDashboard()

const overviewBadgeClass = computed(() => {
  if (healthTone.value === 'critical') return 'status-badge-critical'
  if (healthTone.value === 'warning') return 'status-badge-warning'
  if (healthTone.value === 'healthy') return 'status-badge-healthy'
  return 'status-badge-neutral'
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

// Delta vs the previous poll, computed from the same client-side history the
// sparklines draw from - real observed change, not a fabricated trend.
const deltaFor = (key, digits, suffix) => {
  const series = healthHistory.value[key] || []
  if (series.length < 2) return { text: '', direction: 'neutral' }
  const diff = series[series.length - 1] - series[series.length - 2]
  if (Math.abs(diff) < Math.pow(10, -digits) / 2) return { text: 'flat', direction: 'neutral' }
  const direction = diff > 0 ? 'up' : 'down'
  const sign = diff > 0 ? '+' : ''
  return { text: `${sign}${diff.toFixed(digits)}${suffix}`, direction }
}

const latencyDelta = computed(() => deltaFor('latency_p95_ms', 2, 'ms'))
const errorRateDelta = computed(() => deltaFor('error_rate_5m', 2, '%'))
const throughputDelta = computed(() => deltaFor('throughput_rpm', 2, ' rpm'))
const uptimeDelta = computed(() => deltaFor('uptime_24h', 2, '%'))

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
    <BasePageHeader
      title="Model Monitoring"
      description="Production status, data quality, and prediction performance."
      eyebrow="Overview"
    >
      <template #actions>
        <BaseBtn variant="secondary" @click="gotoModelLibrary">Open Model Library</BaseBtn>
        <BaseBtn variant="primary" :disabled="isLoading" @click="refresh">
          {{ isLoading ? 'Refreshing...' : 'Refresh Now' }}
        </BaseBtn>
      </template>
    </BasePageHeader>

    <BaseCard>
      <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <p class="text-xs uppercase tracking-widest text-slate-500">Environment</p>
          <h2 class="text-lg font-semibold text-slate-100 mt-1">Production Monitor</h2>
          <p class="text-sm text-slate-400 mt-2">Window: {{ monitoring.meta?.window || '24h' }} | Last updated: {{ formattedLastUpdated }}</p>
        </div>
        <span class="status-badge" :class="overviewBadgeClass">{{ statusLabel }}</span>
      </div>
      <p v-if="refreshError" role="alert" class="text-danger-300 text-sm mt-3">{{ refreshError }}</p>
      <p v-if="isLoading" role="status" class="text-slate-400 text-sm mt-3">Loading monitoring data...</p>
    </BaseCard>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <BaseCard>
        <p class="card-title">Active Alerts</p>
        <div class="grid grid-cols-3 gap-3 mt-3">
          <div>
            <p class="stat-label">Open</p>
            <p class="stat-value">{{ monitoring.alerts?.open_total ?? 0 }}</p>
          </div>
          <div>
            <p class="stat-label">Critical</p>
            <p class="stat-value text-danger-300">{{ monitoring.alerts?.critical ?? 0 }}</p>
          </div>
          <div>
            <p class="stat-label">Warning</p>
            <p class="stat-value text-warning-300">{{ monitoring.alerts?.warning ?? 0 }}</p>
          </div>
        </div>
        <div class="mt-3 space-y-2">
          <p v-for="alert in latestAlerts.slice(0, 2)" :key="alert.id || alert.timestamp" class="text-sm text-slate-300">
            {{ alert.title }}: {{ alert.message }}
          </p>
          <p v-if="latestAlerts.length === 0" class="text-sm text-slate-500">No active alerts.</p>
        </div>
      </BaseCard>

      <BaseCard>
        <p class="card-title">Model Version & Rollout</p>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
          <div>
            <p class="stat-label">Active Version</p>
            <p class="stat-value mono">{{ monitoring.model?.active_version || 'unavailable' }}</p>
          </div>
          <div>
            <p class="stat-label">Previous Version</p>
            <p class="stat-value mono">{{ monitoring.model?.previous_version || 'n/a' }}</p>
          </div>
          <div>
            <p class="stat-label">Rollout</p>
            <p class="stat-value">{{ formatPercent(monitoring.model?.rollout_percent || 0, 0) }}</p>
          </div>
          <div>
            <p class="stat-label">Last Deploy</p>
            <p class="stat-value">{{ eventTimestamp(monitoring.model?.last_deploy_at) }}</p>
          </div>
        </div>
        <div class="mt-4 space-y-2">
          <p class="stat-label">Runtime Services</p>
          <div
            v-for="service in runtimeServices"
            :key="service.name"
            class="flex items-center justify-between text-sm"
          >
            <span class="text-slate-200">{{ service.name }}</span>
            <span :class="service.ok ? 'text-success-300' : 'text-danger-300'">
              {{ service.ok ? 'Healthy' : 'Unavailable' }}
            </span>
          </div>
          <p v-if="runtimeServices.length === 0" class="text-sm text-slate-500">Runtime checks disabled.</p>
        </div>
      </BaseCard>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <BaseStatTile
        label="Latency p95"
        :icon="PhTimer"
        :value="`${formatNumber(monitoring.health?.latency_p95_ms, 2)} ms`"
        :points="healthHistory.latency_p95_ms"
        :delta="latencyDelta.text"
        :delta-direction="latencyDelta.direction"
        :rising-is-good="false"
      />
      <BaseStatTile
        label="Error Rate (5m)"
        :icon="PhWarningCircle"
        :value="formatPercent(monitoring.health?.error_rate_5m, 2)"
        :points="healthHistory.error_rate_5m"
        :delta="errorRateDelta.text"
        :delta-direction="errorRateDelta.direction"
        :rising-is-good="false"
      />
      <BaseStatTile
        label="Throughput"
        :icon="PhArrowsLeftRight"
        :value="`${formatNumber(monitoring.health?.throughput_rpm, 2)} rpm`"
        :points="healthHistory.throughput_rpm"
        :delta="throughputDelta.text"
        :delta-direction="throughputDelta.direction"
        :rising-is-good="null"
      />
      <BaseStatTile
        label="Uptime (24h)"
        :icon="PhShieldCheck"
        :value="formatPercent(monitoring.health?.uptime_24h, 2)"
        :points="healthHistory.uptime_24h"
        :delta="uptimeDelta.text"
        :delta-direction="uptimeDelta.direction"
        :rising-is-good="true"
      />
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <BaseCard>
        <p class="card-title">Traffic Volume</p>
        <div class="grid grid-cols-3 gap-3 mt-3">
          <div>
            <p class="stat-label">Last 5m</p>
            <p class="stat-value">{{ monitoring.traffic?.requests_last_5m ?? 0 }}</p>
          </div>
          <div>
            <p class="stat-label">Last 24h</p>
            <p class="stat-value">{{ monitoring.traffic?.requests_last_24h ?? 0 }}</p>
          </div>
          <div>
            <p class="stat-label">Delta</p>
            <p class="stat-value">{{ formatPercent(monitoring.traffic?.trend_delta_pct, 2) }}</p>
          </div>
        </div>
      </BaseCard>

      <BaseCard>
        <p class="card-title">Data Quality</p>
        <div class="grid grid-cols-3 gap-3 mt-3">
          <div>
            <p class="stat-label">Missing Ratio</p>
            <p class="stat-value">{{ formatPercent((monitoring.data_quality?.missing_ratio || 0) * 100, 2) }}</p>
          </div>
          <div>
            <p class="stat-label">Schema Mismatch</p>
            <p class="stat-value">{{ monitoring.data_quality?.schema_mismatch_count ?? 0 }}</p>
          </div>
          <div>
            <p class="stat-label">Drop Rate</p>
            <p class="stat-value">{{ formatPercent((monitoring.data_quality?.drop_rate || 0) * 100, 2) }}</p>
          </div>
        </div>
      </BaseCard>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <BaseCard>
        <p class="card-title">Drift</p>
        <p class="text-sm text-slate-400 mt-1">Global score: {{ formatPercent((monitoring.drift?.global_score || 0) * 100, 2) }}</p>
        <div class="mt-3 space-y-2">
          <div
            v-for="item in topShiftedFeatures"
            :key="item.feature"
            class="flex items-center justify-between text-sm"
          >
            <span class="text-slate-200">{{ item.feature }}</span>
            <span class="text-warning-300">{{ formatPercent(item.shift, 2) }}</span>
          </div>
          <p v-if="topShiftedFeatures.length === 0" class="text-sm text-slate-500">No drift contributors yet.</p>
        </div>
      </BaseCard>

      <BaseCard>
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

    <BaseCard>
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
  background: linear-gradient(180deg, rgb(var(--brand-500) / 0.95), rgb(var(--brand-700) / 0.9));
  min-height: 8px;
}

.event-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.55rem 0.25rem;
  border-bottom: 1px solid rgb(var(--border-subtle));
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
