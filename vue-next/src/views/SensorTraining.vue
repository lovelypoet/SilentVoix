<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import BaseBtn from '../components/base/BaseBtn.vue'
import BaseCard from '../components/base/BaseCard.vue'
import { useSensorTraining } from '../composables/useSensorTraining'
import { usePortSession } from '../composables/usePortSession'

const router = useRouter()

const {
  captureError,
  captureLogPath,
  capturePid,
  captureStatus,
  canExport,
  clearLiveFrames,
  connect,
  connectionError,
  connectionState,
  disconnect,
  estimatedFps,
  exportRecordedCsv,
  exportRecordedJson,
  fetchCaptureStatus,
  isConnected,
  isCaptureBusy,
  isRecording,
  label,
  lastFrameAt,
  latestChannels,
  latestFrame,
  liveFrames,
  maxLiveFrames,
  recordedFrames,
  resetRecording,
  sessionId,
  startCapture,
  stopCapture,
  startRecording,
  stopRecording
} = useSensorTraining()

const {
  applyAutoDetectedPorts,
  applySinglePort,
  autoRefresh,
  error: portError,
  fetchSerialStatus,
  isLoading: isPortLoading,
  isUpdatingConfig,
  lastCheckedAt,
  message: portMessage,
  serialStatus
} = usePortSession({ autoStart: false, pollingEnabled: false })

const selectedPort = ref('')
const showAdvanced = ref(false)

watch(showAdvanced, (open) => {
  if (open && !lastCheckedAt.value && !isPortLoading.value) {
    void fetchSerialStatus()
  }
})

const isCaptureRunning = computed(() => captureStatus.value === 'running')
const canConnectStream = computed(() => isCaptureRunning.value && !isConnected.value)
const canStartRecordingNow = computed(() => isCaptureRunning.value && isConnected.value && !isRecording.value)

const workflowStep = computed(() => {
  if (!isCaptureRunning.value) return 1
  if (!isConnected.value) return 2
  if (!isRecording.value) return 3
  return 4
})

const flowHint = computed(() => {
  if (!isCaptureRunning.value) return 'Start sensor service first.'
  if (!isConnected.value) return 'Service is running. Connect stream next.'
  if (!isRecording.value) return 'Stream is live. Start recording to collect samples.'
  return 'Recording in progress. Stop and export when done.'
})

const lastFrames = computed(() => {
  if (!liveFrames.value.length) return []
  return [...liveFrames.value].slice(-20).reverse()
})

const formatTime = (timestampMs) => {
  if (!timestampMs) return '--'
  return new Date(timestampMs).toLocaleTimeString()
}

const channelPercent = (value, index) => {
  const numeric = Number(value)
  if (Number.isNaN(numeric)) return 0

  if (index < 5) {
    const clamped = Math.min(Math.max(numeric, 0), 1023)
    return Math.round((clamped / 1023) * 100)
  }

  const imuMin = -4
  const imuMax = 4
  const clamped = Math.min(Math.max(numeric, imuMin), imuMax)
  return Math.round(((clamped - imuMin) / (imuMax - imuMin)) * 100)
}
</script>

<template>
  <div class="max-w-7xl mx-auto">
    <section class="mb-6 grid grid-cols-[auto_1fr] md:grid-cols-3 items-center gap-3">
      <div class="flex justify-start">
        <BaseBtn
          variant="secondary"
          title="Return to dashboard"
          class="px-3"
          @click="router.push('/')"
        >
          &larr;
        </BaseBtn>
      </div>
      <div class="text-left md:text-center">
        <h1 class="text-2xl md:text-3xl font-bold text-teal-300">Sensor Training</h1>
        <p class="text-slate-400 mt-1">
          Guided flow: <code>Service</code> -> <code>Stream</code> -> <code>Recording</code> -> <code>Export</code>
        </p>
      </div>
      <div class="hidden md:block"></div>
    </section>

    <section class="mb-6">
      <BaseCard>
        <div class="flex flex-wrap items-start justify-between gap-4 mb-4">
          <div>
            <p class="text-xs uppercase tracking-wide text-slate-400">Primary Workflow</p>
            <p class="text-sm mt-1 text-slate-300">{{ flowHint }}</p>
          </div>
          <div class="text-xs rounded-full px-3 py-1 border" :class="workflowStep === 4 ? 'border-emerald-500/40 text-emerald-300' : 'border-amber-500/40 text-amber-300'">
            Step {{ workflowStep }} of 4
          </div>
        </div>

        <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div class="rounded-xl border p-3" :class="isCaptureRunning ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-slate-800 bg-slate-950/40'">
            <p class="text-[11px] uppercase tracking-wide text-slate-400">1. Sensor Service</p>
            <p class="text-sm mt-1" :class="isCaptureRunning ? 'text-emerald-300' : 'text-amber-300'">
              {{ isCaptureRunning ? 'Running' : 'Stopped' }}
              <span v-if="capturePid"> (pid {{ capturePid }})</span>
            </p>
            <div class="grid grid-cols-1 gap-2 mt-3">
              <BaseBtn variant="secondary" :disabled="isCaptureBusy || isCaptureRunning" @click="startCapture">
                {{ isCaptureBusy ? 'Starting...' : 'Start Sensor Service' }}
              </BaseBtn>
              <BaseBtn variant="secondary" :disabled="isCaptureBusy || !isCaptureRunning" @click="stopCapture">
                Stop Sensor Service
              </BaseBtn>
              <BaseBtn variant="secondary" :disabled="isCaptureBusy" @click="fetchCaptureStatus">
                Refresh Service Status
              </BaseBtn>
            </div>
          </div>

          <div class="rounded-xl border p-3" :class="isConnected ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-slate-800 bg-slate-950/40'">
            <p class="text-[11px] uppercase tracking-wide text-slate-400">2. Stream Connection</p>
            <p class="text-sm mt-1" :class="isConnected ? 'text-emerald-300' : 'text-amber-300'">
              {{ isConnected ? 'Connected' : 'Disconnected' }}
            </p>
            <p class="text-xs text-slate-500 mt-1">Endpoint: /ws/stream</p>
            <div class="grid grid-cols-1 gap-2 mt-3">
              <BaseBtn variant="secondary" :disabled="!canConnectStream" @click="connect">
                Connect Stream
              </BaseBtn>
              <BaseBtn variant="secondary" :disabled="!isConnected" @click="disconnect">
                Disconnect Stream
              </BaseBtn>
              <BaseBtn variant="danger" :disabled="liveFrames.length === 0" @click="clearLiveFrames">
                Clear Live Frames
              </BaseBtn>
            </div>
          </div>

          <div class="rounded-xl border p-3" :class="isRecording ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-slate-800 bg-slate-950/40'">
            <p class="text-[11px] uppercase tracking-wide text-slate-400">3. Recording</p>
            <p class="text-sm mt-1" :class="isRecording ? 'text-emerald-300' : 'text-amber-300'">
              {{ isRecording ? 'Recording' : 'Idle' }}
            </p>
            <p class="text-xs text-slate-500 mt-1">Saved frames: {{ recordedFrames.length }}</p>
            <div class="grid grid-cols-1 gap-2 mt-3">
              <BaseBtn variant="primary" :disabled="!canStartRecordingNow" @click="startRecording">
                Start Recording
              </BaseBtn>
              <BaseBtn variant="amber" :disabled="!isRecording" @click="stopRecording">
                Stop Recording
              </BaseBtn>
              <BaseBtn variant="danger" :disabled="recordedFrames.length === 0 && !isRecording" @click="resetRecording">
                Reset Recording
              </BaseBtn>
            </div>
          </div>

          <div class="rounded-xl border p-3" :class="canExport ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-slate-800 bg-slate-950/40'">
            <p class="text-[11px] uppercase tracking-wide text-slate-400">4. Export</p>
            <p class="text-sm mt-1" :class="canExport ? 'text-emerald-300' : 'text-slate-400'">
              {{ canExport ? 'Ready' : 'Not ready' }}
            </p>
            <p class="text-xs text-slate-500 mt-1">Exported label: {{ (label || 'unlabeled').trim() || 'unlabeled' }}</p>
            <div class="grid grid-cols-1 gap-2 mt-3">
              <BaseBtn :disabled="!canExport" variant="secondary" @click="exportRecordedCsv">Export CSV</BaseBtn>
              <BaseBtn :disabled="!canExport" variant="secondary" @click="exportRecordedJson">Export JSON</BaseBtn>
            </div>
          </div>
        </div>

        <p v-if="captureError" class="text-xs text-rose-300 mt-3">{{ captureError }}</p>
        <p v-if="connectionError" class="text-xs text-rose-300 mt-1">{{ connectionError }}</p>
      </BaseCard>
    </section>

    <section class="grid gap-6 xl:grid-cols-3 mb-6">
      <BaseCard class="xl:col-span-2">
        <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
          <h2 class="text-xl font-semibold text-slate-100">Live Channel Readout</h2>
          <div class="text-xs text-slate-500 flex flex-wrap items-center gap-x-3 gap-y-1">
            <span>State: {{ connectionState }}</span>
            <span>FPS: {{ estimatedFps }}</span>
            <span>Frames: {{ liveFrames.length }}</span>
            <span>Last: {{ lastFrameAt ? lastFrameAt.toLocaleTimeString() : '--' }}</span>
          </div>
        </div>

        <div v-if="latestFrame" class="space-y-4">
          <div>
            <p class="text-sm font-medium text-slate-300 mb-2">Flex (0-1023)</p>
            <div class="space-y-2">
              <div
                v-for="(value, idx) in latestChannels.flex"
                :key="`flex_${idx}`"
                class="rounded-lg border border-slate-700 bg-slate-950/40 p-2"
              >
                <div class="flex justify-between text-xs text-slate-300 mb-1">
                  <span>flex{{ idx + 1 }}</span>
                  <span>{{ Number(value).toFixed(2) }}</span>
                </div>
                <div class="h-2 rounded bg-slate-800 overflow-hidden">
                  <div class="h-full bg-teal-400" :style="{ width: `${channelPercent(value, idx)}%` }"></div>
                </div>
              </div>
            </div>
          </div>

          <div>
            <p class="text-sm font-medium text-slate-300 mb-2">Accel / Gyro (approx -4 to 4)</p>
            <div class="space-y-2">
              <div
                v-for="(value, idx) in [...latestChannels.accel, ...latestChannels.gyro]"
                :key="`imu_${idx}`"
                class="rounded-lg border border-slate-700 bg-slate-950/40 p-2"
              >
                <div class="flex justify-between text-xs text-slate-300 mb-1">
                  <span>{{ idx < 3 ? `accel_${['x', 'y', 'z'][idx]}` : `gyro_${['x', 'y', 'z'][idx - 3]}` }}</span>
                  <span>{{ Number(value).toFixed(4) }}</span>
                </div>
                <div class="h-2 rounded bg-slate-800 overflow-hidden">
                  <div class="h-full bg-sky-400" :style="{ width: `${channelPercent(value, idx + 5)}%` }"></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <p v-else class="text-slate-400">Waiting for sensor frames.</p>
      </BaseCard>

      <BaseCard>
        <h2 class="text-xl font-semibold text-slate-100 mb-4">Session Settings</h2>
        <div class="space-y-3">
          <label class="block text-sm text-slate-300">
            Session ID
            <input
              v-model="sessionId"
              type="text"
              class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2 text-slate-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </label>

          <label class="block text-sm text-slate-300">
            Label
            <input
              v-model="label"
              type="text"
              placeholder="e.g. hello, rest, custom gesture"
              class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2 text-slate-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </label>

          <label class="block text-sm text-slate-300">
            Live Buffer Size
            <input
              v-model.number="maxLiveFrames"
              type="number"
              min="20"
              max="2000"
              class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2 text-slate-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </label>
        </div>

        <div class="mt-4 border border-slate-800 rounded-lg bg-slate-950/40 p-3">
          <button class="w-full flex items-center justify-between text-sm text-slate-200" @click="showAdvanced = !showAdvanced">
            <span>Advanced Controls</span>
            <span class="text-xs text-slate-500">{{ showAdvanced ? 'Hide' : 'Show' }}</span>
          </button>

          <div v-if="showAdvanced" class="mt-3 space-y-3">
            <div>
              <p class="text-xs uppercase tracking-wide text-slate-400">Serial Port</p>
              <p class="text-xs mt-1" :class="serialStatus.single_connected ? 'text-emerald-300' : 'text-amber-300'">
                {{ serialStatus.single_connected ? 'Connected' : 'Not Connected' }}
                <span class="text-slate-500"> ({{ serialStatus.single_port || '--' }})</span>
              </p>
              <p class="text-[11px] text-slate-500 mt-1">
                Detected: {{ (serialStatus.available_ports || []).length ? serialStatus.available_ports.join(', ') : 'none' }}
              </p>
              <label class="block text-xs text-slate-400 mt-2">
                Set Port
                <select
                  v-model="selectedPort"
                  class="mt-1 w-full rounded border border-slate-700 bg-slate-950/70 px-2 py-1 text-slate-200"
                >
                  <option value="">Select detected port</option>
                  <option v-for="port in (serialStatus.available_ports || [])" :key="port" :value="port">
                    {{ port }}
                  </option>
                </select>
              </label>
              <div class="grid grid-cols-2 gap-2 mt-2">
                <BaseBtn
                  variant="secondary"
                  class="!px-2 !py-1 text-xs"
                  :disabled="isUpdatingConfig"
                  @click="applyAutoDetectedPorts"
                >
                  {{ isUpdatingConfig ? 'Applying...' : 'Auto Detect' }}
                </BaseBtn>
                <BaseBtn
                  variant="secondary"
                  class="!px-2 !py-1 text-xs"
                  :disabled="isUpdatingConfig || !selectedPort"
                  @click="applySinglePort(selectedPort)"
                >
                  Use Selected
                </BaseBtn>
              </div>
              <div class="flex items-center justify-between mt-2">
                <p class="text-[11px] text-slate-500">Last check: {{ lastCheckedAt ? lastCheckedAt.toLocaleTimeString() : '--' }}</p>
                <BaseBtn
                  variant="secondary"
                  class="!px-2 !py-1 text-xs"
                  :disabled="isPortLoading || isUpdatingConfig"
                  @click="fetchSerialStatus"
                >
                  {{ isPortLoading ? 'Checking...' : 'Refresh' }}
                </BaseBtn>
              </div>
              <p class="text-[11px] mt-2" :class="autoRefresh ? 'text-teal-300' : 'text-amber-300'">
                Auto-refresh: {{ autoRefresh ? 'on' : 'paused' }}
              </p>
              <p v-if="portError" class="text-xs text-rose-300 mt-1">{{ portError }}</p>
              <p v-if="portMessage" class="text-xs text-emerald-300 mt-1">{{ portMessage }}</p>
            </div>

            <div>
              <p class="text-xs uppercase tracking-wide text-slate-400">Capture Log</p>
              <p class="text-[11px] text-slate-500 truncate mt-1">{{ captureLogPath || 'No log file yet.' }}</p>
            </div>
          </div>
        </div>
      </BaseCard>
    </section>

    <section class="mt-6">
      <BaseCard>
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-xl font-semibold text-slate-100">Recent Frames</h2>
          <p class="text-xs text-slate-500">
            showing {{ lastFrames.length }} / {{ liveFrames.length }}
          </p>
        </div>
        <div class="overflow-auto">
          <table class="w-full min-w-[900px] text-sm">
            <thead class="text-slate-400 border-b border-slate-800">
              <tr>
                <th class="text-left py-2 pr-3">Time</th>
                <th class="text-left py-2 pr-3">Sequence</th>
                <th class="text-left py-2 pr-3">Label</th>
                <th class="text-left py-2 pr-3">Source</th>
                <th class="text-left py-2 pr-3">Values</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(frame, idx) in lastFrames"
                :key="`row_${idx}_${frame.timestamp_ms}`"
                class="border-b border-slate-900/70 text-slate-200"
              >
                <td class="py-2 pr-3 whitespace-nowrap">{{ formatTime(frame.timestamp_ms) }}</td>
                <td class="py-2 pr-3">{{ frame.sequence ?? '--' }}</td>
                <td class="py-2 pr-3">{{ label || 'unlabeled' }}</td>
                <td class="py-2 pr-3">{{ frame.source || '--' }}</td>
                <td class="py-2 pr-3 text-xs text-slate-300">
                  {{ frame.values.map((v) => Number(v).toFixed(3)).join(', ') }}
                </td>
              </tr>
              <tr v-if="!lastFrames.length">
                <td colspan="5" class="py-4 text-slate-500">No frames yet.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </BaseCard>
    </section>
  </div>
</template>
