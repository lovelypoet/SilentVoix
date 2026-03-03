<script setup>
import { computed, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import { useHandTracking } from '../composables/useHandTracking.js'

const router = useRouter()

const modelFile = ref(null)
const metadataFile = ref(null)
const metadata = ref(null)
const validationErrors = ref([])
const uploadMessage = ref('')

const mirrorCamera = ref(false)
const showLandmarks = ref(true)
const videoEl = ref(null)
const landmarkCanvasEl = ref(null)
const bboxCanvasEl = ref(null)
const mediaStream = ref(null)
const isLive = ref(false)
const liveStatus = ref('Camera idle.')
const prediction = ref(null)

const { startHandTracking, stopHandTracking, onFrame } = useHandTracking(mirrorCamera, showLandmarks)

const modelSummary = computed(() => {
  if (!metadata.value) return null
  const m = metadata.value
  return {
    name: m.model_name,
    family: m.model_family,
    labels: Array.isArray(m.labels) ? m.labels : [],
    inputSpec: m.input_spec,
    format: m.export_format,
    version: m.version,
    precision: m.precision,
    recall: m.recall,
    f1: m.f1
  }
})

const parseJsonFile = (file) => new Promise((resolve, reject) => {
  const reader = new FileReader()
  reader.onload = () => {
    try {
      resolve(JSON.parse(String(reader.result || '{}')))
    } catch (e) {
      reject(e)
    }
  }
  reader.onerror = () => reject(new Error('Failed to read metadata file'))
  reader.readAsText(file)
})

const validateMetadata = (m) => {
  const errs = []
  if (!m || typeof m !== 'object') errs.push('Metadata must be a JSON object.')
  if (!m?.model_name) errs.push('Missing `model_name`.')
  if (!m?.model_family) errs.push('Missing `model_family`.')
  if (!m?.input_spec) errs.push('Missing `input_spec`.')
  if (!Array.isArray(m?.labels) || m.labels.length === 0) errs.push('`labels` must be a non-empty array.')
  if (!m?.export_format) errs.push('Missing `export_format`.')
  if (!m?.version) errs.push('Missing `version`.')
  if (typeof m?.precision !== 'number') errs.push('Missing numeric `precision`.')
  if (typeof m?.recall !== 'number') errs.push('Missing numeric `recall`.')
  if (typeof m?.f1 !== 'number') errs.push('Missing numeric `f1`.')
  return errs
}

const onPickModelFile = (event) => {
  const file = event?.target?.files?.[0]
  modelFile.value = file || null
}

const onPickMetadataFile = async (event) => {
  const file = event?.target?.files?.[0]
  metadataFile.value = file || null
  metadata.value = null
  validationErrors.value = []
  uploadMessage.value = ''

  if (!file) return
  try {
    const parsed = await parseJsonFile(file)
    const errs = validateMetadata(parsed)
    metadata.value = parsed
    validationErrors.value = errs
    uploadMessage.value = errs.length
      ? 'Metadata loaded with validation errors.'
      : 'Model package metadata is valid.'
  } catch {
    validationErrors.value = ['Invalid metadata JSON file.']
    uploadMessage.value = 'Failed to parse metadata.'
  }
}

const drawBoundingBoxes = (results) => {
  const canvas = bboxCanvasEl.value
  const video = videoEl.value
  if (!canvas || !video) return
  const ctx = canvas.getContext('2d')
  canvas.width = video.videoWidth || 640
  canvas.height = video.videoHeight || 480
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  const hands = results?.landmarks || []
  const handedness = results?.handedness || []
  if (!hands.length) {
    prediction.value = null
    return
  }

  hands.forEach((hand, idx) => {
    const xs = hand.map((p) => Number(p.x) * canvas.width)
    const ys = hand.map((p) => Number(p.y) * canvas.height)
    const minX = Math.max(0, Math.min(...xs))
    const minY = Math.max(0, Math.min(...ys))
    const maxX = Math.min(canvas.width, Math.max(...xs))
    const maxY = Math.min(canvas.height, Math.max(...ys))
    const score = Number(handedness?.[idx]?.[0]?.score || 0.5)

    const labels = modelSummary.value?.labels || ['unknown']
    const predictedLabel = hands.length >= 2 ? labels[Math.min(1, labels.length - 1)] : labels[0]
    const confidence = Math.max(0.5, Math.min(0.99, score))

    prediction.value = {
      label: predictedLabel,
      confidence,
      note: 'Preview inference from uploaded metadata labels.'
    }

    ctx.strokeStyle = '#22d3ee'
    ctx.lineWidth = 2
    ctx.strokeRect(minX, minY, Math.max(1, maxX - minX), Math.max(1, maxY - minY))
    ctx.fillStyle = 'rgba(2,6,23,0.8)'
    ctx.fillRect(minX, Math.max(0, minY - 24), 220, 20)
    ctx.fillStyle = '#67e8f9'
    ctx.font = '12px monospace'
    ctx.fillText(`${predictedLabel} ${(confidence * 100).toFixed(1)}%`, minX + 6, Math.max(12, minY - 10))
  })
}

const stopLive = () => {
  stopHandTracking()
  if (mediaStream.value) {
    mediaStream.value.getTracks().forEach((t) => t.stop())
    mediaStream.value = null
  }
  isLive.value = false
  liveStatus.value = 'Camera stopped.'
  const canvas = bboxCanvasEl.value
  if (canvas) {
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, canvas.width, canvas.height)
  }
}

const startLive = async () => {
  liveStatus.value = 'Requesting camera...'
  try {
    stopLive()
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    mediaStream.value = stream
    await startHandTracking(videoEl.value, landmarkCanvasEl.value, stream)
    onFrame((results) => {
      drawBoundingBoxes(results)
    })
    isLive.value = true
    liveStatus.value = 'Live camera running.'
  } catch (e) {
    liveStatus.value = e?.message || 'Failed to start camera.'
    stopLive()
  }
}

onUnmounted(() => {
  stopLive()
})
</script>

<template>
  <div class="max-w-7xl mx-auto space-y-6">
    <section class="mb-2 grid grid-cols-[auto_1fr] md:grid-cols-3 items-center gap-3">
      <div class="flex justify-start">
        <BaseBtn variant="secondary" title="Return to training page" class="px-3" @click="router.push('/training')">
          &larr;
        </BaseBtn>
      </div>
      <div class="text-left md:text-center">
        <h1 class="text-2xl md:text-3xl font-bold text-white mb-2">Realtime AI Playground</h1>
        <p class="text-slate-400">Upload exported model package metadata and test live CV overlays.</p>
      </div>
      <div class="hidden md:block"></div>
    </section>

    <BaseCard>
      <h2 class="text-xl text-white font-semibold">Model Package</h2>
      <p class="text-xs text-slate-400 mt-1">Accepted metadata fields: model_name, model_family, input_spec, labels, export_format, version, precision, recall, f1.</p>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
        <label class="text-sm text-slate-300">
          Exported Model File (optional in this phase)
          <input type="file" class="mt-1 block w-full text-sm text-slate-300" @change="onPickModelFile" />
        </label>
        <label class="text-sm text-slate-300">
          Metadata JSON (required)
          <input type="file" accept=".json,application/json" class="mt-1 block w-full text-sm text-slate-300" @change="onPickMetadataFile" />
        </label>
      </div>

      <p v-if="uploadMessage" class="mt-3 text-sm" :class="validationErrors.length ? 'text-amber-300' : 'text-emerald-300'">{{ uploadMessage }}</p>
      <ul v-if="validationErrors.length" class="mt-2 text-sm text-rose-300 list-disc list-inside">
        <li v-for="err in validationErrors" :key="err">{{ err }}</li>
      </ul>

      <div v-if="modelSummary" class="mt-4 rounded-lg border border-slate-800 bg-slate-950/40 p-3 text-sm">
        <p class="text-slate-100 font-medium">{{ modelSummary.name }} ({{ modelSummary.family }})</p>
        <p class="text-slate-400 mt-1">Format: {{ modelSummary.format }} | Version: {{ modelSummary.version }}</p>
        <p class="text-slate-400 mt-1">Precision: {{ modelSummary.precision }} | Recall: {{ modelSummary.recall }} | F1: {{ modelSummary.f1 }}</p>
        <p class="text-slate-400 mt-1">Labels: {{ modelSummary.labels.join(', ') }}</p>
      </div>
    </BaseCard>

    <BaseCard>
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h2 class="text-xl text-white font-semibold">Live CV Preview</h2>
        <div class="flex gap-2">
          <BaseBtn variant="secondary" :disabled="isLive" @click="startLive">Start CV Live</BaseBtn>
          <BaseBtn variant="secondary" :disabled="!isLive" @click="stopLive">Stop CV Live</BaseBtn>
        </div>
      </div>
      <p class="mt-2 text-sm text-slate-400">{{ liveStatus }}</p>

      <div class="mt-4 relative aspect-video w-full overflow-hidden rounded-xl border border-slate-700 bg-black">
        <video ref="videoEl" autoplay playsinline muted class="absolute inset-0 h-full w-full object-cover"></video>
        <canvas ref="landmarkCanvasEl" class="absolute inset-0 h-full w-full"></canvas>
        <canvas ref="bboxCanvasEl" class="absolute inset-0 h-full w-full"></canvas>
      </div>

      <div class="mt-4 rounded-lg border border-slate-800 bg-slate-950/40 p-3 text-sm">
        <p class="text-slate-400">Prediction</p>
        <p v-if="prediction" class="text-slate-100 mt-1">
          {{ prediction.label }} ({{ (prediction.confidence * 100).toFixed(2) }}%)
        </p>
        <p v-else class="text-slate-500 mt-1">No hand detected.</p>
        <p class="text-xs text-slate-500 mt-2">
          {{ prediction?.note || 'Load metadata and start camera for preview inference.' }}
        </p>
      </div>

      <p class="mt-3 text-xs text-amber-300">
        Note: this phase validates model metadata and CV overlay flow; runtime adapter-specific inference will be integrated in next phase.
      </p>
    </BaseCard>
  </div>
</template>
