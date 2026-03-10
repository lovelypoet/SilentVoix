<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import { useHandTracking } from '../composables/useHandTracking.js'
import api from '../services/api'
import { useToast } from 'primevue/usetoast'
import Dialog from 'primevue/dialog'

const toast = useToast()

const router = useRouter()

const uploadError = ref('')
const activeModel = ref(null)
const savedModels = ref([])
const selectedSavedModelId = ref('')
const isSwitchingSavedModel = ref(false)

// --- Dual-Model Late Fusion State ---
const isFusionMode = ref(false)
const selectedCvModelId = ref('')
const selectedSensorModelId = ref('')
const activeCvModel = ref(null)
const activeSensorModel = ref(null)
const gloveWeight = ref(0.8)
const fusionPrediction = ref(null)
const cvPrediction = ref(null)
const sensorPrediction = ref(null)
const isFusionPredicting = ref(false)

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
let integratedPredictTimer = null

const useIntegratedMode = ref(false)
const styleSettings = ref({
  landmarkColor: '#22d3ee',
  pointColor: '#ffffff',
  lineWidth: 3,
  pointRadius: 4
})

const { startHandTracking, stopHandTracking, onFrame } = useHandTracking(mirrorCamera, showLandmarks, styleSettings)

const modelSummary = computed(() => {
  const source = activeModel.value?.metadata
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

const loadActiveModel = async () => {
  try {
    const res = await api.modelLibrary.getActiveModel()
    activeModel.value = res?.model || null
    selectedSavedModelId.value = activeModel.value?.id || ''
  } catch {
    activeModel.value = null
    selectedSavedModelId.value = ''
  }
}

const backendLandmarks = ref(null)
const activeDetectorId = ref('')
const isUpdatingDetector = ref(false)

// Performance Feedback State
const feedbackSent = ref(false)
const showCorrectionDialog = ref(false)
const correctedLabel = ref('')
const isSubmittingFeedback = ref(false)

const loadSavedModels = async () => {
  try {
    const res = await api.modelLibrary.listModels()
    const rows = Array.isArray(res?.models) ? res.models : []
    savedModels.value = rows
  } catch {
    savedModels.value = []
  }
}

const loadModelContext = async () => {
  await Promise.all([loadActiveModel(), loadSavedModels()])
}

const activateSavedModel = async () => {
  uploadError.value = ''
  
  if (!selectedSavedModelId.value) {
    uploadError.value = 'Select a saved model first.'
    return
  }
  isSwitchingSavedModel.value = true
  try {
    await api.modelLibrary.activateModel(selectedSavedModelId.value)
    await loadModelContext()
    
  } catch (e) {
    uploadError.value = e?.response?.data?.detail || 'Failed to activate saved model.'
  } finally {
    isSwitchingSavedModel.value = false
  }
}

const activateFusionModels = () => {
  uploadError.value = ''
  if (!selectedCvModelId.value || !selectedSensorModelId.value) {
    uploadError.value = 'Select both CV and Sensor models for Late Fusion.'
    return
  }
  
  activeCvModel.value = savedModels.value.find(m => m.id === selectedCvModelId.value) || null
  activeSensorModel.value = savedModels.value.find(m => m.id === selectedSensorModelId.value) || null
  
  if (activeCvModel.value && activeSensorModel.value) {
    toast.add({ severity: 'success', summary: 'Fusion Activated', detail: 'Ready for Dual-Model Late Fusion.', life: 3000 })
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

const availableDetectors = computed(() => {
  return savedModels.value.filter(m => m.metadata?.export_format === 'yolo')
})

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

    ctx.strokeStyle = styleSettings.value.landmarkColor
    ctx.lineWidth = 2
    ctx.strokeRect(minX, minY, Math.max(1, maxX - minX), Math.max(1, maxY - minY))
    const overlayText = prediction.value?.label
      ? `${prediction.value.label} ${(Number(prediction.value.confidence || 0) * 100).toFixed(1)}%`
      : 'Detecting...'
    ctx.fillStyle = 'rgba(2,6,23,0.8)'
    ctx.fillRect(minX, Math.max(0, minY - 24), 220, 20)
    ctx.fillStyle = styleSettings.value.pointColor
    ctx.font = '12px monospace'
    ctx.fillText(overlayText, minX + 6, Math.max(12, minY - 10))
  })
}

const loadActiveDetector = async () => {
  try {
    const res = await api.modelLibrary.getIntegratedDetector()
    activeDetectorId.value = res.model_id || ''
  } catch (e) {
    console.error('Failed to load active detector:', e)
  }
}

const switchDetector = async (modelId) => {
  if (modelId === activeDetectorId.value) return
  isUpdatingDetector.value = true
  try {
    await api.modelLibrary.setIntegratedDetector(modelId)
    activeDetectorId.value = modelId
  } catch (e) {
    uploadError.value = e?.response?.data?.detail || 'Failed to switch detector.'
  } finally {
    isUpdatingDetector.value = false
  }
}

watch(useIntegratedMode, (val) => {
  if (val) {
    loadActiveDetector()
  }
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

  ctx.strokeStyle = styleSettings.value.landmarkColor
  ctx.fillStyle = styleSettings.value.pointColor
  ctx.lineWidth = styleSettings.value.lineWidth

  landmarks.forEach((pt, i) => {
    const x = Number(pt[0]) * canvas.width
    const y = Number(pt[1]) * canvas.height
    const actualX = mirrorCamera.value ? canvas.width - x : x
    
    ctx.beginPath()
    ctx.arc(actualX, y, styleSettings.value.pointRadius, 0, 2 * Math.PI)
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

    const res = await api.modelLibrary.predictIntegrated(base64)
    
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

const startIntegratedLoop = () => {
  if (integratedPredictTimer !== null) return
  integratedPredictTimer = window.setInterval(() => {
    if (!useIntegratedMode.value || !isLive.value) return
    void predictFromIntegratedService()
  }, 250)
}

const stopIntegratedLoop = () => {
  if (integratedPredictTimer !== null) {
    clearInterval(integratedPredictTimer)
    integratedPredictTimer = null
  }
}

const submitFeedback = async (correct, trueLabel = null) => {
  if (!prediction.value || !activeModel.value || feedbackSent.value) return
  
  isSubmittingFeedback.value = true
  try {
    const payload = {
      model_id: activeModel.value.id,
      predicted_label: prediction.value.label,
      true_label: trueLabel || (correct ? prediction.value.label : 'unknown'),
      confidence: prediction.value.confidence,
    }
    await api.modelFeedback.submit(payload)
    feedbackSent.value = true
    toast.add({ severity: 'success', summary: 'Feedback Recorded', detail: 'Thank you for helping improve the model!', life: 3000 })
    showCorrectionDialog.value = false
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Feedback Failed', detail: 'Could not record feedback.' })
  } finally {
    isSubmittingFeedback.value = false
  }
}

const openCorrectionDialog = () => {
  correctedLabel.value = ''
  showCorrectionDialog.value = true
}

const predictFromResults = async (results) => {
  if (useIntegratedMode.value) {
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
    const res = await api.modelLibrary.predictCv(payload)
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
  if (isFusionMode.value) return // Handled by predictFusion
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
    const res = await api.modelLibrary.predictSensor({ sensor_values: normalized, model_id: activeModel.value.id })
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

const predictFusion = async (cvResults) => {
  if (!activeCvModel.value || !activeSensorModel.value || isFusionPredicting.value) return
  
  const now = Date.now()
  if (now - lastPredictTs < 300) return
  lastPredictTs = now
  isFusionPredicting.value = true

  try {
    // 1. Prepare Data
    const cvPayload = buildCvPayloadForModel(cvResults)
    const sensorRaw = await api.utils.latestSensorFrame()
    sensorSnapshot.value = {
      values: Array.isArray(sensorRaw?.values) ? sensorRaw.values : [],
      realSensor: Boolean(sensorRaw?.real_sensor),
      updatedAt: Date.now()
    }
    
    // 2. Parallel Inference
    const [cvRes, sensorRes] = await Promise.all([
       api.modelLibrary.predictCv({ ...cvPayload, model_id: activeCvModel.value.id }),
       api.modelLibrary.predictSensor({ sensor_values: sensorSnapshot.value.values, model_id: activeSensorModel.value.id })
    ])

    const cvProbs = cvRes?.prediction?.probabilities || {}
    const sensorProbs = sensorRes?.prediction?.probabilities || {}
    
    cvPrediction.value = cvRes.prediction
    sensorPrediction.value = sensorRes.prediction

    // 3. Merge Logic (Weighted Average)
    const labels = Array.from(new Set([...Object.keys(cvProbs), ...Object.keys(sensorProbs)]))
    const fusedProbs = {}
    
    labels.forEach(label => {
       const vProb = Number(cvProbs[label] || 0)
       const sProb = Number(sensorProbs[label] || 0)
       fusedProbs[label] = (vProb * (1 - gloveWeight.value)) + (sProb * gloveWeight.value)
    })

    // 4. Find Winner
    const sorted = Object.entries(fusedProbs).sort((a, b) => b[1] - a[1])
    const winner = sorted[0]

    prediction.value = {
       label: winner ? winner[0] : 'Unknown',
       confidence: winner ? winner[1] : 0,
       note: `Fusion: ${activeCvModel.value.display_name} + ${activeSensorModel.value.display_name}`,
       top3: sorted.slice(0, 3).map(([label, conf]) => ({ label, confidence: conf }))
    }

  } catch (e) {
    prediction.value = { label: 'error', confidence: 0, note: 'Fusion failed: ' + (e.message || 'Check logs') }
  } finally {
    isFusionPredicting.value = false
  }
}

const stopLive = () => {
  if (sensorPollTimer) {
    clearInterval(sensorPollTimer)
    sensorPollTimer = null
  }
  stopIntegratedLoop()
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
  if (isFusionMode.value) {
    if (!activeCvModel.value || !activeSensorModel.value) {
       liveStatus.value = 'Activate a fusion pair first.'
       return
    }
    // Fusion mode always starts camera and lets predictFusion handle sensor polling
    liveStatus.value = 'Starting Fusion Streams (CV + Sensor)...'
  } else {
    if (!activeModel.value) {
      liveStatus.value = 'Upload and activate a model first.'
      return
    }
    if (activeRuntimeState.value === 'fail') {
      liveStatus.value = 'Active model runtime-check is failing. Fix model package or run Runtime Check in Model Library.'
      return
    }
  }

  if (modelModality.value === 'sensor' && !isFusionMode.value) {
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
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false
    })
    mediaStream.value = stream
    await startHandTracking(videoEl.value, landmarkCanvasEl.value, stream)
    onFrame((results) => {
      if (isFusionMode.value) {
         void predictFusion(results)
      } else {
        if (!useIntegratedMode.value) {
          drawBoundingBoxes(results)
        }
        if (results?.landmarks?.length || useIntegratedMode.value) {
          void predictFromResults(results)
        }
      }
    })
    isLive.value = true
    liveStatus.value = isFusionMode.value ? 'Fusion Mode Active.' : 'Live camera running.'
    if (useIntegratedMode.value) {
      startIntegratedLoop()
    }
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
  feedbackSent.value = false
})

watch(() => prediction.value?.label, (newLabel, oldLabel) => {
  if (newLabel !== oldLabel) {
    feedbackSent.value = false
  }
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
      <div class="hidden md:flex justify-end">
      </div>
    </section>

    <BaseCard>
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-xl text-white font-semibold">Active Model</h2>
          <p class="text-xs text-slate-400 mt-1">Select a model from your library to use in the playground. Manage your models in the <router-link to="/model-library" class="text-teal-400 hover:underline">Model Library</router-link>.</p>
        </div>
        <div class="flex items-center gap-2">
           <span class="text-xs font-bold uppercase tracking-widest text-slate-500">Late Fusion Mode:</span>
           <button 
             class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none"
             :class="isFusionMode ? 'bg-teal-500' : 'bg-slate-700'"
             @click="isFusionMode = !isFusionMode; stopLive()"
           >
             <span class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform" :class="isFusionMode ? 'translate-x-6' : 'translate-x-1'"></span>
           </button>
        </div>
      </div>
      
      <!-- Standard Mode Model Selection -->
      <div v-if="!isFusionMode" class="mt-4">
        <label class="text-sm text-slate-300">
          Switch Classifier
          <div class="mt-1 flex flex-col gap-2 md:flex-row">
            <select v-model="selectedSavedModelId" class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white">
              <option value="">Select a classifier...</option>
              <option v-for="model in savedModels.filter(m => m.metadata?.model_family !== 'yolo-pose')" :key="model.id" :value="model.id">
                {{ model.display_name || model.id }} | {{ model.metadata?.export_format || '--' }}
              </option>
            </select>
            <BaseBtn variant="secondary" :disabled="isSwitchingSavedModel || !selectedSavedModelId" @click="activateSavedModel">
              {{ isSwitchingSavedModel ? 'Activating...' : 'Activate' }}
            </BaseBtn>
          </div>
        </label>
      </div>

      <!-- Fusion Mode Model Selection -->
      <div v-else class="mt-4 space-y-4">
         <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="space-y-1">
               <label class="text-xs font-bold text-slate-500 uppercase">Vision (CV) Model</label>
               <select v-model="selectedCvModelId" class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white text-sm">
                 <option value="">Select CV model...</option>
                 <option v-for="model in savedModels.filter(m => m.metadata?.modality === 'cv')" :key="model.id" :value="model.id">
                   {{ model.display_name || model.id }}
                 </option>
               </select>
            </div>
            <div class="space-y-1">
               <label class="text-xs font-bold text-slate-500 uppercase">Glove (Sensor) Model</label>
               <select v-model="selectedSensorModelId" class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white text-sm">
                 <option value="">Select Sensor model...</option>
                 <option v-for="model in savedModels.filter(m => m.metadata?.modality === 'sensor')" :key="model.id" :value="model.id">
                   {{ model.display_name || model.id }}
                 </option>
               </select>
            </div>
         </div>

         <!-- Fusion Slider -->
         <div class="p-3 bg-slate-900 rounded-lg border border-slate-800">
            <div class="flex items-center justify-between mb-2">
               <span class="text-xs font-bold text-slate-500 uppercase">Glove vs. Vision Weight (Slider)</span>
               <div class="flex gap-4">
                  <span class="text-[10px] text-teal-400 font-bold uppercase tracking-widest">Vision: {{ (1 - gloveWeight).toFixed(2) }}</span>
                  <span class="text-[10px] text-amber-400 font-bold uppercase tracking-widest">Glove: {{ gloveWeight.toFixed(2) }}</span>
               </div>
            </div>
            <input type="range" v-model.number="gloveWeight" min="0" max="1" step="0.05" class="w-full accent-teal-500 bg-slate-800 h-2 rounded-lg cursor-pointer" />
         </div>

         <div class="flex justify-end">
            <BaseBtn variant="primary" :disabled="!selectedCvModelId || !selectedSensorModelId" @click="activateFusionModels">
               Activate Fusion Pair
            </BaseBtn>
         </div>
      </div>

      <div v-if="uploadError" class="mt-4 p-3 rounded bg-rose-400/10 text-rose-300 border border-rose-400/20 text-sm italic">
        {{ uploadError }}
      </div>

      <div v-if="modelSummary && !isFusionMode" class="mt-6 rounded-lg border border-slate-800 bg-slate-950/40 p-4 shadow-inner">
        <div class="flex items-start justify-between">
          <div>
            <h3 class="text-slate-100 font-bold text-lg">{{ modelSummary.name }}</h3>
            <p class="text-teal-400 text-xs font-medium uppercase tracking-wider mt-0.5">{{ modelSummary.family }}</p>
          </div>
          <span 
            class="px-2 py-1 rounded text-[10px] font-bold uppercase tracking-tighter"
            :class="activeRuntimeState === 'pass' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'"
          >
            Runtime: {{ activeRuntimeState }}
          </span>
        </div>
        
        <div class="grid grid-cols-2 gap-4 mt-4 text-xs">
          <div class="space-y-1">
            <p class="text-slate-500">Format: <span class="text-slate-300">{{ modelSummary.format }}</span></p>
            <p class="text-slate-500">Version: <span class="text-slate-300">{{ modelSummary.version }}</span></p>
          </div>
          <div class="space-y-1">
            <p class="text-slate-500">P/R/F1: <span class="text-slate-300">{{ modelSummary.precision }}/{{ modelSummary.recall }}/{{ modelSummary.f1 }}</span></p>
            <p class="text-slate-500 truncate">Labels: <span class="text-slate-300">{{ modelSummary.labels.join(', ') }}</span></p>
          </div>
        </div>
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
          <div v-if="useIntegratedMode" class="flex items-center gap-2 bg-slate-800/30 p-2 rounded-lg border border-slate-700/50">
            <span class="text-xs font-medium text-slate-400">Detector:</span>
            <select 
              :value="activeDetectorId"
              @change="switchDetector($event.target.value)"
              :disabled="isUpdatingDetector"
              class="bg-slate-900 text-xs text-white rounded border border-slate-700 px-2 py-1 outline-none min-w-[150px]"
            >
              <option value="">-- Select Detector --</option>
              <option v-for="d in availableDetectors" :key="d.id" :value="d.id">
                {{ d.display_name }} ({{ d.metadata.version }})
              </option>
            </select>
            <span v-if="isUpdatingDetector" class="text-[10px] text-teal-400 animate-pulse">Switching...</span>
            <span v-else-if="!activeDetectorId && availableDetectors.length === 0" class="text-[10px] text-amber-400/80">
              No YOLO models in library.
            </span>
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

      <!-- Customization Settings -->
      <div class="mt-4 p-4 rounded-xl border border-slate-700 bg-slate-900/30">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-sm font-medium text-slate-200 flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            Visual Customization
          </h3>
          <button 
            @click="styleSettings = { landmarkColor: '#22d3ee', pointColor: '#ffffff', lineWidth: 3, pointRadius: 4 }"
            class="text-[10px] uppercase font-bold text-slate-500 hover:text-teal-400 transition-colors"
          >
            Reset Defaults
          </button>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div class="space-y-2">
            <label class="block text-[10px] text-slate-500 uppercase font-bold tracking-wider">Skeleton Color</label>
            <div class="flex items-center gap-2">
              <input type="color" v-model="styleSettings.landmarkColor" class="h-8 w-8 rounded cursor-pointer bg-transparent border-none" />
              <span class="text-xs text-slate-300 font-mono underline decoration-teal-500/30 decoration-2">{{ styleSettings.landmarkColor }}</span>
            </div>
          </div>
          <div class="space-y-2">
            <label class="block text-[10px] text-slate-500 uppercase font-bold tracking-wider">Joint Color</label>
            <div class="flex items-center gap-2">
              <input type="color" v-model="styleSettings.pointColor" class="h-8 w-8 rounded cursor-pointer bg-transparent border-none" />
              <span class="text-xs text-slate-300 font-mono underline decoration-teal-500/30 decoration-2">{{ styleSettings.pointColor }}</span>
            </div>
          </div>
          <div class="space-y-2">
            <label class="block text-[10px] text-slate-500 uppercase font-bold tracking-wider text-center">Line Thickness ({{ styleSettings.lineWidth }}px)</label>
            <input type="range" v-model.number="styleSettings.lineWidth" min="1" max="10" step="1" class="w-full accent-teal-500 bg-slate-800" />
          </div>
          <div class="space-y-2">
            <label class="block text-[10px] text-slate-500 uppercase font-bold tracking-wider text-center">Joint Size ({{ styleSettings.pointRadius }}px)</label>
            <input type="range" v-model.number="styleSettings.pointRadius" min="1" max="12" step="1" class="w-full accent-teal-500 bg-slate-800" />
          </div>
        </div>
      </div>

      <div class="mt-4 relative aspect-video w-full overflow-hidden rounded-xl border border-slate-700 bg-black">
        <video v-show="!isFusionMode && modelModality !== 'sensor' || isFusionMode" ref="videoEl" autoplay playsinline muted :class="videoClasses"></video>
        <canvas v-show="!isFusionMode && modelModality !== 'sensor' || isFusionMode" ref="landmarkCanvasEl" class="absolute inset-0 h-full w-full"></canvas>
        <canvas v-show="!isFusionMode && modelModality !== 'sensor' || isFusionMode" ref="bboxCanvasEl" class="absolute inset-0 h-full w-full"></canvas>
        
        <!-- Sensor Overlay (Always visible in Fusion or Sensor Mode) -->
        <div v-if="isFusionMode || modelModality === 'sensor'" class="absolute right-0 top-0 bottom-0 w-48 overflow-auto bg-slate-950/80 p-3 border-l border-slate-700 backdrop-blur-sm">
          <p class="text-[10px] text-amber-500 font-bold uppercase mb-2">Sensor Stream</p>
          <div class="space-y-1">
            <div
              v-for="item in sensorDisplayRows"
              :key="item.label"
              class="flex justify-between text-[10px] border-b border-slate-800 pb-1"
            >
              <span class="text-slate-500">{{ item.label }}</span>
              <span class="text-slate-200 font-mono">{{ Number(item.value).toFixed(2) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Prediction Output -->
      <div class="mt-4 rounded-lg border border-slate-800 bg-slate-950/40 p-3 text-sm">
        <div class="flex items-center justify-between mb-2">
           <p class="text-slate-400">Final Prediction</p>
           <span v-if="isFusionMode" class="text-[10px] bg-teal-500/20 text-teal-400 px-2 py-0.5 rounded font-bold uppercase">Weighted Fusion</span>
        </div>

        <div v-if="prediction" class="flex items-end justify-between">
           <div>
              <p class="text-2xl font-bold text-white">
                {{ prediction.label }}
              </p>
              <p class="text-xs text-slate-500 mt-1">
                Confidence: {{ (prediction.confidence * 100).toFixed(2) }}% | {{ prediction.note }}
              </p>
           </div>
           <div v-if="prediction.top3" class="text-right">
              <p class="text-[10px] text-slate-500 uppercase font-bold mb-1">Top Alternatives</p>
              <div class="flex flex-col gap-1">
                 <div v-for="alt in prediction.top3.slice(1)" :key="alt.label" class="text-[11px] text-slate-400">
                    {{ alt.label }} ({{ (alt.confidence * 100).toFixed(1) }}%)
                 </div>
              </div>
           </div>
        </div>
        <p v-else class="text-slate-500 mt-1">Ready to predict...</p>

        <!-- Fusion Breakdown -->
        <div v-if="isFusionMode && (cvPrediction || sensorPrediction)" class="mt-4 pt-4 border-t border-slate-800 grid grid-cols-2 gap-4">
           <div class="p-2 rounded bg-blue-500/5 border border-blue-500/10">
              <p class="text-[9px] text-blue-400 font-bold uppercase mb-1">Vision Contribution ({{ ((1 - gloveWeight) * 100).toFixed(0) }}%)</p>
              <p v-if="cvPrediction" class="text-xs font-semibold text-slate-200">{{ cvPrediction.label }} ({{ (cvPrediction.confidence * 100).toFixed(1) }}%)</p>
              <p v-else class="text-xs text-slate-600 italic">Waiting...</p>
           </div>
           <div class="p-2 rounded bg-amber-500/5 border border-amber-500/10">
              <p class="text-[9px] text-amber-400 font-bold uppercase mb-1">Glove Contribution ({{ (gloveWeight * 100).toFixed(0) }}%)</p>
              <p v-if="sensorPrediction" class="text-xs font-semibold text-slate-200">{{ sensorPrediction.label }} ({{ (sensorPrediction.confidence * 100).toFixed(1) }}%)</p>
              <p v-else class="text-xs text-slate-600 italic">Waiting...</p>
           </div>
        </div>

        <!-- Feedback UI -->
        <div v-if="prediction && prediction.label !== 'Waiting...' && prediction.label !== 'error'" class="mt-4 pt-3 border-t border-slate-800/50 flex items-center justify-between">
           <span class="text-[10px] text-slate-500 uppercase font-bold tracking-widest">Was this correct?</span>
           <div class="flex gap-2">
              <template v-if="!feedbackSent">
                <button 
                  @click="submitFeedback(true)"
                  class="flex items-center gap-1.5 px-2 py-1 rounded bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 text-xs font-semibold transition-colors"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                  Correct
                </button>
                <button 
                  @click="openCorrectionDialog"
                  class="flex items-center gap-1.5 px-2 py-1 rounded bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 text-xs font-semibold transition-colors"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                  Wrong
                </button>
              </template>
              <div v-else class="flex items-center gap-1.5 text-xs text-teal-400 font-medium italic opacity-80">
                 <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                 Feedback saved
              </div>
           </div>
        </div>
      </div>

      <Dialog v-model:visible="showCorrectionDialog" modal header="Correct Prediction" :style="{ width: '25rem' }">
        <div class="space-y-4 py-2">
          <p class="text-sm text-slate-400">
            Current prediction for the model is <span class="text-white font-bold">"{{ prediction?.label }}"</span>.
            What was the actual gesture?
          </p>
          <div class="space-y-2">
            <label class="text-xs font-bold text-slate-500 uppercase">Select True Gesture</label>
            <select 
              v-model="correctedLabel"
              class="w-full bg-slate-900 text-white rounded border border-slate-700 px-3 py-2 outline-none"
            >
              <option value="" disabled>-- Select Gesture --</option>
              <option v-for="l in activeModel?.metadata?.labels || []" :key="l" :value="l">{{ l }}</option>
              <option value="Unknown">Other / Not in list</option>
            </select>
          </div>
          <div class="flex justify-end gap-2 pt-2">
            <BaseBtn variant="secondary" @click="showCorrectionDialog = false">Cancel</BaseBtn>
            <BaseBtn 
              variant="primary" 
              :disabled="!correctedLabel || isSubmittingFeedback" 
              @click="submitFeedback(false, correctedLabel)"
            >
              {{ isSubmittingFeedback ? 'Submitting...' : 'Submit Correction' }}
            </BaseBtn>
          </div>
        </div>
      </Dialog>

      <p class="mt-3 text-xs text-slate-500 flex justify-end">
        Supported inference adapters in this phase: exported `.tflite`, `.keras`, `.h5`, `.pth`, `.pt` with valid metadata contract.
      </p>
    </BaseCard>
  </div>
</template>
