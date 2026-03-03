<script setup>
import { ref, watch, computed, nextTick, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import TrainingSettings from '../components/TrainingSettings.vue'
import CaptureSyncGraph from '../components/CaptureSyncGraph.vue'
import CaptureTerminal from '../components/CaptureTerminal.vue'
import api from '../services/api'
import { useMediaPermissions } from '../composables/useMediaPermissions.js'
import { useTrainingSettings } from '../composables/useTrainingSettings.js'
import { useHandTracking } from '../composables/useHandTracking.js'
import { useCollectData } from '../composables/useCollectData.js'
import { useCollectorLogs } from '../composables/useCollectorLogs.js'
import { useSyncStream } from '../composables/useSyncStream.js'
import { usePortSession } from '../composables/usePortSession.js'
import { useSensorCaptureSession } from '../composables/useSensorCaptureSession.js'

const isSessionActive = ref(false)
const showSettings = ref(false)
const videoEl = ref(null)
const canvasEl = ref(null)
const actualFps = ref(0)
const detectedGesture = ref('Waiting...')
const confidence = ref('--%')
const prevLandmarks = ref(null)
const prevHandedness = ref(null)
const recordingStartCount = ref(0)
const cvFrameId = ref(0)
const hasAutoSavedCurrentRun = ref(false)
const route = useRoute()
const router = useRouter()
const captureMode = ref('single')
const syncCountdown = ref(0)
const expectedSyncTimestampMs = ref(null)
const isAwaitingSyncCue = ref(false)
const terminalComponent = ref(null)
const isExportingSensorCsv = ref(false)
const exportStatusMessage = ref('')
const showAdvancedControls = ref(false)
const sensorMaxSamples = ref(0)

const {
  collectedLandmarks,
  isCollecting,
  currentGestureName,
  metadata,
  takeLogs,
  startCollecting,
  stopCollecting,
  addLandmark,
  clearData
} = useCollectData()

const {
  hasPermissions,
  isRequesting,
  error,
  stream,
  requestPermissions
} = useMediaPermissions()

const { mirrorCamera, enableCamera, showLandmarks, frameLimit } = useTrainingSettings()
const { startHandTracking, stopHandTracking, onFrame } = useHandTracking(mirrorCamera, showLandmarks)

const {
  serialStatus,
} = usePortSession()

const {
  sensorCaptureStatus,
  startSensorCapture,
  stopSensorCapture
} = useSensorCaptureSession()

const {
  terminalLines,
  terminalError,
  isStreaming: isTerminalStreaming,
  autoScroll: terminalAutoScroll,
  toggleStream: toggleTerminalStream
} = useCollectorLogs(captureMode, sensorCaptureStatus)

const {
  sensorSpikeActive,
  cvSpikeActive,
  syncOffsetMs,
  syncWsConnected,
  sparkPath,
  cvPath,
  sparkPeak,
  cvPeak,
  sparkThreshold,
  cvThreshold,
  sparkSpike,
  cvSpike,
  ingestCvPoint,
  resetCvState
} = useSyncStream(captureMode)

const videoClasses = computed(() => [
  'w-full',
  'h-full',
  'object-cover',
  { '-scale-x-100': mirrorCamera.value }
])

const isEarlyFusionRoute = computed(() => route.path === '/early-fusion-training')
const pageTitle = computed(() => (isEarlyFusionRoute.value ? 'Early Fusion Training' : 'Fusion Training'))
const pageSubtitle = computed(() => (
  isEarlyFusionRoute.value
    ? 'Guided flow: Camera Session -> Sensor Source -> Recording -> Export (Early Fusion).'
    : 'Guided flow: Camera Session -> Sensor Source -> Recording -> Export.'
))
const permissionTrainingLabel = computed(() => (isEarlyFusionRoute.value ? 'early fusion training' : 'fusion training'))

const expectedSyncLabel = computed(() => {
  if (!expectedSyncTimestampMs.value) return ''
  return new Date(expectedSyncTimestampMs.value).toLocaleTimeString()
})

const isSensorRunning = computed(() => sensorCaptureStatus.value?.status === 'running')
const sensorReady = computed(() => isSensorRunning.value)
const canStartTake = computed(
  () => Boolean(currentGestureName.value.trim()) && !isCollecting.value && !isAwaitingSyncCue.value && sensorReady.value
)
const canExportFusion = computed(
  () => collectedLandmarks.value.length > 0 && !isExportingSensorCsv.value
)
const framesInCurrentTake = computed(() => Math.max(0, collectedLandmarks.value.length - recordingStartCount.value))
const workflowStep = computed(() => {
  if (!isSessionActive.value) return 1
  if (!sensorReady.value) return 2
  if (!isCollecting.value && !isAwaitingSyncCue.value) return 3
  return 4
})
const flowHint = computed(() => {
  if (!isSessionActive.value) return 'Enable camera session first.'
  if (!sensorReady.value) return 'Start sensor service first.'
  if (!isCollecting.value && !isAwaitingSyncCue.value) return 'Set gesture name and start recording.'
  if (isAwaitingSyncCue.value) return 'Sync cue active. Recording starts when countdown hits zero.'
  return 'Recording in progress. Stop and export when done.'
})

let frameCount = 0
let lastTime = performance.now()
let fpsInterval = null
let syncCueTimer = null

const calculateFps = () => {
  frameCount++
  const currentTime = performance.now()
  const elapsed = currentTime - lastTime
  if (elapsed >= 1000) {
    actualFps.value = Math.round((frameCount * 1000) / elapsed)
    frameCount = 0
    lastTime = currentTime
  }
}

const startFpsCounter = () => {
  frameCount = 0
  lastTime = performance.now()
  actualFps.value = 0
  fpsInterval = setInterval(() => {
    calculateFps()
  }, 100)
}

const stopFpsCounter = () => {
  if (fpsInterval) {
    clearInterval(fpsInterval)
    fpsInterval = null
  }
  actualFps.value = 0
  frameCount = 0
}

const startSession = async () => {
  await requestPermissions()
  if (hasPermissions.value) {
    isSessionActive.value = true
  }
}

const startRecording = () => {
  if (isCollecting.value || isAwaitingSyncCue.value || !currentGestureName.value.trim()) return
  metadata.value.fps = 30
  metadata.value.frame_limit = frameLimit.value
  cvFrameId.value = 0
  hasAutoSavedCurrentRun.value = false
  isAwaitingSyncCue.value = true
  triggerSyncCue(() => {
    if (!isAwaitingSyncCue.value) return
    recordingStartCount.value = collectedLandmarks.value.length
    startCollecting(currentGestureName.value)
    isAwaitingSyncCue.value = false
  })
}

const resetRecording = () => {
  cancelPendingRecording()
  stopCollecting()
  clearData()
  recordingStartCount.value = 0
  expectedSyncTimestampMs.value = null
  hasAutoSavedCurrentRun.value = false
}

const stopTake = () => {
  cancelPendingRecording()
  stopCollecting()
}

const stopAndAutoSave = async () => {
  if (!isCollecting.value || hasAutoSavedCurrentRun.value) return
  hasAutoSavedCurrentRun.value = true
  
  stopCollecting()
  resetRecording()
  await downloadCvSensorCsv()
}

const buildFusionCsv = (frames, sensorHeader, sensorRows, sensorSource = 'unknown') => {
  const cvHeader = [
    'frame_id', 'timestamp_ms', 'gesture', 'take_id', 'take_quality', 'quality_score',
    'bad_reasons', 'primary_hand', 'lighting_status', 'L_exist', 'R_exist', 'L_missing', 'R_missing'
  ]

  for (let i = 0; i < 21; i++) cvHeader.push(`L_x${i}`, `L_y${i}`, `L_z${i}`)
  for (let i = 0; i < 21; i++) cvHeader.push(`R_x${i}`, `R_y${i}`, `R_z${i}`)

  const sensorPrefixed = sensorHeader.map((key) => `sensor_${key}`)
  const header = [...cvHeader, 'capture_sensor_source', 'sensor_match_delta_ms', ...sensorPrefixed]

  const safeCell = (value) => {
    const text = value === null || value === undefined ? '' : String(value)
    if (text.includes(',') || text.includes('"') || text.includes('\n')) {
      return `"${text.replace(/"/g, '""')}"`
    }
    return text
  }

  const sensorEntries = sensorRows.map((row) => ({
    ...row,
    timestamp_ms: Number(row.timestamp_ms)
  })).filter((row) => Number.isFinite(row.timestamp_ms))

  const nearestSensor = (ts) => {
    if (!sensorEntries.length) return { row: null, delta: '' }
    let best = sensorEntries[0]
    let bestDelta = Math.abs(sensorEntries[0].timestamp_ms - ts)
    for (let i = 1; i < sensorEntries.length; i++) {
      const delta = Math.abs(sensorEntries[i].timestamp_ms - ts)
      if (delta < bestDelta) {
        best = sensorEntries[i]
        bestDelta = delta
      }
    }
    return { row: best, delta: best.timestamp_ms - ts }
  }

  const lines = [header.map(safeCell).join(',')]
  frames.forEach((frame) => {
    const L_missing = frame.L_exist ? 0 : 1
    const R_missing = frame.R_exist ? 0 : 1
    const badReasons = (frame.bad_reasons || '').replace(/,/g, ';')
    const cvCells = [
      frame.frame_id,
      frame.timestamp_ms,
      frame.gesture,
      frame.take_id ?? '',
      frame.take_quality ?? '',
      frame.quality_score ?? '',
      badReasons,
      frame.primary_hand ?? '',
      frame.lighting_status ?? '',
      frame.L_exist,
      frame.R_exist,
      L_missing,
      R_missing,
      ...frame.features
    ]

    const { row: sensorRow, delta } = nearestSensor(Number(frame.timestamp_ms))
    const sensorCells = sensorHeader.map((key) => (sensorRow ? (sensorRow[key] ?? '') : ''))
    lines.push([...cvCells, sensorSource, delta, ...sensorCells].map(safeCell).join(','))
  })

  return lines.join('\n') + '\n'
}

const downloadCvSensorCsv = async () => {
  exportStatusMessage.value = ''
  if (collectedLandmarks.value.length === 0 || isExportingSensorCsv.value) {
    exportStatusMessage.value = 'No CV frames to export yet.'
    return false
  }
  const frames = collectedLandmarks.value
  const startMs = Number(frames[0]?.timestamp_ms)
  const endMs = Number(frames[frames.length - 1]?.timestamp_ms)
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs)) {
    exportStatusMessage.value = 'Invalid frame timestamps. Record again and retry export.'
    return false
  }

  isExportingSensorCsv.value = true
  try {
    const activeMode = sensorCaptureStatus.value?.status === 'running'
      ? (sensorCaptureStatus.value?.mode || captureMode.value)
      : captureMode.value

    let sensorHeader = []
    let sensorRows = []
    let usedFallback = false
    try {
      const response = await api.sync.sensorWindow(activeMode, startMs, endMs, 3000)
      sensorHeader = response?.header || []
      sensorRows = response?.rows || []
    } catch (e) {
      console.error('Failed to fetch sensor window for export. Falling back to CV-only export.', e)
      usedFallback = true
    }

    const sensorSource = sensorRows.length ? 'real' : 'none'
    const csv = buildFusionCsv(frames, sensorHeader, sensorRows, sensorSource)
    const stamp = new Date().toISOString().replace(/[:.]/g, '-')
    const label = (currentGestureName.value || 'data').replace(/\s+/g, '_')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `cv_sensor_${label}_${stamp}.csv`
    a.click()
    URL.revokeObjectURL(url)
    if (usedFallback) {
      exportStatusMessage.value = 'Sensor API unavailable. Downloaded CV-only CSV.'
    } else if (!sensorRows.length) {
      exportStatusMessage.value = 'Downloaded CSV. No sensor rows matched this capture window.'
    } else {
      exportStatusMessage.value = `Downloaded CSV with ${sensorRows.length} sensor rows.`
    }
    return true
  } catch (e) {
    console.error('Failed to export CV+Sensor CSV', e)
    exportStatusMessage.value = 'Export failed. Check API connectivity and try again.'
    return false
  } finally {
    isExportingSensorCsv.value = false
  }
}

const triggerSyncCue = (onComplete = null) => {
  if (syncCountdown.value > 0) return
  if (syncCueTimer) {
    clearInterval(syncCueTimer)
    syncCueTimer = null
  }
  syncCountdown.value = 3
  expectedSyncTimestampMs.value = Date.now() + 3000
  syncCueTimer = setInterval(() => {
    syncCountdown.value -= 1
    if (syncCountdown.value <= 0) {
      clearInterval(syncCueTimer)
      syncCueTimer = null
      if (typeof onComplete === 'function') onComplete()
    }
  }, 1000)
}

const cancelPendingRecording = () => {
  isAwaitingSyncCue.value = false
  syncCountdown.value = 0
  expectedSyncTimestampMs.value = null
  if (syncCueTimer) {
    clearInterval(syncCueTimer)
    syncCueTimer = null
  }
}

const scrollTerminalToBottom = () => {
  const el = terminalComponent.value?.terminalEl
  if (!el || !terminalAutoScroll.value) return
  el.scrollTop = el.scrollHeight
}

onUnmounted(() => {
  cancelPendingRecording()
})

watch(
  [isSessionActive, stream, videoEl, canvasEl, enableCamera],
  async ([active, mediaStream, video, canvas, cameraEnabled]) => {
    if (!active || !cameraEnabled) {
      stopHandTracking()
      stopFpsCounter()
      prevLandmarks.value = null
      prevHandedness.value = null
      resetCvState()
      confidence.value = '--%'
      detectedGesture.value = 'Waiting...'
      return
    }

    if (!mediaStream || !video || !canvas) return

    await nextTick()

    if (video.srcObject !== mediaStream) {
      video.srcObject = mediaStream
      video.play().catch(e => console.error('Error playing video:', e))
    }

    startHandTracking(video, canvas, mediaStream)
    startFpsCounter()

    onFrame((results) => {
      frameCount++

      if (results?.landmarks?.[0]?.[0]) {
        ingestCvPoint(results.landmarks[0][0], Date.now())
      }

      if (isCollecting.value) {
        const framesSinceStart = collectedLandmarks.value.length - recordingStartCount.value
        if (framesSinceStart >= frameLimit.value) {
          void stopAndAutoSave()
          return
        }
      }

      if (results?.landmarks && results.landmarks.length > 0) {
        detectedGesture.value = 'Hand Detected'
        const landmarks = results.landmarks[0]
        const handedness = results.handedness?.[0]?.[0]

        const handednessScore = handedness?.score || 0
        let landmarkStability = 0
        if (prevLandmarks.value) {
          const distances = landmarks.map((point, i) => {
            const prevPoint = prevLandmarks.value[i]
            return Math.sqrt(
              Math.pow(point.x - prevPoint.x, 2) +
              Math.pow(point.y - prevPoint.y, 2) +
              Math.pow(point.z - prevPoint.z, 2)
            )
          })
          const avgDistance = distances.reduce((sum, d) => sum + d, 0) / distances.length
          landmarkStability = Math.max(0, 1 - avgDistance * 10)
        } else {
          landmarkStability = 1
        }

        const visibility = 1
        let noFlipPenalty = 1
        if (prevHandedness.value && handedness?.categoryName && handedness.categoryName !== prevHandedness.value) {
          noFlipPenalty = 0
        }

        const finalScore =
          0.4 * handednessScore +
          0.3 * landmarkStability +
          0.2 * visibility +
          0.1 * noFlipPenalty

        confidence.value = `${Math.round(finalScore * 100)}%`
        prevLandmarks.value = landmarks
        prevHandedness.value = handedness?.categoryName

        if (isCollecting.value) {
          addLandmark(results.landmarks, results.handedness, {
            frame_id: cvFrameId.value,
            timestamp_ms: Date.now()
          })
          cvFrameId.value += 1
        }
      } else {
        detectedGesture.value = 'No Hand Detected'
        confidence.value = '--%'
        prevLandmarks.value = null
        prevHandedness.value = null
        if (isCollecting.value) {
          addLandmark([], [], {
            frame_id: cvFrameId.value,
            timestamp_ms: Date.now()
          })
          cvFrameId.value += 1
        }
      }
    })
  },
  { immediate: true }
)

watch(
  () => [isCollecting.value, collectedLandmarks.value.length, frameLimit.value],
  ([collecting, frameCountNow, limit]) => {
    if (!collecting) return
    if (frameCountNow - recordingStartCount.value >= limit) {
      void stopAndAutoSave()
    }
  }
)

watch(terminalLines, () => {
  nextTick(() => {
    scrollTerminalToBottom()
  })
})
</script>

<template>
  <div class="max-w-6xl mx-auto">
    <TrainingSettings v-if="showSettings" @close="showSettings = false" />

    <div class="mb-8 grid grid-cols-[auto_1fr] md:grid-cols-3 items-center gap-3">
      <div class="flex justify-start">
        <BaseBtn
          variant="secondary"
          title="Return to training page"
          class="px-3"
          @click="router.push('/training')"
        >
          &larr;
        </BaseBtn>
      </div>
      <div class="text-left md:text-center">
        <h1 class="text-2xl md:text-3xl font-bold text-white mb-2">{{ pageTitle }}</h1>
        <p class="text-slate-400">
          {{ pageSubtitle }}
        </p>
      </div>
      <div class="hidden md:block"></div>
    </div>

    <div v-if="error" class="text-center mt-12">
      <BaseCard class="max-w-md mx-auto">
        <h3 class="text-xl font-bold text-red-400 mb-2">Permissions Required</h3>
        <p class="text-slate-400 mb-4">
          Camera access is required for {{ permissionTrainingLabel }}. Please grant permissions in your browser settings.
        </p>
        <p class="text-xs text-slate-500">Error: {{ error.name }} - {{ error.message }}</p>
        <BaseBtn class="mt-4" :disabled="isRequesting" @click="startSession">
          {{ isRequesting ? 'Retrying...' : 'Retry' }}
        </BaseBtn>
      </BaseCard>
    </div>

    <div v-else class="grid grid-cols-1 lg:grid-cols-5 gap-6">
      <div class="lg:col-span-3">
        <div class="w-full aspect-video bg-black rounded-2xl border border-slate-700 relative overflow-hidden shadow-2xl">
          <div v-if="!enableCamera" class="absolute inset-0 flex items-center justify-center text-slate-500 bg-black">
            Camera is disabled
          </div>

          <video ref="videoEl" autoplay playsinline muted :class="videoClasses"></video>
          <canvas ref="canvasEl" class="absolute inset-0 w-full h-full"></canvas>

          <div class="absolute top-6 left-6 right-6 flex justify-between items-end">
            <div class="bg-black/60 backdrop-blur px-4 py-2 rounded-lg border border-white/10">
              <div class="text-xs text-slate-400">FPS (Target: 30)</div>
              <div class="text-2xl font-bold" :class="actualFps > 0 ? 'text-white' : 'text-slate-500'">
                {{ actualFps || '--' }}
              </div>
            </div>
            <div class="bg-black/60 backdrop-blur px-4 py-2 rounded-lg border border-white/10">
              <div class="text-xs text-slate-400">Detected Gesture</div>
              <div class="text-2xl font-bold text-white">{{ detectedGesture }}</div>
            </div>
          </div>
          <div class="absolute bottom-6 left-6 right-6 flex justify-between items-end">
            <div class="bg-black/60 backdrop-blur px-4 py-2 rounded-lg border border-white/10">
              <div class="text-xs text-slate-400">Confidence</div>
              <div class="text-2xl font-bold text-slate-400">{{ confidence }}</div>
            </div>
          </div>
          <div v-if="syncCountdown > 0" class="absolute inset-0 flex items-center justify-center">
            <div class="bg-black/70 border border-teal-500/40 text-teal-300 rounded-2xl px-8 py-6 text-5xl font-bold">
              {{ syncCountdown }}
            </div>
          </div>
        </div>

        <div class="mt-6 flex flex-col md:flex-row items-stretch gap-4">
          <BaseBtn variant="primary" :disabled="isRequesting" class="flex-none" @click="startSession">
            {{ isRequesting ? 'Requesting...' : 'Enable Camera Session' }}
          </BaseBtn>

          <CaptureSyncGraph
            :spark-path="sparkPath"
            :cv-path="cvPath"
            :spark-threshold="sparkThreshold"
            :cv-threshold="cvThreshold"
            :spark-peak="sparkPeak"
            :cv-peak="cvPeak"
            :spark-spike="sparkSpike"
            :cv-spike="cvSpike"
            :sensor-spike-active="sensorSpikeActive"
            :cv-spike-active="cvSpikeActive"
            :sync-offset-ms="syncOffsetMs"
            :sync-ws-connected="syncWsConnected"
            :expected-sync-label="expectedSyncLabel"
          />
        </div>

        <div class="mt-6">
          <CaptureTerminal
            ref="terminalComponent"
            :is-streaming="isTerminalStreaming"
            :terminal-lines="terminalLines"
            :terminal-error="terminalError"
            :auto-scroll="terminalAutoScroll"
            @toggle-stream="toggleTerminalStream"
            @update:auto-scroll="terminalAutoScroll = $event"
          >
            <template #subtitle>
              {{
                (sensorCaptureStatus.status === 'running'
                  ? sensorCaptureStatus.mode
                  : captureMode) === 'dual'
                  ? 'Dual-hand'
                  : 'Single-hand'
              }} collector output
            </template>
          </CaptureTerminal>
        </div>
      </div>

      <div class="lg:col-span-2 lg:sticky lg:top-6 self-start">
        <BaseCard class="w-full">
          <div class="flex justify-between items-center mb-4">
            <h3 class="text-lg font-bold text-white">Session Workflow</h3>
            <BaseBtn variant="secondary" @click="showSettings = true">Settings</BaseBtn>
          </div>

          <div class="mb-4 rounded-xl border border-slate-800 bg-slate-950/40 px-4 py-3">
            <div class="flex items-center justify-between">
              <p class="text-xs uppercase tracking-wide text-slate-400">Flow Status</p>
              <span class="text-xs rounded-full px-3 py-1 border" :class="workflowStep === 4 ? 'border-emerald-500/40 text-emerald-300' : 'border-amber-500/40 text-amber-300'">
                Step {{ workflowStep }} of 4
              </span>
            </div>
            <p class="text-sm text-slate-300 mt-2">{{ flowHint }}</p>
          </div>

          <div class="mb-4 grid grid-cols-1 gap-3">
            <div class="rounded-xl border p-3" :class="isSessionActive ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-slate-800 bg-slate-950/40'">
              <p class="text-[11px] uppercase tracking-wide text-slate-400">1. Camera Session</p>
              <p class="text-sm mt-1" :class="isSessionActive ? 'text-emerald-300' : 'text-amber-300'">
                {{ isSessionActive ? 'Active' : 'Inactive' }}
              </p>
              <BaseBtn class="mt-3 w-full" variant="secondary" :disabled="isRequesting" @click="startSession">
                {{ isRequesting ? 'Requesting...' : 'Enable Camera Session' }}
              </BaseBtn>
            </div>

            <div class="rounded-xl border p-3" :class="sensorReady ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-slate-800 bg-slate-950/40'">
              <p class="text-[11px] uppercase tracking-wide text-slate-400">2. Sensor Source</p>
              <p class="text-sm mt-1" :class="isSensorRunning ? 'text-emerald-300' : 'text-amber-300'">
                {{ isSensorRunning ? 'Service Running' : 'Service Stopped' }}
              </p>
              <p class="text-xs text-slate-500 mt-1">
                Mode: {{ captureMode === 'dual' ? 'Dual hand' : 'Single hand' }}
              </p>
              <div class="mt-3">
                <label class="block text-xs text-slate-400 mb-1">Capture Mode</label>
                <select v-model="captureMode" class="bg-slate-700 border border-slate-600 rounded-md px-3 py-2 text-white w-full">
                  <option value="single">Single Hand</option>
                  <option value="dual">Dual Hand</option>
                </select>
              </div>
              <div class="flex flex-wrap gap-2 mt-3">
                <label class="block text-xs text-slate-400 w-full">
                  Max Samples (optional)
                  <input
                    v-model.number="sensorMaxSamples"
                    type="number"
                    min="0"
                    class="mt-1 w-full rounded border border-slate-700 bg-slate-950/70 px-2 py-1 text-slate-200"
                    placeholder="0 = unlimited"
                  />
                </label>
                <BaseBtn variant="secondary" class="flex-1 min-w-[120px]" @click="startSensorCapture(captureMode, sensorMaxSamples)">
                  Start Sensor Service
                </BaseBtn>
                <BaseBtn variant="secondary" class="flex-1 min-w-[120px]" @click="stopSensorCapture">
                  Stop Sensor Service
                </BaseBtn>
              </div>
            </div>
          </div>

          <div class="mb-4">
            <label class="block text-sm text-slate-400 mb-2">Gesture Name</label>
            <input
              v-model="currentGestureName"
              type="text"
              placeholder="e.g., hello, thanks"
              class="w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white focus:border-teal-500 focus:outline-none"
              :disabled="isCollecting || isAwaitingSyncCue"
            />
          </div>

          <div class="mb-4 grid grid-cols-1 gap-2">
            <BaseBtn
              v-if="!isCollecting"
              :disabled="!canStartTake"
              variant="primary"
              @click="startRecording"
            >
              {{ isAwaitingSyncCue ? 'Syncing...' : '3. Start Recording' }}
            </BaseBtn>
            <BaseBtn v-else variant="danger" @click="stopTake">Stop Recording</BaseBtn>
            <BaseBtn v-if="isAwaitingSyncCue" variant="secondary" @click="cancelPendingRecording">
              Cancel Sync Cue
            </BaseBtn>
            <BaseBtn variant="secondary" @click="triggerSyncCue">Manual Sync Cue</BaseBtn>
          </div>

          <div class="grid grid-cols-1 gap-2">
            <BaseBtn
              :disabled="!canExportFusion"
              variant="secondary"
              @click="downloadCvSensorCsv"
            >
              {{ isExportingSensorCsv ? 'Preparing...' : '4. Export CV+Sensor CSV' }}
            </BaseBtn>

            <BaseBtn
              :disabled="collectedLandmarks.length === 0"
              variant="secondary"
              @click="clearData"
            >
              Clear Data
            </BaseBtn>

            <BaseBtn variant="secondary" @click="resetRecording">Reset</BaseBtn>
          </div>

          <div class="mt-4 border border-slate-800 rounded-lg bg-slate-950/40 p-3">
            <button class="w-full flex items-center justify-between text-sm text-slate-200" @click="showAdvancedControls = !showAdvancedControls">
              <span>Advanced Details</span>
              <span class="text-xs text-slate-500">{{ showAdvancedControls ? 'Hide' : 'Show' }}</span>
            </button>
          </div>

          <div v-if="showAdvancedControls" class="mt-4 border border-slate-800 bg-black/70 rounded-lg px-4 py-3 font-mono text-xs text-slate-200">
            <div class="text-slate-500 mb-2">
              Left: <span :class="serialStatus.left_connected ? 'text-green-400' : 'text-red-400'">{{ serialStatus.left_connected ? 'Online' : 'Offline' }}</span>
              ({{ serialStatus.left_port || '--' }})
            </div>
            <div class="text-slate-500 mb-2">
              Right: <span :class="serialStatus.right_connected ? 'text-green-400' : 'text-red-400'">{{ serialStatus.right_connected ? 'Online' : 'Offline' }}</span>
              ({{ serialStatus.right_port || '--' }})
            </div>
            <div class="text-slate-500 mb-2">
              Available ports: {{ serialStatus.available_ports?.length ? serialStatus.available_ports.join(', ') : '--' }}
            </div>
            <div class="text-slate-500 mb-2">Take Console</div>
            <div v-if="takeLogs.length === 0" class="text-slate-500">
              No takes recorded yet.
            </div>
            <div v-else class="space-y-1 max-h-28 overflow-y-auto">
              <div v-for="(line, idx) in takeLogs" :key="`take-log-${idx}`">
                <span class="text-emerald-400">$</span>
                <span class="ml-2">{{ line }}</span>
              </div>
            </div>
          </div>

          <div class="mt-4 text-sm">
            <div v-if="isAwaitingSyncCue" class="text-amber-400 font-semibold">
              Sync cue active. Recording starts when countdown reaches 0.
            </div>
            <div v-if="isCollecting" class="text-green-400 font-semibold">
              Recording "{{ currentGestureName }}"...
            </div>
            <div v-if="exportStatusMessage" class="text-xs text-sky-300 mt-1">
              {{ exportStatusMessage }}
            </div>
            <div class="text-slate-400">
              Frames collected: <span class="text-white font-bold">{{ framesInCurrentTake }}</span>
              <span class="text-slate-500"> / {{ frameLimit }}</span>
            </div>
          </div>

          <div class="mt-6">
            <BaseBtn variant="danger" class="w-full" @click="router.push('/training')">
              End Session
            </BaseBtn>
          </div>
        </BaseCard>
      </div>
    </div>

    
  </div>
</template>
