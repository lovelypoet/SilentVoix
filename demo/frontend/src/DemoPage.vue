<template>
  <div class="demo-page">
    <div class="status-bar">
      <div class="status-item">
        <span class="dot" :class="store.connected ? 'dot--green' : 'dot--red'" />
        <span>{{ store.connected ? 'Connected' : 'Disconnected' }}</span>
        <button v-if="!store.connected" class="btn btn--sm btn--ghost" @click="wsConn.connect()">
          Reconnect
        </button>
      </div>
      <div class="status-item" v-if="store.connected">
        <span class="label">Latency:</span>
        <span class="value">{{ store.stableLatency.toFixed(0) }}ms</span>
      </div>
      <div class="status-item" v-if="store.connected">
        <span class="label">Confidence:</span>
        <span class="value">{{ (store.stableConfidence * 100).toFixed(0) }}%</span>
      </div>
      <div class="status-item">
        <span class="ws-status" :class="'ws-status--' + wsStatus.value">{{ wsStatus.value }}</span>
      </div>
    </div>

    <div v-if="store.anomaly" class="anomaly-banner" @click="store.clearAnomaly()">
      &#9888; {{ store.anomaly }}
    </div>

    <div class="word-display">
      <span class="word-text">{{ store.stableGesture }}</span>
    </div>

    <div class="controls-row">
      <button class="btn btn--primary" :disabled="store.connected" @click="wsConn.connect()">
        Connect
      </button>
      <button class="btn btn--danger" :disabled="!store.connected" @click="wsConn.disconnect()">
        Disconnect
      </button>
      <button class="btn btn--ghost" @click="tts.cancel()" :disabled="!tts.speaking.value">
        Cancel TTS
      </button>
    </div>

    <div class="log-section">
      <div class="log-header">
        <h3>Prediction Log</h3>
        <button class="btn btn--sm btn--ghost" @click="store.reset()">Clear</button>
      </div>
      <div class="log-list" ref="logRef">
        <div v-for="p in store.predictions.slice().reverse()" :key="p.id" class="log-entry">
          <span class="log-gesture">{{ p.gesture }}</span>
          <span class="log-conf">%{{ (p.confidence * 100).toFixed(0) }}</span>
          <span class="log-latency">{{ p.latency_ms?.toFixed(0) }}ms</span>
          <span v-if="p.anomaly" class="log-anomaly">&#9878;</span>
        </div>
        <div v-if="store.predictions.length === 0" class="log-empty">
          No predictions yet — connect or switch to Test Lab
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useDemoStore } from './stores/demo.js'
import { useWebSocket } from './useWebSocket.js'
import { useTTS } from './useTTS.js'

const store = useDemoStore()
const tts = useTTS()
const wsConn = useWebSocket('/ws/demo')
const { status: wsStatus } = wsConn
const logRef = ref(null)

let lastSpoken = ''

onMounted(() => {
  wsConn.connect()
})

watch(() => store.stableGesture, (gesture) => {
  if (gesture && gesture !== '—' && gesture !== lastSpoken) {
    lastSpoken = gesture
    tts.speak(gesture, store.stableConfidence)
  }
})
</script>

<style scoped>
.demo-page { display: flex; flex-direction: column; gap: 24px; }

.status-bar {
  display: flex; flex-wrap: wrap; gap: 16px; align-items: center;
  background: #141a2b; border-radius: 12px; padding: 12px 20px;
  font-size: 13px; border: 1px solid #1e2740;
}
.status-item { display: flex; align-items: center; gap: 6px; }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.dot--green { background: #22c55e; box-shadow: 0 0 6px #22c55e88; }
.dot--red { background: #ef4444; box-shadow: 0 0 6px #ef444488; }
.label { color: #64748b; }
.value { color: #e2e8f0; font-weight: 600; font-variant-numeric: tabular-nums; }
.ws-status { font-size: 11px; padding: 2px 8px; border-radius: 4px; text-transform: uppercase; background: #1e2740; }
.ws-status--connected { color: #22c55e; }
.ws-status--disconnected { color: #ef4444; }
.ws-status--reconnecting { color: #f59e0b; }
.ws-status--connecting { color: #3b82f6; }

.anomaly-banner {
  background: #7f1d1d; color: #fca5a5; padding: 10px 16px;
  border-radius: 10px; font-size: 14px; font-weight: 500;
  cursor: pointer; border: 1px solid #991b1b;
}

.word-display {
  display: flex; align-items: center; justify-content: center;
  min-height: 280px;
  background: linear-gradient(135deg, #141a2b 0%, #1a2340 100%);
  border-radius: 16px; border: 1px solid #1e2740;
  text-align: center; padding: 40px 24px;
}
.word-text {
  font-size: clamp(64px, 12vw, 120px);
  font-weight: 800;
  color: #a5b4fc;
  line-height: 1.1;
  text-shadow: 0 0 40px rgba(165, 180, 252, 0.3);
  letter-spacing: -2px;
}

.controls-row { display: flex; gap: 8px; flex-wrap: wrap; }

.log-section {
  background: #141a2b; border-radius: 12px; border: 1px solid #1e2740; overflow: hidden;
}
.log-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px; border-bottom: 1px solid #1e2740;
}
.log-header h3 { margin: 0; font-size: 14px; font-weight: 600; color: #94a3b8; }
.log-list { max-height: 320px; overflow-y: auto; padding: 4px; }
.log-entry {
  display: flex; gap: 12px; align-items: center;
  padding: 6px 12px; font-size: 13px; font-variant-numeric: tabular-nums;
  border-radius: 6px; transition: background 0.15s;
}
.log-entry:hover { background: #1e2740; }
.log-gesture { color: #a5b4fc; font-weight: 600; min-width: 100px; }
.log-conf { color: #64748b; min-width: 40px; }
.log-latency { color: #64748b; min-width: 50px; }
.log-anomaly { color: #ef4444; }
.log-empty { padding: 24px; text-align: center; color: #475569; font-size: 13px; }

.btn {
  padding: 8px 18px; border-radius: 8px; font-size: 13px; font-weight: 600;
  border: none; cursor: pointer; transition: all 0.15s;
}
.btn--primary { background: #4f46e5; color: white; }
.btn--primary:hover { background: #6366f1; }
.btn--primary:disabled { opacity: 0.4; cursor: default; }
.btn--danger { background: #dc2626; color: white; }
.btn--danger:hover { background: #ef4444; }
.btn--danger:disabled { opacity: 0.4; cursor: default; }
.btn--ghost { background: transparent; color: #94a3b8; border: 1px solid #1e2740; }
.btn--ghost:hover { color: #e2e8f0; border-color: #334155; }
.btn--sm { padding: 4px 10px; font-size: 12px; }
</style>
