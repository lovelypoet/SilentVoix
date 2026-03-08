<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
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
const savedModels = ref([])
const selectedSavedModelId = ref('')
const isSwitchingSavedModel = ref(false)

const mirrorCamera = ref(true)
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
const cvFrameBuffer = ref([])

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
const activeInputSpec = computed(() => {
  const spec = activeModel.value?.metadata?.input_spec
  return spec && typeof spec === 'object' ? spec : {}
})
const cvSequenceLength = computed(() => {
  const raw = Number(activeInputSpec.value?.sequence_length || 1)
  return Number.isFinite(raw) && raw > 1 ? Math.floor(raw) : 1
})
const cvFeatureDim = computed(() => {
  const explicit = Number(activeInputSpec.value?.feature_dim || 0)
  if (Number.isFinite(explicit) && explicit > 0) {
    return Math.floor(explicit)
  }
  if (cvSequenceLength.value > 1 && modelInputDim.value % cvSequenceLength.value === 0) {
    return modelInputDim.value / cvSequenceLength.value
  }
  return modelInputDim.value
})
const cvPreprocessProfile = computed(() => String(activeInputSpec.value?.preprocess_profile || '').trim().toLowerCase())
const cvUsesSequence = computed(() => cvSequenceLength.value > 1)
const cvCanFlattenSequence = computed(() => modelInputDim.value === cvSequenceLength.value * cvFeatureDim.value)
const videoClasses = computed(() => [
  'absolute inset-0 h-full w-full object-cover',
  { '-scale-x-100': mirrorCamera.value }
])
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
    selectedSavedModelId.value = activeModel.value?.id || ''
  } catch {
    activeModel.value = null
    selectedSavedModelId.value = ''
  }
}

const loadSavedModels = async () => {
  try {
    const res = await api.playground.listModels()
    const rows = Array.isArray(res?.models) ? res.models : []
    savedModels.value = rows
  } catch {
    savedModels.value = []
  }
}

const loadModelContext = async () => {
  await Promise.all([loadActiveModel(), loadSavedModels()])
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
    selectedSavedModelId.value = activeModel.value?.id || ''
    uploadMessage.value = res?.message || 'Model uploaded.'
    await loadSavedModels()
  } catch (e) {
    uploadError.value = e?.response?.data?.detail || 'Failed to upload model package.'
  } finally {
    isUploading.value = false
  }
}

const activateSavedModel = async () => {
  uploadError.value = ''
  uploadMessage.value = ''
  if (!selectedSavedModelId.value) {
    uploadError.value = 'Select a saved model first.'
    return
  }
  isSwitchingSavedModel.value = true
  try {
    await api.playground.activateModel(selectedSavedModelId.value)
    await loadModelContext()
    uploadMessage.value = 'Saved model activated.'
  } catch (e) {
    uploadError.value = e?.response?.data?.detail || 'Failed to activate saved model.'
  } finally {
    isSwitchingSavedModel.value = false
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

const buildCvFeatureVector = (results, featureDim) => {
  const dim = Number(featureDim || modelInputDim.value)
  const { left, right, first } = pickHands(results)
  if (dim === 63) {
    return flattenHand63(left || right || first)
  }
  if (dim === 126) {
    return [...flattenHand63(left), ...flattenHand63(right)]
  }
  const base = flattenHand63(left || right || first)
  if (dim < 63) return base.slice(0, dim)
  return [...base, ...Array.from({ length: dim - 63 }, () => 0)]
}

const buildCvPayloadForModel = (results) => {
  const featureDim = cvFeatureDim.value
  const frameVector = buildCvFeatureVector(results, featureDim)
  const maxBuffer = Math.max(cvSequenceLength.value, 120)
  cvFrameBuffer.value = [...cvFrameBuffer.value, frameVector].slice(-maxBuffer)

  if (!cvUsesSequence.value) {
    return { cv_values: frameVector }
  }

  return { sequence: cvFrameBuffer.value }
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
    const xs = hand.map((p) => {
      const x = Number(p.x) * canvas.width
      return mirrorCamera.value ? canvas.width - x : x
    })
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

const useIntegratedMode = ref(false)
const backendLandmarks = ref(null)
const availableDetectors = ref([])
const currentDetector = ref('')
const detectorFile = ref(null)
const isUpdatingDetector = ref(false)

const loadDetectorsList = async () => {
  try {
    const res = await api.playground.listDetectors()
    availableDetectors.value = res.detectors || []
    currentDetector.value = res.current || ''
  } catch (e) {
    console.error('Failed to load detectors:', e)
  }
}

const onPickDetectorFile = (event) => {
  detectorFile.value = event?.target?.files?.[0] || null
}

const uploadNewDetector = async () => {
  if (!detectorFile.value) return
  isUpdatingDetector.value = true
  try {
    await api.playground.setDetector(null, detectorFile.value)
    uploadMessage.value = 'Detector uploaded and activated.'
    detectorFile.value = null
    await loadDetectorsList()
  } catch (e) {
    uploadError.value = e?.response?.data?.detail || 'Failed to upload detector.'
  } finally {
    isUpdatingDetector.value = false
  }
}

const switchDetector = async (name) => {
  if (name === currentDetector.value) return
  isUpdatingDetector.value = true
  try {
    await api.playground.setDetector(name)
    uploadMessage.value = `Switched to ${name}`
    await loadDetectorsList()
  } catch (e) {
    uploadError.value = e?.response?.data?.detail || 'Failed to switch detector.'
  } finally {
    isUpdatingDetector.value = false
  }
}

watch(useIntegratedMode, (val) => {
  if (val) loadDetectorsList()
})

const drawBackendSkeleton = (landmarks) => {
  const canvas = landmarkCanvasEl.value
  const video = videoEl.value
  if (!canvas || !video || !landmarks) return
  const ctx = canvas.getContext('2d')
  canvas.width = video.videoWidth || 640
  canvas.height = video.videoHeight || 480
  
  // Clear previous landmarks if we are the only ones drawing
  if (useIntegratedMode.value) {
    ctx.clearRect(0, 0, canvas.width, canvas.height)
  }

  // Draw points and connections (standard hand skeleton)
  const connections = [
    [0,1],[1,2],[2,3],[3,4], // thumb
    [0,5],[5,6],[6,7],[7,8], // index
    [5,9],[9,10],[10,11],[11,12], // middle
    [9,13],[13,14],[14,15],[15,16], // ring
    [13,17],[17,18],[18,19],[19,20], // pinky
    [0,17] // palm base
  ]

  ctx.strokeStyle = '#facc15' // teal-400
  ctx.fillStyle = '#ffffff'
  ctx.lineWidth = 3

  landmarks.forEach((pt, i) => {
    const x = Number(pt[0]) * canvas.width
    const y = Number(pt[1]) * canvas.height
    const actualX = mirrorCamera.value ? canvas.width - x : x
    
    ctx.beginPath()
    ctx.arc(actualX, y, 4, 0, 2 * Math.PI)
    ctx.fill()
  })

  ctx.beginPath()
  connections.forEach(([i, j]) => {
    const p1 = landmarks[i]
    const p2 = landmarks[j]
    const x1 = Number(p1[0]) * canvas.width
    const y1 = Number(p1[1]) * canvas.height
    const x2 = Number(p2[0]) * canvas.width
    const y2 = Number(p2[1]) * canvas.height
    
    const ax1 = mirrorCamera.value ? canvas.width - x1 : x1
    const ax2 = mirrorCamera.value ? canvas.width - x2 : x2
    
    ctx.moveTo(ax1, y1)
    ctx.lineTo(ax2, y2)
  })
  ctx.stroke()
}

const predictFromIntegratedService = async () => {
  if (isPredictingFrame) return
  if (!videoEl.value || videoEl.value.readyState < 2) return
  
  isPredictingFrame = true
  try {
    // Capture frame from video element
    const canvas = document.createElement('canvas')
    canvas.width = videoEl.value.videoWidth
    canvas.height = videoEl.value.videoHeight
    const ctx = canvas.getContext('2d')
    ctx.drawImage(videoEl.value, 0, 0)
    const base64 = canvas.toDataURL('image/jpeg', 0.7)

    const res = await api.playground.predictIntegrated(base64)
    
    if (res.status === 'success') {
      prediction.value = {
        label: res.gesture,
        confidence: res.confidence,
        note: `Integrated YOLO+LSTM Loop. Buffer: ${res.buffer_status}`
      }
      backendLandmarks.value = res.landmarks
      if (res.landmarks) {
        drawBackendSkeleton(res.landmarks)
      }
    }
  } catch (e) {
    prediction.value = {
      label: 'error',
      confidence: 0,
      note: e?.response?.data?.detail || 'Integrated inference failed.'
    }
  } finally {
    isPredictingFrame = false
  }
}

const predictFromResults = async (results) => {
  if (useIntegratedMode.value) {
    void predictFromIntegratedService()
    return
  }
  if (!activeModel.value) return
  if (isPredictingFrame) return
  const now = Date.now()
  if (now - lastPredictTs < 250) return
  lastPredictTs = now
  isPredictingFrame = true
  try {
    const payload = buildCvPayloadForModel(results)
    payload.model_id = activeModel.value.id
    const res = await api.playground.predictCv(payload)
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
    const res = await api.playground.predictSensor({ sensor_values: normalized, model_id: activeModel.value.id })
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
  cvFrameBuffer.value = []
  lastPredictTs = 0
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
  if (cvUsesSequence.value && !cvCanFlattenSequence.value && modelInputDim.value !== cvFeatureDim.value) {
    liveStatus.value = `Sequence preprocess enabled (${cvSequenceLength.value}x${cvFeatureDim.value}), but model input_dim=${modelInputDim.value}. Using best-effort mapping.`
  }

  liveStatus.value = 'Requesting camera...'
  try {
    stopLive()
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false
    })
    mediaStream.value = stream
    await startHandTracking(videoEl.value, landmarkCanvasEl.value, stream)
    onFrame((results) => {
      if (!useIntegratedMode.value) {
        drawBoundingBoxes(results)
      } else {
        // In integrated mode, we don't draw bounding boxes from mediapipe
        // because we will draw the skeleton from YOLO keypoints
        const canvas = bboxCanvasEl.value
        if (canvas) {
          const ctx = canvas.getContext('2d')
          ctx.clearRect(0, 0, canvas.width, canvas.height)
        }
      }
      
      // If no landmarks from mediapipe but we are in integrated mode, 
      // we still want to trigger the loop (YOLO will find its own hands)
      if (results?.landmarks?.length || useIntegratedMode.value) {
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
  void loadModelContext()
})

watch(() => activeModel.value?.id, () => {
  cvFrameBuffer.value = []
  lastPredictTs = 0
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
        <label class="text-sm text-slate-300 md:col-span-2">
          Reuse Saved Model
          <div class="mt-1 flex flex-col gap-2 md:flex-row">
            <select v-model="selectedSavedModelId" class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white">
              <option value="">Select a saved model...</option>
              <option v-for="model in savedModels" :key="model.id" :value="model.id">
                {{ model.display_name || model.id }} | {{ model.metadata?.model_family || '--' }} | {{ model.metadata?.export_format || '--' }}
              </option>
            </select>
            <BaseBtn variant="secondary" :disabled="isSwitchingSavedModel || !selectedSavedModelId" @click="activateSavedModel">
              {{ isSwitchingSavedModel ? 'Activating...' : 'Use Saved Model' }}
            </BaseBtn>
          </div>
        </label>
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
        <BaseBtn variant="secondary" @click="loadModelContext">Refresh Active Model</BaseBtn>
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
        <div class="flex flex-wrap items-center gap-4">
          <div class="flex items-center gap-2 bg-slate-800/50 p-1 rounded-lg border border-slate-700">
            <button 
              class="px-3 py-1 text-xs rounded transition-colors"
              :class="!useIntegratedMode ? 'bg-teal-500 text-white' : 'text-slate-400 hover:text-slate-200'"
              @click="useIntegratedMode = false"
            >
              MediaPipe (Client)
            </button>
            <button 
              class="px-3 py-1 text-xs rounded transition-colors"
              :class="useIntegratedMode ? 'bg-teal-500 text-white' : 'text-slate-400 hover:text-slate-200'"
              @click="useIntegratedMode = true"
            >
              YOLO+LSTM (Server)
            </button>
          </div>

          <!-- YOLO Detector Management (Integrated Mode Only) -->
          <div v-if="useIntegratedMode" class="flex flex-wrap items-center gap-2 bg-slate-800/30 p-2 rounded-lg border border-slate-700/50">
            <span class="text-xs font-medium text-slate-400">Detector:</span>
            <select 
              :value="currentDetector"
              @change="switchDetector($event.target.value)"
              class="bg-slate-900 text-xs text-white rounded border border-slate-700 px-2 py-1 outline-none"
            >
              <option v-for="d in availableDetectors" :key="d" :value="d">{{ d }}</option>
            </select>
            <div class="h-4 w-px bg-slate-700 mx-1"></div>
            <label class="cursor-pointer bg-slate-700 hover:bg-slate-600 px-2 py-1 rounded text-[10px] text-white transition-colors">
              Upload .pt
              <input type="file" accept=".pt" class="hidden" @change="onPickDetectorFile" />
            </label>
            <span v-if="detectorFile" class="text-[10px] text-teal-400 truncate max-w-[100px]">{{ detectorFile.name }}</span>
            <button 
              v-if="detectorFile"
              @click="uploadNewDetector"
              :disabled="isUpdatingDetector"
              class="bg-teal-600 hover:bg-teal-500 disabled:opacity-50 px-2 py-1 rounded text-[10px] text-white"
            >
              {{ isUpdatingDetector ? '...' : 'Save' }}
            </button>
          </div>

          <div class="flex gap-2">
            <BaseBtn variant="secondary" :disabled="isLive" @click="startLive">
              {{ modelModality === 'sensor' ? 'Start Sensor Live' : 'Start CV Live' }}
            </BaseBtn>
            <BaseBtn variant="secondary" :disabled="!isLive" @click="stopLive">
              {{ modelModality === 'sensor' ? 'Stop Sensor Live' : 'Stop CV Live' }}
            </BaseBtn>
          </div>
        </div>
      </div>
      <p class="mt-2 text-sm text-slate-400">{{ liveStatus }}</p>

      <div class="mt-4 relative aspect-video w-full overflow-hidden rounded-xl border border-slate-700 bg-black">
        <video v-show="modelModality !== 'sensor'" ref="videoEl" autoplay playsinline muted :class="videoClasses"></video>
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
