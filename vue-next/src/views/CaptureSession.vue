<script setup>
import { ref, watch, computed, nextTick, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import TrainingSettings from '../components/TrainingSettings.vue'
import CaptureSyncGraph from '../components/CaptureSyncGraph.vue'
import CaptureTerminal from '../components/CaptureTerminal.vue'
import { useMediaPermissions } from '../composables/useMediaPermissions.js'
import { useTrainingSettings } from '../composables/useTrainingSettings.js'
import { useHandTracking } from '../composables/useHandTracking.js'
import { useCollectData } from '../composables/useCollectData.js'
import { useCollectorLogs } from '../composables/useCollectorLogs.js'
import { useSyncStream } from '../composables/useSyncStream.js'
import { useSensorStatus } from '../composables/useSensorStatus.js'

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
const router = useRouter()
const captureMode = ref('single')
const syncCountdown = ref(0)
const terminalComponent = ref(null)

const {
  collectedLandmarks,
  isCollecting,
  currentGestureName,
  metadata,
  startCollecting,
  stopCollecting,
  addLandmark,
  downloadCSV,
  clearData
} = useCollectData()

const {
  hasPermissions,
  isRequesting,
  error,
  stream,
  requestPermissions,
  stopStream
} = useMediaPermissions()

const { mirrorCamera, enableCamera, showLandmarks, frameLimit } = useTrainingSettings()
const { startHandTracking, stopHandTracking, onFrame } = useHandTracking(mirrorCamera, showLandmarks)

const {
  serialStatus,
  sensorCaptureStatus,
  startSensorCapture,
  stopSensorCapture
} = useSensorStatus()

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
} = useSyncStream(captureMode, isSessionActive)

const videoClasses = computed(() => [
  'w-full',
  'h-full',
  'object-cover',
  { '-scale-x-100': mirrorCamera.value }
])

let frameCount = 0
let lastTime = performance.now()
let fpsInterval = null

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

const stopSession = () => {
  stopHandTracking()
  stopFpsCounter()
  stopStream()
  isSessionActive.value = false
  showSettings.value = false
}

const startRecording = () => {
  metadata.value.fps = 30
  metadata.value.frame_limit = frameLimit.value
  recordingStartCount.value = collectedLandmarks.value.length
  cvFrameId.value = 0
  startCollecting(currentGestureName.value)
}

const resetRecording = () => {
  stopCollecting()
  clearData()
  recordingStartCount.value = 0
}

const triggerSyncCue = () => {
  if (syncCountdown.value > 0) return
  syncCountdown.value = 3
  const timer = setInterval(() => {
    syncCountdown.value -= 1
    if (syncCountdown.value <= 0) {
      clearInterval(timer)
    }
  }, 1000)
}

const scrollTerminalToBottom = () => {
  const el = terminalComponent.value?.terminalEl
  if (!el || !terminalAutoScroll.value) return
  el.scrollTop = el.scrollHeight
}

onUnmounted(() => {
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
          stopCollecting()
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
      stopCollecting()
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

    <div class="mb-8 flex items-center justify-between">
      <div>
        <h1 class="text-3xl font-bold text-white mb-2">Capture Session</h1>
        <p class="text-slate-400">
          Record labeled gestures with consistent frame caps and CSV export.
        </p>
      </div>
      <BaseBtn variant="secondary" @click="router.push('/training')">
        Return
      </BaseBtn>
    </div>

    <div v-if="error" class="text-center mt-12">
      <BaseCard class="max-w-md mx-auto">
        <h3 class="text-xl font-bold text-red-400 mb-2">Permissions Required</h3>
        <p class="text-slate-400 mb-4">
          Camera access is required for capture. Please grant permissions in your browser settings.
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

        <div v-if="!isSessionActive" class="mt-6 flex items-stretch gap-4">
          <BaseBtn variant="primary" :disabled="isRequesting" class="flex-none" @click="startSession">
            {{ isRequesting ? 'Requesting...' : 'Start Capture Session' }}
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
            :sync-ws-connected="syncWsConnected"
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
            <h3 class="text-lg font-bold text-white">Capture Controls</h3>
            <BaseBtn variant="secondary" @click="showSettings = true">Settings</BaseBtn>
          </div>

          <div class="mb-4 space-y-2 text-sm">
            <div class="flex items-center justify-between">
              <span class="text-slate-400">Glove Left</span>
              <span :class="serialStatus.left_connected ? 'text-green-400' : 'text-red-400'">
                {{ serialStatus.left_connected ? 'Online' : 'Offline' }}
              </span>
            </div>
            <div class="text-xs text-slate-500">
              Port: {{ serialStatus.left_port || '--' }}
            </div>
            <div class="flex items-center justify-between">
              <span class="text-slate-400">Glove Right</span>
              <span :class="serialStatus.right_connected ? 'text-green-400' : 'text-red-400'">
                {{ serialStatus.right_connected ? 'Online' : 'Offline' }}
              </span>
            </div>
            <div class="text-xs text-slate-500">
              Port: {{ serialStatus.right_port || '--' }}
            </div>
          </div>

          <div class="mb-4 text-xs text-slate-500">
            Available ports: {{ serialStatus.available_ports?.length ? serialStatus.available_ports.join(', ') : '--' }}
          </div>

          <div class="mb-4">
            <label class="block text-sm text-slate-400 mb-2">Capture Mode</label>
            <select v-model="captureMode" class="bg-slate-700 border border-slate-600 rounded-md px-3 py-2 text-white w-full">
              <option value="single">Single Hand</option>
              <option value="dual">Dual Hand</option>
            </select>
          </div>

          <div class="mb-4 space-y-2">
            <div class="flex items-center justify-between text-sm">
              <span class="text-slate-400">Sensor Capture</span>
              <span :class="sensorCaptureStatus.status === 'running' ? 'text-green-400' : 'text-red-400'">
                {{ sensorCaptureStatus.status === 'running' ? 'Running' : 'Stopped' }}
              </span>
            </div>
            <div class="flex gap-3">
              <BaseBtn variant="primary" @click="startSensorCapture(captureMode)">Start Sensor</BaseBtn>
              <BaseBtn variant="secondary" @click="stopSensorCapture">Stop Sensor</BaseBtn>
            </div>
          </div>

          <div class="mb-4">
            <label class="block text-sm text-slate-400 mb-2">Gesture Name</label>
            <input
              v-model="currentGestureName"
              type="text"
              placeholder="e.g., hello, thanks"
              class="w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white focus:border-teal-500 focus:outline-none"
              :disabled="isCollecting"
            />
          </div>

          <div class="flex flex-wrap gap-3">
            <BaseBtn
              v-if="!isCollecting"
              :disabled="!currentGestureName.trim()"
              variant="primary"
              @click="startRecording"
            >
              Start Recording
            </BaseBtn>
            <BaseBtn v-else variant="danger" @click="stopCollecting">Stop Recording</BaseBtn>

            <BaseBtn
              :disabled="collectedLandmarks.length === 0"
              variant="secondary"
              @click="downloadCSV"
            >
              Download CSV
            </BaseBtn>

            <BaseBtn
              :disabled="collectedLandmarks.length === 0"
              variant="secondary"
              @click="clearData"
            >
              Clear Data
            </BaseBtn>

            <BaseBtn variant="secondary" @click="resetRecording">Reset</BaseBtn>
            <BaseBtn variant="secondary" @click="triggerSyncCue">Sync Cue</BaseBtn>
          </div>

          <div class="mt-4 text-sm">
            <div v-if="isCollecting" class="text-green-400 font-semibold">
              Recording "{{ currentGestureName }}"...
            </div>
            <div class="text-slate-400">
              Frames collected: <span class="text-white font-bold">{{ collectedLandmarks.length - recordingStartCount }}</span>
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
