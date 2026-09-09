<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useToast } from 'primevue/usetoast'
import {
  PhBrain,
  PhCircleNotch,
  PhDownloadSimple,
  PhRecord,
  PhSpeakerHigh,
  PhStop,
  PhVideoCamera,
  PhWarningCircle
} from '@phosphor-icons/vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import BaseCard from '../components/base/BaseCard.vue'
import api from '../services/api'
import { useFaceEmotion, LOCAL_MODEL_URL } from '../composables/ai/useFaceEmotion'
import { EMOTION_LABELS, EMOTION_META } from '../composables/ai/emotionModel'

/*
 * Emotion Studio — the camera-side counterpart to the gesture playground.
 *
 * MediaPipe FaceLandmarker locates the face and reports its 52 blendshapes;
 * the FER+ CNN (ONNX, running in this tab through onnxruntime-web) turns the
 * cropped face into a distribution over eight emotion classes. No backend
 * inference is involved, so this page works against a dev server with no
 * TensorFlow or PyTorch sidecar running.
 */

const toast = useToast()

const videoEl = ref(null)
const overlayEl = ref(null)
const timelineEl = ref(null)
const mediaStream = ref(null)
const cameras = ref([])
const selectedCamera = ref('')
const cameraError = ref(null)
const isStarting = ref(false)

// Tuning knobs, handed to the composable as refs so changes take effect live.
const mirror = ref(true)
const showMesh = ref(true)
const smoothing = ref(0.6)
const inferenceFps = ref(12)
const threshold = ref(0.35)
const announce = ref(false)

const {
  isLoading,
  isRunning,
  loadError,
  loadErrorStage,
  modelSource,
  faceDetected,
  distribution,
  dominant,
  inferenceMs,
  measuredFps,
  signals,
  history,
  isRecording,
  start,
  stop,
  startRecording,
  stopRecording,
  saveToCSV,
  emotionColor
} = useFaceEmotion({ mirror, showMesh, smoothing, inferenceFps, threshold })

const dominantMeta = computed(() => (dominant.value ? EMOTION_META[dominant.value.label] : null))
const usingRemoteWeights = computed(() => Boolean(modelSource.value) && !modelSource.value.startsWith('/'))

/*
 * Three distinct failures wear the same "model would not load" hat, and each
 * has a different fix. Say which one happened.
 */
const failureHint = computed(() => {
  switch (loadErrorStage.value) {
    case 'weights':
      return {
        title: 'The FER+ weights could not be fetched',
        body: 'weights'
      }
    case 'runtime':
      return {
        title: 'onnxruntime-web could not start',
        body: 'runtime'
      }
    case 'detector':
      return {
        title: 'The MediaPipe face detector could not be fetched',
        body: 'detector'
      }
    default:
      return { title: 'Emotion recognition could not start', body: 'unknown' }
  }
})

const statusLine = computed(() => {
  if (loadError.value) return { text: 'Model failed to load', tone: 'text-danger-300' }
  if (isLoading.value) return { text: 'Loading FER+ weights…', tone: 'text-warning-300' }
  if (!isRunning.value) return { text: 'Camera idle', tone: 'text-slate-400' }
  if (!faceDetected.value) return { text: 'Searching for a face…', tone: 'text-warning-300' }
  return { text: 'Tracking', tone: 'text-success-300' }
})

// ---------------------------------------------------------------------------
// Camera
// ---------------------------------------------------------------------------
const listCameras = async () => {
  try {
    const devices = await navigator.mediaDevices.enumerateDevices()
    cameras.value = devices.filter((d) => d.kind === 'videoinput')
    if (!selectedCamera.value && cameras.value[0]) selectedCamera.value = cameras.value[0].deviceId
  } catch (error) {
    console.warn('[EmotionStudio] could not enumerate cameras:', error)
  }
}

const stopStream = () => {
  mediaStream.value?.getTracks().forEach((track) => track.stop())
  mediaStream.value = null
}

const startCamera = async () => {
  isStarting.value = true
  cameraError.value = null
  try {
    stopStream()
    mediaStream.value = await navigator.mediaDevices.getUserMedia({
      video: {
        deviceId: selectedCamera.value ? { exact: selectedCamera.value } : undefined,
        width: { ideal: 1280 },
        height: { ideal: 720 },
        facingMode: 'user'
      },
      audio: false
    })
    // Labels are only exposed once permission is granted, so refresh the list.
    await listCameras()
    await start(videoEl.value, overlayEl.value, mediaStream.value)
  } catch (error) {
    cameraError.value = error.message || String(error)
    stopStream()
    toast.add({
      severity: 'error',
      summary: 'Could not start',
      detail: cameraError.value,
      life: 5000
    })
  } finally {
    isStarting.value = false
  }
}

const stopCamera = () => {
  if (isRecording.value) stopRecording()
  stop()
  stopStream()
}

watch(selectedCamera, () => {
  if (isRunning.value) startCamera()
})

// ---------------------------------------------------------------------------
// Recording
// ---------------------------------------------------------------------------
const toggleRecording = () => {
  if (!isRecording.value) {
    startRecording()
    return
  }
  const samples = stopRecording()
  const rows = saveToCSV(samples)
  toast.add({
    severity: rows ? 'success' : 'warn',
    summary: rows ? 'Session exported' : 'Nothing recorded',
    detail: rows ? `${rows} rows written to CSV.` : 'No classifications were captured.',
    life: 4000
  })
}

// ---------------------------------------------------------------------------
// Spoken announcements
//
// The backend TTS route is the same one the gesture pipeline speaks through.
// Only announce a label once it has held steady, or a flickering argmax turns
// the page into a stutter machine.
// ---------------------------------------------------------------------------
const STABLE_MS = 1200
const COOLDOWN_MS = 3000
let candidate = null
let candidateSince = 0
let lastSpoken = null
let lastSpokenAt = 0

const maybeAnnounce = (sample) => {
  if (!announce.value || !sample.dominant) return

  if (sample.dominant !== candidate) {
    candidate = sample.dominant
    candidateSince = sample.timestamp
    return
  }
  if (sample.timestamp - candidateSince < STABLE_MS) return
  if (candidate === lastSpoken && sample.timestamp - lastSpokenAt < COOLDOWN_MS) return

  lastSpoken = candidate
  lastSpokenAt = sample.timestamp
  // Fire and forget: a missing backend must not break the live preview.
  api.utils.tts
    .speakTest(EMOTION_META[candidate].display, true)
    .catch((error) => console.warn('[EmotionStudio] TTS unavailable:', error?.message))
}

// ---------------------------------------------------------------------------
// Timeline strip — one coloured column per classification, alpha by confidence
// ---------------------------------------------------------------------------
const drawTimeline = () => {
  const canvas = timelineEl.value
  if (!canvas) return

  const width = canvas.clientWidth || 640
  const height = canvas.clientHeight || 72
  const dpr = window.devicePixelRatio || 1
  if (canvas.width !== Math.round(width * dpr) || canvas.height !== Math.round(height * dpr)) {
    canvas.width = Math.round(width * dpr)
    canvas.height = Math.round(height * dpr)
  }

  const ctx = canvas.getContext('2d')
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, width, height)

  const samples = history.value
  if (!samples.length) return

  const columnWidth = width / samples.length
  samples.forEach((sample, index) => {
    if (!sample.dominant) return
    ctx.globalAlpha = 0.35 + sample.confidence * 0.65
    ctx.fillStyle = emotionColor(sample.dominant)
    // A whole-pixel overlap keeps the columns from showing hairline seams.
    ctx.fillRect(index * columnWidth, 0, columnWidth + 0.5, height)
  })
  ctx.globalAlpha = 1
}

watch(history, () => {
  drawTimeline()
  const latest = history.value[history.value.length - 1]
  if (latest) maybeAnnounce(latest)
})

onMounted(() => {
  listCameras()
  window.addEventListener('resize', drawTimeline)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', drawTimeline)
  stopCamera()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 class="text-3xl font-bold text-white">Emotion Studio</h1>
        <p class="text-slate-400">
          MediaPipe face landmarks feeding an ONNX FER+ classifier, entirely in this tab.
        </p>
      </div>
      <div class="flex flex-wrap gap-2">
        <BaseBtn
          v-if="!isRunning"
          variant="primary"
          :disabled="isStarting || isLoading"
          @click="startCamera"
        >
          <span class="flex items-center gap-2">
            <PhCircleNotch v-if="isStarting || isLoading" size="18" weight="bold" class="animate-spin" />
            <PhVideoCamera v-else size="18" weight="bold" />
            {{ isLoading ? 'Loading model…' : 'Start camera' }}
          </span>
        </BaseBtn>
        <BaseBtn v-else variant="danger" @click="stopCamera">
          <span class="flex items-center gap-2">
            <PhStop size="18" weight="bold" />
            Stop
          </span>
        </BaseBtn>
        <BaseBtn
          :variant="isRecording ? 'warning' : 'secondary'"
          :disabled="!isRunning"
          @click="toggleRecording"
        >
          <span class="flex items-center gap-2">
            <PhRecord v-if="!isRecording" size="18" weight="bold" />
            <PhDownloadSimple v-else size="18" weight="bold" />
            {{ isRecording ? 'Stop & export CSV' : 'Record session' }}
          </span>
        </BaseBtn>
      </div>
    </div>

    <!-- Model load failure: the one state the page cannot recover from on its own -->
    <div
      v-if="loadError"
      class="flex flex-col gap-2 rounded-lg border border-danger-500/30 bg-danger-500/5 px-4 py-3"
    >
      <div class="flex items-center gap-2 text-sm font-semibold text-danger-300">
        <PhWarningCircle size="18" weight="bold" />
        {{ failureHint.title }}
      </div>

      <p v-if="failureHint.body === 'weights'" class="text-xs text-slate-400">
        Vendor them locally with
        <code class="rounded bg-slate-900 px-1.5 py-0.5 text-brand-200">npm run model:emotion</code>
        (writes <code class="text-slate-300">public{{ LOCAL_MODEL_URL }}</code>), or point
        <code class="text-slate-300">VITE_EMOTION_MODEL_URL</code> at your own copy. The weights
        themselves are fine — only the fetch failed.
      </p>

      <p v-else-if="failureHint.body === 'runtime'" class="text-xs text-slate-400">
        The weights downloaded, but the WASM backend would not initialise. A
        <code class="text-slate-300">magic number</code> error means the dev server answered the
        <code class="text-slate-300">.wasm</code> request with HTML — check that
        <code class="rounded bg-slate-900 px-1.5 py-0.5 text-brand-200">optimizeDeps.exclude</code>
        in <code class="text-slate-300">vite.config.js</code> still lists
        <code class="text-slate-300">onnxruntime-web</code>, and restart Vite so it drops its
        <code class="text-slate-300">node_modules/.vite</code> cache. Otherwise your browser may
        lack WebAssembly SIMD.
      </p>

      <p v-else-if="failureHint.body === 'detector'" class="text-xs text-slate-400">
        <code class="text-slate-300">face_landmarker.task</code> and the MediaPipe vision runtime
        are fetched from Google's CDN at load time, so this page needs network access on first
        run even when the FER+ weights are vendored locally.
      </p>

      <p v-else class="text-xs text-slate-400">
        See the browser console for the full stack; the stage that failed is logged there.
      </p>
      <pre class="overflow-x-auto whitespace-pre-wrap text-[11px] leading-relaxed text-slate-500">{{ loadError }}</pre>
    </div>

    <div class="grid grid-cols-1 gap-6 xl:grid-cols-3">
      <!-- Camera -->
      <BaseCard class="xl:col-span-2 !p-0 overflow-hidden">
        <div class="relative aspect-video w-full bg-black">
          <video
            ref="videoEl"
            autoplay
            playsinline
            muted
            class="absolute inset-0 h-full w-full object-contain"
            :class="{ '-scale-x-100': mirror }"
          ></video>
          <!-- object-contain on both layers keeps the overlay pixel-aligned
               with the frame whatever aspect ratio the camera reports. -->
          <canvas ref="overlayEl" class="absolute inset-0 h-full w-full object-contain"></canvas>

          <div
            v-if="!isRunning"
            class="absolute inset-0 flex flex-col items-center justify-center gap-2 text-center"
          >
            <PhBrain size="40" weight="duotone" class="text-slate-600" />
            <p class="text-sm text-slate-500">Start the camera to begin recognition.</p>
          </div>

          <!-- Status strip -->
          <div
            class="absolute inset-x-0 bottom-0 flex flex-wrap items-center gap-x-5 gap-y-1 bg-slate-950/70 px-4 py-2 text-[11px] backdrop-blur"
          >
            <span class="flex items-center gap-1.5 font-semibold" :class="statusLine.tone">
              <span class="h-1.5 w-1.5 rounded-full bg-current"></span>
              {{ statusLine.text }}
            </span>
            <span class="text-slate-500">
              Latency <span class="text-slate-300">{{ inferenceMs }} ms</span>
            </span>
            <span class="text-slate-500">
              Rate <span class="text-slate-300">{{ measuredFps.toFixed(1) }}/s</span>
            </span>
            <span v-if="modelSource" class="text-slate-500">
              Weights
              <span class="text-slate-300">{{ usingRemoteWeights ? 'remote (CDN)' : 'local' }}</span>
            </span>
          </div>
        </div>
      </BaseCard>

      <!-- Readout -->
      <div class="space-y-6">
        <BaseCard>
          <div class="flex items-center justify-between">
            <span class="text-[10px] font-bold uppercase tracking-widest text-slate-500">
              Dominant emotion
            </span>
            <span v-if="dominant" class="text-xs font-semibold" :class="dominantMeta.textClass">
              {{ (dominant.probability * 100).toFixed(1) }}%
            </span>
          </div>

          <div class="mt-4 flex items-center gap-4">
            <span class="text-5xl leading-none">{{ dominantMeta?.emoji ?? '🙂' }}</span>
            <div>
              <p class="text-2xl font-bold" :class="dominantMeta?.textClass ?? 'text-slate-500'">
                {{ dominantMeta?.display ?? 'Uncertain' }}
              </p>
              <p class="text-xs text-slate-500">
                {{ faceDetected ? 'Face locked' : 'No face in frame' }}
              </p>
            </div>
          </div>

          <!-- Full distribution, fixed class order so bars stay where the eye
               left them rather than reshuffling every frame. -->
          <div class="mt-5 space-y-2">
            <div v-for="label in EMOTION_LABELS" :key="label" class="space-y-1">
              <div class="flex items-baseline justify-between text-[11px]">
                <span class="text-slate-400">
                  {{ EMOTION_META[label].emoji }} {{ EMOTION_META[label].display }}
                </span>
                <span class="tabular-nums text-slate-500">
                  {{ ((distribution[label] || 0) * 100).toFixed(1) }}%
                </span>
              </div>
              <div class="h-1.5 overflow-hidden rounded-full bg-slate-800">
                <div
                  class="h-full rounded-full transition-[width] duration-150 ease-out"
                  :class="EMOTION_META[label].barClass"
                  :style="{ width: `${Math.min((distribution[label] || 0) * 100, 100)}%` }"
                ></div>
              </div>
            </div>
          </div>
        </BaseCard>

        <!-- MediaPipe's geometric read, next to the CNN's -->
        <BaseCard>
          <span class="text-[10px] font-bold uppercase tracking-widest text-slate-500">
            Blendshape signals
          </span>
          <div class="mt-4 space-y-2">
            <div v-for="signal in signals" :key="signal.key" class="flex items-center gap-3">
              <span class="w-24 shrink-0 text-[11px] text-slate-400">{{ signal.label }}</span>
              <div class="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-800">
                <div
                  class="h-full rounded-full bg-brand-400 transition-[width] duration-150 ease-out"
                  :style="{ width: `${Math.min(signal.score * 100, 100)}%` }"
                ></div>
              </div>
              <span class="w-9 shrink-0 text-right text-[11px] tabular-nums text-slate-500">
                {{ (signal.score * 100).toFixed(0) }}
              </span>
            </div>
          </div>
        </BaseCard>
      </div>
    </div>

    <!-- Timeline -->
    <BaseCard>
      <div class="flex items-center justify-between">
        <span class="text-[10px] font-bold uppercase tracking-widest text-slate-500">
          Recent history
        </span>
        <span class="text-[11px] text-slate-500">{{ history.length }} classifications</span>
      </div>
      <canvas ref="timelineEl" class="mt-3 h-16 w-full rounded-lg bg-slate-900/60"></canvas>
      <div class="mt-3 flex flex-wrap gap-x-4 gap-y-1">
        <span
          v-for="label in EMOTION_LABELS"
          :key="label"
          class="flex items-center gap-1.5 text-[10px] text-slate-500"
        >
          <span class="h-2 w-2 rounded-sm" :class="EMOTION_META[label].barClass"></span>
          {{ EMOTION_META[label].display }}
        </span>
      </div>
    </BaseCard>

    <!-- Controls -->
    <BaseCard>
      <span class="text-[10px] font-bold uppercase tracking-widest text-slate-500">Controls</span>
      <div class="mt-4 grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
        <label class="space-y-2 text-xs">
          <span class="text-slate-400">Camera</span>
          <select
            v-model="selectedCamera"
            class="focus-ring w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-brand-500 focus:outline-none"
          >
            <option v-if="!cameras.length" value="">Default camera</option>
            <option v-for="(device, index) in cameras" :key="device.deviceId" :value="device.deviceId">
              {{ device.label || `Camera ${index + 1}` }}
            </option>
          </select>
        </label>

        <label class="space-y-2 text-xs">
          <span class="flex justify-between text-slate-400">
            <span>Smoothing</span>
            <span class="tabular-nums text-slate-300">{{ smoothing.toFixed(2) }}</span>
          </span>
          <input
            v-model.number="smoothing"
            type="range"
            min="0"
            max="0.9"
            step="0.05"
            class="w-full accent-brand-500"
          />
          <span class="block text-[10px] text-slate-500">Weight kept from the previous frame.</span>
        </label>

        <label class="space-y-2 text-xs">
          <span class="flex justify-between text-slate-400">
            <span>Inference rate</span>
            <span class="tabular-nums text-slate-300">{{ inferenceFps }}/s</span>
          </span>
          <input
            v-model.number="inferenceFps"
            type="range"
            min="2"
            max="30"
            step="1"
            class="w-full accent-brand-500"
          />
          <span class="block text-[10px] text-slate-500">Landmarks always track at 30 fps.</span>
        </label>

        <label class="space-y-2 text-xs">
          <span class="flex justify-between text-slate-400">
            <span>Confidence floor</span>
            <span class="tabular-nums text-slate-300">{{ (threshold * 100).toFixed(0) }}%</span>
          </span>
          <input
            v-model.number="threshold"
            type="range"
            min="0.1"
            max="0.9"
            step="0.05"
            class="w-full accent-brand-500"
          />
          <span class="block text-[10px] text-slate-500">Below this the page says "Uncertain".</span>
        </label>
      </div>

      <div class="mt-5 flex flex-wrap gap-x-6 gap-y-3 border-t border-slate-800/60 pt-4 text-sm">
        <label class="flex cursor-pointer items-center gap-2">
          <input v-model="mirror" type="checkbox" class="accent-brand-500" />
          <span class="text-slate-300">Mirror view</span>
        </label>
        <label class="flex cursor-pointer items-center gap-2">
          <input v-model="showMesh" type="checkbox" class="accent-brand-500" />
          <span class="text-slate-300">Show face mesh</span>
        </label>
        <label class="flex cursor-pointer items-center gap-2">
          <input v-model="announce" type="checkbox" class="accent-brand-500" />
          <span class="flex items-center gap-1.5 text-slate-300">
            <PhSpeakerHigh size="16" weight="bold" />
            Speak the emotion
          </span>
        </label>
      </div>
    </BaseCard>

    <!-- Provenance. A testing ground should always say which weights produced
         the numbers on screen. -->
    <p class="text-[11px] leading-relaxed text-slate-500">
      Classifier: <span class="text-slate-400">emotion-ferplus-8</span> from the ONNX Model Zoo — a
      VGG-style CNN trained on the FER+ re-annotation of FER2013, 64×64 grayscale input, eight
      classes. Detection and blendshapes: MediaPipe <span class="text-slate-400">face_landmarker</span>
      (478 landmarks, 52 blendshapes). Both run client-side; nothing is uploaded.
    </p>
  </div>
</template>
