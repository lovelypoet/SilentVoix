<script setup>
import { computed } from 'vue'

/*
 * Single source of truth for realtime/system state across the app - the
 * playground pipeline, the model library runtime column, dashboard runtime
 * services, sensor/websocket status, etc. One dot+label shape, one set of
 * tones, so "connected" or "processing" reads identically everywhere
 * instead of every view inventing its own colored dot.
 */
const STATE_CONFIG = {
  connected: { tone: 'success', label: 'Connected', pulse: false },
  active: { tone: 'success', label: 'Active', pulse: true },
  ready: { tone: 'brand', label: 'Ready', pulse: false },
  processing: { tone: 'brand', label: 'Processing', pulse: true },
  standby: { tone: 'neutral', label: 'Standby', pulse: false },
  disconnected: { tone: 'danger', label: 'Disconnected', pulse: false },
  unavailable: { tone: 'neutral', label: 'Unavailable', pulse: false },
  error: { tone: 'danger', label: 'Error', pulse: false }
}

const props = defineProps({
  state: {
    type: String,
    required: true,
    validator: (v) => ['connected', 'active', 'ready', 'processing', 'standby', 'disconnected', 'unavailable', 'error'].includes(v)
  },
  // Overrides the state's default label - e.g. "Live" instead of "Active".
  label: {
    type: String,
    default: ''
  },
  size: {
    type: String,
    default: 'md' // sm, md
  }
})

const config = computed(() => STATE_CONFIG[props.state] || STATE_CONFIG.standby)
const displayLabel = computed(() => props.label || config.value.label)
</script>

<template>
  <span class="status-indicator" :class="[`status-indicator-${config.tone}`, `status-indicator-${size}`]">
    <span class="status-indicator-dot" :class="{ 'status-indicator-pulse': config.pulse }">
      <span v-if="config.pulse" class="status-indicator-ping"></span>
    </span>
    {{ displayLabel }}
  </span>
</template>

<style scoped>
.status-indicator {
  display: inline-flex;
  align-items: center;
  gap: 0.4375rem;
  font-weight: 600;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  line-height: 1;
  white-space: nowrap;
  transition: color 200ms ease;
}

.status-indicator-sm {
  font-size: 0.625rem;
}

.status-indicator-md {
  font-size: 0.6875rem;
}

.status-indicator-dot {
  position: relative;
  display: inline-block;
  width: 0.4375rem;
  height: 0.4375rem;
  border-radius: 9999px;
  background: currentColor;
  flex-shrink: 0;
}

.status-indicator-ping {
  position: absolute;
  inset: 0;
  border-radius: 9999px;
  background: currentColor;
  animation: status-ping 1.8s cubic-bezier(0, 0, 0.2, 1) infinite;
}

.status-indicator-success {
  color: rgb(var(--success-400));
}

.status-indicator-brand {
  color: rgb(var(--brand-400));
}

.status-indicator-danger {
  color: rgb(var(--danger-400));
}

.status-indicator-neutral {
  color: rgb(var(--slate-500));
}

@keyframes status-ping {
  0% {
    transform: scale(1);
    opacity: 0.65;
  }
  75%, 100% {
    transform: scale(2.4);
    opacity: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .status-indicator-ping {
    animation: none;
    display: none;
  }
}
</style>
