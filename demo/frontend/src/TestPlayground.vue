<template>
  <div class="playground">
    <h2 class="pg-title">Testing Playground</h2>

    <div class="pg-grid">
      <div class="card">
        <h3>Mock Data Injector</h3>
        <p class="card-desc">Simulate 22-point dual-hand sensor payloads</p>

        <div class="inj-controls">
          <button class="btn btn--primary" @click="toggleAutoInject" :disabled="!wsConnected">
            {{ autoInject ? 'Stop Auto-Inject' : 'Start Auto-Inject' }}
          </button>
          <button class="btn btn--accent" @click="injectPreset('hello')">Preset: Hello</button>
          <button class="btn btn--accent" @click="injectPreset('rest')">Preset: Rest</button>
          <button class="btn btn--accent" @click="injectPreset('no')">Preset: No</button>
        </div>

        <div class="sensor-grid">
          <div class="sensor-group">
            <h4>Left Hand</h4>
            <div v-for="k in leftKeys" :key="k" class="sensor-row">
              <label>{{ k }}</label>
              <input type="range" :min="-10" :max="10" step="0.1" v-model.number="mockData[k]" @change="sendMock" />
              <span class="sensor-val">{{ mockData[k].toFixed(1) }}</span>
            </div>
          </div>
          <div class="sensor-group">
            <h4>Right Hand</h4>
            <div v-for="k in rightKeys" :key="k" class="sensor-row">
              <label>{{ k }}</label>
              <input type="range" :min="-10" :max="10" step="0.1" v-model.number="mockData[k]" @change="sendMock" />
              <span class="sensor-val">{{ mockData[k].toFixed(1) }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <h3>TTS Stress Test</h3>
        <p class="card-desc">Queue rapid-fire TTS to verify debounce/cancel</p>
        <div class="stress-controls">
          <button class="btn btn--warning" @click="runStressTest" :disabled="tts.speaking.value">
            Start Stress Test
          </button>
          <button class="btn btn--danger" @click="tts.cancel()">
            Cancel All
          </button>
          <span class="stress-status" v-if="tts.speaking.value">Speaking...</span>
        </div>
        <div class="stress-words">
          <div v-for="(w, i) in stressWords" :key="i" class="stress-word">
            {{ w }}
          </div>
        </div>

        <div class="spoken-history">
          <h4>TTS History</h4>
          <div v-for="(h, i) in tts.spokenHistory.value.slice(0, 10)" :key="i" class="history-entry">
            <span class="history-word">{{ h.text }}</span>
            <span class="history-conf">%{{ (h.conf * 100).toFixed(0) }}</span>
          </div>
          <div v-if="tts.spokenHistory.value.length === 0" class="log-empty">No TTS yet</div>
        </div>
      </div>
    </div>

    <div class="card full-width">
      <h3>Real-Time Visual Logs</h3>
      <p class="card-desc">Prediction stream with latency and confidence</p>

      <div class="vlog-controls">
        <button class="btn btn--sm btn--ghost" @click="resetLog">Clear</button>
        <span class="vlog-count">{{ store.predictions.length }} predictions</span>
      </div>
      <div class="vlog-container" ref="logContainer">
        <div v-for="(p, i) in paginatedLog" :key="p.id" class="vlog-row" :class="vlogRowClass(p)">
          <span class="vlog-idx">{{ totalPages - page + 1 }}.{{ i + 1 }}</span>
          <span class="vlog-gesture">{{ p.gesture }}</span>
          <span class="vlog-conf">%{{ (p.confidence * 100).toFixed(0) }}</span>
          <span class="vlog-latency">{{ p.latency_ms?.toFixed(0) }}ms</span>
          <span v-if="p.anomaly" class="vlog-anomaly">&#9888; {{ p.anomaly }}</span>
          <span v-if="p._mock" class="vlog-mock">MOCK</span>
        </div>
        <div v-if="store.predictions.length === 0" class="log-empty">
          No predictions yet — connect to WebSocket or use Mock Injector
        </div>
      </div>
      <div class="vlog-pages" v-if="totalPages > 1">
        <button class="btn btn--sm btn--ghost" @click="page = Math.max(1, page - 1)" :disabled="page <= 1">Prev</button>
        <span class="vlog-page-num">{{ page }} / {{ totalPages }}</span>
        <button class="btn btn--sm btn--ghost" @click="page = Math.min(totalPages, page + 1)" :disabled="page >= totalPages">Next</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useDemoStore } from './stores/demo.js'
import { useWebSocket } from './useWebSocket.js'
import { useTTS } from './useTTS.js'

const store = useDemoStore()
const tts = useTTS()
const wsConn = useWebSocket('/ws/predict')
const { status: wsStatus } = wsConn
const wsConnected = computed(() => wsStatus.value === 'connected')

const leftKeys = ['ax_l', 'ay_l', 'az_l', 'gx_l', 'gy_l', 'gz_l', 'f1_l', 'f2_l', 'f3_l', 'f4_l', 'f5_l']
const rightKeys = ['ax_r', 'ay_r', 'az_r', 'gx_r', 'gy_r', 'gz_r', 'f1_r', 'f2_r', 'f3_r', 'f4_r', 'f5_r']

const mockData = reactive({})
for (const k of [...leftKeys, ...rightKeys]) {
  mockData[k] = 0.0
}

const autoInject = ref(false)
let autoInterval = null
const page = ref(1)
const pageSize = 20

const stressWords = ['Hello', 'Yes', 'No', 'We', 'Are', 'Students', 'Thank You', 'Please', 'Help', 'Water', 'Food']

const totalPages = computed(() => Math.max(1, Math.ceil(store.predictions.length / pageSize)))
const paginatedLog = computed(() => {
  const start = (page.value - 1) * pageSize
  return store.predictions.slice().reverse().slice(start, start + pageSize)
})

const logContainer = ref(null)

function vlogRowClass(p) {
  if (p.anomaly) return 'vlog-row--anomaly'
  if (p._mock) return 'vlog-row--mock'
  return ''
}

function toggleAutoInject() {
  autoInject.value = !autoInject.value
  if (autoInject.value) {
    let t = 0
    const presets = [
      { f1_l: 4, f2_l: 3, f3_l: 2, f4_l: 1.5, f1_r: 4, f2_r: 3, f3_r: 2, f4_r: 1.5 },
      { f1_l: 0.5, f2_l: 0.5, f3_l: 0.5, f4_l: 0.5, f1_r: 0.5, f2_r: 0.5, f3_r: 0.5, f4_r: 0.5 },
      { f1_l: 5, f2_l: 4, f3_l: 0.2, f4_l: 0.2, f1_r: 0.2, f2_r: 0.2, f3_r: 0.2, f4_r: 0.2 },
    ]
    autoInterval = setInterval(() => {
      const p = presets[t % presets.length]
      const payload = { ...mockData, ...p, _mock: true }
      payload.ax_l = Math.sin(Date.now() / 1000) * 0.5
      payload.ax_r = Math.cos(Date.now() / 1000) * 0.5
      wsConn.send(payload)
      t++
    }, 800)
  } else {
    if (autoInterval) { clearInterval(autoInterval); autoInterval = null }
  }
}

function injectPreset(name) {
  const presets = {
    hello: { f1_l: 4.5, f2_l: 3.5, f3_l: 2.5, f4_l: 2.0, f5_l: 1.0, f1_r: 4.0, f2_r: 3.0, f3_r: 2.0, f4_r: 1.5, f5_r: 1.0, ax_l: 0.5, ax_r: 0.3 },
    rest: { f1_l: 0.5, f2_l: 0.5, f3_l: 0.5, f4_l: 0.5, f5_l: 0.5, f1_r: 0.5, f2_r: 0.5, f3_r: 0.5, f4_r: 0.5, f5_r: 0.5, ax_l: 0.0, ax_r: 0.0 },
    no: { f1_l: 5.0, f2_l: 4.5, f3_l: 0.5, f4_l: 0.5, f5_l: 0.5, f1_r: 0.5, f2_r: 0.5, f3_r: 0.5, f4_r: 0.5, f5_r: 0.5, ax_l: 0.1, ax_r: 0.1 },
  }
  const preset = presets[name]
  if (!preset) return
  const payload = { ...mockData, ...preset, _mock: true }
  wsConn.send(payload)
}

function sendMock() {
  const payload = { ...mockData, _mock: true }
  wsConn.send(payload)
}

function runStressTest() {
  tts.stressTest(stressWords, 15)
}

function resetLog() {
  store.reset()
  page.value = 1
}

onMounted(() => {
  wsConn.connect()
})

onUnmounted(() => {
  if (autoInterval) clearInterval(autoInterval)
})
</script>

<style scoped>
.playground { display: flex; flex-direction: column; gap: 20px; }
.pg-title { font-size: 22px; font-weight: 700; margin: 0 0 4px; color: #e2e8f0; }
.pg-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
@media (max-width: 800px) { .pg-grid { grid-template-columns: 1fr; } }

.card {
  background: #141a2b; border-radius: 12px; border: 1px solid #1e2740; padding: 20px;
}
.card h3 { margin: 0 0 4px; font-size: 16px; font-weight: 600; color: #e2e8f0; }
.card h4 { margin: 12px 0 8px; font-size: 13px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; }
.card-desc { margin: 0 0 16px; font-size: 13px; color: #64748b; }
.full-width { grid-column: 1 / -1; }

.inj-controls { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 16px; }

.sensor-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 600px) { .sensor-grid { grid-template-columns: 1fr; } }
.sensor-group { }
.sensor-row { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.sensor-row label { min-width: 40px; font-size: 11px; color: #64748b; font-family: monospace; }
.sensor-row input { flex: 1; accent-color: #4f46e5; height: 4px; }
.sensor-val { min-width: 36px; text-align: right; font-size: 11px; color: #94a3b8; font-family: monospace; }

.stress-controls { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; margin-bottom: 12px; }
.stress-status { font-size: 12px; color: #f59e0b; font-weight: 600; }
.stress-words { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 16px; }
.stress-word {
  padding: 2px 8px; background: #1e2740; border-radius: 4px;
  font-size: 11px; color: #94a3b8;
}

.spoken-history { }
.history-entry { display: flex; gap: 8px; padding: 4px 0; font-size: 13px; }
.history-word { color: #a5b4fc; font-weight: 500; }
.history-conf { color: #64748b; }

.vlog-controls { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.vlog-count { font-size: 12px; color: #64748b; }
.vlog-container { max-height: 400px; overflow-y: auto; }
.vlog-row {
  display: flex; gap: 12px; align-items: center;
  padding: 6px 10px; font-size: 13px; font-variant-numeric: tabular-nums;
  border-radius: 6px; transition: background 0.15s;
}
.vlog-row:hover { background: #1e2740; }
.vlog-row--anomaly { background: #7f1d1d22; border-left: 3px solid #ef4444; }
.vlog-row--mock { opacity: 0.7; }
.vlog-idx { color: #475569; min-width: 60px; font-size: 11px; }
.vlog-gesture { color: #a5b4fc; font-weight: 600; min-width: 100px; }
.vlog-conf { color: #64748b; min-width: 40px; }
.vlog-latency { color: #64748b; min-width: 50px; }
.vlog-anomaly { color: #ef4444; font-size: 12px; }
.vlog-mock { font-size: 10px; padding: 1px 6px; background: #1e2740; border-radius: 3px; color: #475569; text-transform: uppercase; }
.vlog-pages { display: flex; justify-content: center; align-items: center; gap: 12px; margin-top: 8px; }
.vlog-page-num { font-size: 12px; color: #64748b; }
.log-empty { padding: 24px; text-align: center; color: #475569; font-size: 13px; }

.btn {
  padding: 8px 18px; border-radius: 8px; font-size: 13px; font-weight: 600;
  border: none; cursor: pointer; transition: all 0.15s;
}
.btn--primary { background: #4f46e5; color: white; }
.btn--primary:hover { background: #6366f1; }
.btn--primary:disabled { opacity: 0.4; cursor: default; }
.btn--accent { background: #141a2b; color: #a5b4fc; border: 1px solid #4f46e5; }
.btn--accent:hover { background: #1e2740; }
.btn--warning { background: #d97706; color: white; }
.btn--warning:hover { background: #f59e0b; }
.btn--warning:disabled { opacity: 0.4; cursor: default; }
.btn--danger { background: #dc2626; color: white; }
.btn--danger:hover { background: #ef4444; }
.btn--ghost { background: transparent; color: #94a3b8; border: 1px solid #1e2740; }
.btn--ghost:hover { color: #e2e8f0; border-color: #334155; }
.btn--sm { padding: 4px 10px; font-size: 12px; }
</style>
