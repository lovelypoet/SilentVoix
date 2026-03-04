<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import { useHandTracking } from '../composables/useHandTracking.js'
import api from '../services/api'

const router = useRouter()

const modelFile = ref(null)
const metadataFile = ref(null)
const modelClassFile = ref(null)
const isStateDict = ref(false)
const metadata = ref(null)
const validationErrors = ref([])
const uploadMessage = ref('')
const uploadError = ref('')
const isUploading = ref(false)
const activeModel = ref(null)

const mirrorCamera = ref(false)
const showLandmarks = ref(true)
const videoEl = ref(null)
const landmarkCanvasEl = ref(null)
const bboxCanvasEl = ref(null)
const mediaStream = ref(null)
const isLive = ref(false)
const liveStatus = ref('Camera idle.')
const prediction = ref(null)
const sensorSnapshot = ref({
  values: [],
  realSensor: false,
  updatedAt: null
})
let lastPredictTs = 0
let isPredictingFrame = false
let sensorPollTimer = null

const { startHandTracking, stopHandTracking, onFrame } = useHandTracking(mirrorCamera, showLandmarks)

const modelSummary = computed(() => {
  const source = activeModel.value?.metadata || metadata.value
  if (!source) return null
  const m = source
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

const modelInputDim = computed(() => Number(activeModel.value?.input_dim || 63))
const modelModality = computed(() => {
  const raw = String(activeModel.value?.metadata?.modality || '').trim().toLowerCase()
  if (raw === 'cv' || raw === 'sensor') return raw
  const dim = modelInputDim.value
  if (dim === 11 || dim === 22) return 'sensor'
  return 'cv'
})

const activeRuntimeState = computed(() => {
  const state = String(activeModel.value?.runtime_status?.state || '').trim().toLowerCase()
  if (state === 'pass' || state === 'fail') return state
  return 'untested'
})

const sensorUpdatedAtText = computed(() => {
  const ts = sensorSnapshot.value?.updatedAt
  if (!ts) return '--'
  const d = new Date(ts)
  return Number.isNaN(d.getTime()) ? '--' : d.toLocaleTimeString()
})

const sensorDisplayRows = computed(() => {
  const values = Array.isArray(sensorSnapshot.value?.values) ? sensorSnapshot.value.values : []
  const rows = []

  if (modelInputDim.value === 11) {
    const labels = ['F1', 'F2', 'F3', 'F4', 'F5', 'AX', 'AY', 'AZ', 'GX', 'GY', 'GZ']
    labels.forEach((label, i) => {
      rows.push({ label, value: Number(values[i] ?? 0) })
    })
    return rows
  }

  if (modelInputDim.value === 22) {
    const labels = [
      'L-F1', 'L-F2', 'L-F3', 'L-F4', 'L-F5', 'L-AX', 'L-AY', 'L-AZ', 'L-GX', 'L-GY', 'L-GZ',
      'R-F1', 'R-F2', 'R-F3', 'R-F4', 'R-F5', 'R-AX', 'R-AY', 'R-AZ', 'R-GX', 'R-GY', 'R-GZ'
    ]
    labels.forEach((label, i) => {
      rows.push({ label, value: Number(values[i] ?? 0) })
    })
    return rows
  }

  for (let i = 0; i < values.length; i += 1) {
    rows.push({ label: `V${i + 1}`, value: Number(values[i] ?? 0) })
  }
  return rows
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

const onPickModelClassFile = (event) => {
  const file = event?.target?.files?.[0]
  modelClassFile.value = file || null
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

const loadActiveModel = async () => {
  try {
    const res = await api.playground.getActiveModel()
    activeModel.value = res?.model || null
  } catch {
    activeModel.value = null
  }
}

const uploadAndActivateModel = async () => {
  uploadError.value = ''
  uploadMessage.value = ''
  if (!modelFile.value) {
    uploadError.value = 'Select an exported model file first.'
    return
  }
  if (!metadataFile.value) {
    uploadError.value = 'Select a metadata JSON file first.'
    return
  }
  if (validationErrors.value.length) {
    uploadError.value = 'Fix metadata validation errors before upload.'
    return
  }
  if (isStateDict.value && !modelClassFile.value) {
    uploadError.value = 'Model class file (.py) is required for state_dict models.'
    return
  }
  isUploading.value = true
  try {
    const res = await api.playground.uploadModel(modelFile.value, metadataFile.value, modelClassFile.value, isStateDict.value)
    activeModel.value = res?.model || null
    uploadMessage.value = res?.message || 'Model uploaded.'
  } catch (e) {
    uploadError.value = e?.response?.data?.detail || 'Failed to upload model package.'
  } finally {
    isUploading.value = false
  }
}

const pickHands = (results) => {
  const hands = results?.landmarks || []
  const handedness = results?.handedness || []
  let left = null
  let right = null
  let first = null
  hands.forEach((hand, i) => {
    if (!first) first = hand
    const label = handedness?.[i]?.[0]?.categoryName
    if (label === 'Left' && !left) left = hand
    if (label === 'Right' && !right) right = hand
  })
  if (!left && first) left = first
  if (!right && hands.length > 1) right = hands[hands.length - 1]
  return { left, right, first }
}

const flattenHand63 = (hand) => {
  if (!Array.isArray(hand) || hand.length !== 21) {
    return Array.from({ length: 63 }, () => 0)
  }
  const values = []
  for (let i = 0; i < 21; i++) {
    values.push(Number(hand[i]?.x ?? 0), Number(hand[i]?.y ?? 0), Number(hand[i]?.z ?? 0))
  }
  return values
}

const buildCvVectorForModel = (results) => {
  const dim = modelInputDim.value
  const { left, right, first } = pickHands(results)
  if (dim === 63) {
    return flattenHand63(first || left || right)
  }
  if (dim === 126) {
    return [...flattenHand63(left), ...flattenHand63(right)]
  }
  const base = flattenHand63(first || left || right)
  if (dim < 63) return base.slice(0, dim)
  return [...base, ...Array.from({ length: dim - 63 }, () => 0)]
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
  if (!hands.length) {
    prediction.value = null
    return
  }

  hands.forEach((hand) => {
    const xs = hand.map((p) => Number(p.x) * canvas.width)
    const ys = hand.map((p) => Number(p.y) * canvas.height)
    const minX = Math.max(0, Math.min(...xs))
    const minY = Math.max(0, Math.min(...ys))
    const maxX = Math.min(canvas.width, Math.max(...xs))
    const maxY = Math.min(canvas.height, Math.max(...ys))

    ctx.strokeStyle = '#22d3ee'
    ctx.lineWidth = 2
    ctx.strokeRect(minX, minY, Math.max(1, maxX - minX), Math.max(1, maxY - minY))
    const overlayText = prediction.value?.label
      ? `${prediction.value.label} ${(Number(prediction.value.confidence || 0) * 100).toFixed(1)}%`
      : 'Detecting...'
    ctx.fillStyle = 'rgba(2,6,23,0.8)'
    ctx.fillRect(minX, Math.max(0, minY - 24), 220, 20)
    ctx.fillStyle = '#67e8f9'
    ctx.font = '12px monospace'
    ctx.fillText(overlayText, minX + 6, Math.max(12, minY - 10))
  })
}

const predictFromResults = async (results) => {
  if (!activeModel.value) return
  if (isPredictingFrame) return
  const now = Date.now()
  if (now - lastPredictTs < 250) return
  lastPredictTs = now
  isPredictingFrame = true
  try {
    const cvValues = buildCvVectorForModel(results)
    const res = await api.playground.predictCv(cvValues, activeModel.value.id)
    const pred = res?.prediction
    if (pred) {
      prediction.value = {
        label: pred.label,
        confidence: pred.confidence,
        top3: pred.top3 || [],
        note: `Real model inference (${res?.model_name || activeModel.value.display_name}).`
      }
    }
  } catch (e) {
    prediction.value = {
      label: 'error',
      confidence: 0,
      note: e?.response?.data?.detail || 'Inference failed.'
    }
  } finally {
    isPredictingFrame = false
  }
}

const normalizeSensorVectorForModel = (values) => {
  const dim = modelInputDim.value
  const vector = Array.isArray(values) ? values.map((v) => Number(v ?? 0)) : []
  if (vector.length === dim) return vector
  return null
}

const predictFromLatestSensor = async () => {
  if (!activeModel.value || modelModality.value !== 'sensor') return
  if (isPredictingFrame) return
  const now = Date.now()
  if (now - lastPredictTs < 250) return
  lastPredictTs = now
  isPredictingFrame = true
  try {
    const latest = await api.utils.latestSensorFrame()
    sensorSnapshot.value = {
      values: Array.isArray(latest?.values) ? latest.values : [],
      realSensor: Boolean(latest?.real_sensor),
      updatedAt: Date.now()
    }
    const normalized = normalizeSensorVectorForModel(latest?.values || [])
    if (!normalized) {
      prediction.value = {
        label: 'error',
        confidence: 0,
        note: `Sensor vector mismatch: expected ${modelInputDim.value}, got ${(latest?.values || []).length || 0}.`
      }
      return
    }
    const res = await api.playground.predictSensor(normalized, activeModel.value.id)
    const pred = res?.prediction
    if (pred) {
      prediction.value = {
        label: pred.label,
        confidence: pred.confidence,
        top3: pred.top3 || [],
        note: `Realtime sensor inference (${res?.model_name || activeModel.value.display_name}).`
      }
      liveStatus.value = latest?.real_sensor ? 'Live sensor stream running.' : 'Using last available sensor snapshot.'
    }
  } catch (e) {
    prediction.value = {
      label: 'error',
      confidence: 0,
      note: e?.response?.data?.detail || 'Sensor inference failed.'
    }
  } finally {
    isPredictingFrame = false
  }
}

const stopLive = () => {
  if (sensorPollTimer) {
    clearInterval(sensorPollTimer)
    sensorPollTimer = null
  }
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
  if (!activeModel.value) {
    liveStatus.value = 'Upload and activate a model first.'
    return
  }
  if (activeRuntimeState.value === 'fail') {
    liveStatus.value = 'Active model runtime-check is failing. Fix model package or run Runtime Check in Model Library.'
    return
  }
  if (modelModality.value === 'sensor') {
    stopLive()
    isLive.value = true
    liveStatus.value = 'Starting realtime sensor polling...'
    sensorPollTimer = setInterval(() => {
      void predictFromLatestSensor()
    }, 250)
    void predictFromLatestSensor()
    return
  }

  liveStatus.value = 'Requesting camera...'
  try {
    stopLive()
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    mediaStream.value = stream
    await startHandTracking(videoEl.value, landmarkCanvasEl.value, stream)
    onFrame((results) => {
      drawBoundingBoxes(results)
      if (results?.landmarks?.length) {
        void predictFromResults(results)
      }
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

onMounted(() => {
  void loadActiveModel()
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
        <p class="text-slate-400">Upload exported model package metadata and test live CV or sensor inference.</p>
      </div>
      <div class="hidden md:block"></div>
    </section>

    <BaseCard>
      <h2 class="text-xl text-white font-semibold">Model Package</h2>
      <p class="text-xs text-slate-400 mt-1">Accepted metadata fields: model_name, model_family, input_spec, labels, export_format, version, precision, recall, f1.</p>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
        <label class="text-sm text-slate-300">
          Exported Model File (required)
          <input type="file" class="mt-1 block w-full text-sm text-slate-300" @change="onPickModelFile" />
        </label>
        <label class="text-sm text-slate-300">
          Metadata JSON (required)
          <input type="file" accept=".json,application/json" class="mt-1 block w-full text-sm text-slate-300" @change="onPickMetadataFile" />
        </label>
        <div class="md:col-span-2 pt-2 border-t border-slate-800 flex flex-col gap-3">
          <label class="text-sm text-slate-300 flex items-center gap-2">
            <input type="checkbox" v-model="isStateDict" class="rounded border-slate-700 bg-slate-800 text-teal-400 focus:ring-teal-500" />
            This PyTorch model is a state_dict
          </label>
          <div v-if="isStateDict" class="transition-all bg-slate-900/50 p-3 rounded border border-slate-800">
            <label class="text-sm text-slate-300">
              Model Class Definition (.py file)
              <span class="block text-xs text-slate-500 mt-1 mb-2">Required for backend runtime to instantiate the model before loading weights.</span>
              <input type="file" accept=".py" class="mt-1 block w-full text-sm text-slate-300" @change="onPickModelClassFile" />
            </label>
          </div>
        </div>
      </div>

      <p v-if="uploadMessage" class="mt-3 text-sm" :class="validationErrors.length ? 'text-amber-300' : 'text-emerald-300'">{{ uploadMessage }}</p>
      <p v-if="uploadError" class="mt-2 text-sm text-rose-300">{{ uploadError }}</p>
      <ul v-if="validationErrors.length" class="mt-2 text-sm text-rose-300 list-disc list-inside">
        <li v-for="err in validationErrors" :key="err">{{ err }}</li>
      </ul>

      <div class="mt-3 flex gap-2">
        <BaseBtn variant="primary" :disabled="isUploading" @click="uploadAndActivateModel">
          {{ isUploading ? 'Uploading...' : 'Upload & Activate' }}
        </BaseBtn>
        <BaseBtn variant="secondary" @click="loadActiveModel">Refresh Active Model</BaseBtn>
      </div>

      <div v-if="modelSummary" class="mt-4 rounded-lg border border-slate-800 bg-slate-950/40 p-3 text-sm">
        <p class="text-slate-100 font-medium">{{ modelSummary.name }} ({{ modelSummary.family }})</p>
        <p class="text-slate-400 mt-1">Format: {{ modelSummary.format }} | Version: {{ modelSummary.version }}</p>
        <p class="text-slate-400 mt-1">Precision: {{ modelSummary.precision }} | Recall: {{ modelSummary.recall }} | F1: {{ modelSummary.f1 }}</p>
        <p class="text-slate-400 mt-1">Labels: {{ modelSummary.labels.join(', ') }}</p>
        <p class="mt-2 text-xs" :class="activeRuntimeState === 'pass' ? 'text-emerald-300' : activeRuntimeState === 'fail' ? 'text-amber-300' : 'text-slate-400'">
          Runtime status: {{ activeRuntimeState }}
        </p>
      </div>
    </BaseCard>

    <BaseCard>
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h2 class="text-xl text-white font-semibold">Live Preview</h2>
        <div class="flex gap-2">
          <BaseBtn variant="secondary" :disabled="isLive" @click="startLive">
            {{ modelModality === 'sensor' ? 'Start Sensor Live' : 'Start CV Live' }}
          </BaseBtn>
          <BaseBtn variant="secondary" :disabled="!isLive" @click="stopLive">
            {{ modelModality === 'sensor' ? 'Stop Sensor Live' : 'Stop CV Live' }}
          </BaseBtn>
        </div>
      </div>
      <p class="mt-2 text-sm text-slate-400">{{ liveStatus }}</p>

      <div class="mt-4 relative aspect-video w-full overflow-hidden rounded-xl border border-slate-700 bg-black">
        <video v-show="modelModality !== 'sensor'" ref="videoEl" autoplay playsinline muted class="absolute inset-0 h-full w-full object-cover"></video>
        <canvas v-show="modelModality !== 'sensor'" ref="landmarkCanvasEl" class="absolute inset-0 h-full w-full"></canvas>
        <canvas v-show="modelModality !== 'sensor'" ref="bboxCanvasEl" class="absolute inset-0 h-full w-full"></canvas>
        <div v-if="modelModality === 'sensor'" class="absolute inset-0 overflow-auto bg-slate-950/70 p-4">
          <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
            <p class="text-sm text-slate-200 font-medium">Realtime Sensor Telemetry</p>
            <div class="text-xs text-slate-400">
              <span class="mr-3">Source: {{ sensorSnapshot.realSensor ? 'real sensor' : 'snapshot/fallback' }}</span>
              <span>Updated: {{ sensorUpdatedAtText }}</span>
            </div>
          </div>
          <div class="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-6 gap-2">
            <div
              v-for="item in sensorDisplayRows"
              :key="item.label"
              class="rounded border border-slate-800 bg-slate-900/70 px-2 py-2"
            >
              <p class="text-[11px] text-slate-400">{{ item.label }}</p>
              <p class="text-sm text-slate-100 font-semibold">{{ Number(item.value).toFixed(3) }}</p>
            </div>
          </div>
        </div>
      </div>

      <div class="mt-4 rounded-lg border border-slate-800 bg-slate-950/40 p-3 text-sm">
        <p class="text-slate-400">Prediction</p>
        <p v-if="prediction" class="text-slate-100 mt-1">
          {{ prediction.label }} ({{ (prediction.confidence * 100).toFixed(2) }}%)
        </p>
        <p v-else class="text-slate-500 mt-1">No hand detected.</p>
        <p class="text-xs text-slate-500 mt-2">
          {{ prediction?.note || (activeModel ? 'Start real inference.' : 'Upload & activate a model first.') }}
        </p>
        <p v-if="prediction?.top3?.length" class="text-xs text-slate-400 mt-2">
          Top-3: {{ prediction.top3.map((x) => `${x.label} ${(x.confidence * 100).toFixed(1)}%`).join(' | ') }}
        </p>
      </div>

      <p class="mt-3 text-xs text-slate-500 flex justify-end">
        Supported inference adapters in this phase: exported `.tflite`, `.keras`, `.h5`, `.pth`, `.pt` with valid metadata contract.
      </p>
    </BaseCard>
  </div>
</template>
