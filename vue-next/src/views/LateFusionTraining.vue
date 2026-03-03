<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import api from '../services/api'
import { useHandTracking } from '../composables/useHandTracking.js'

const router = useRouter()

const mode = ref('single')
const isLoading = ref(false)
const error = ref('')
const selectionStatus = ref(null)
const gloveWeight = ref(0.8)
const isSubmittingRun = ref(false)
const activeJobId = ref('')
const activeJob = ref(null)
const latestResult = ref(null)
const runError = ref('')
let jobPollTimer = null

const isCompletePair = computed(() => Boolean(selectionStatus.value?.is_complete_pair))
const selectedCv = computed(() => selectionStatus.value?.cv?.name || '')
const selectedSensor = computed(() => selectionStatus.value?.sensor?.name || '')
const visionWeight = computed(() => Math.max(0, 1 - Number(gloveWeight.value || 0)))
const runStatus = computed(() => activeJob.value?.status || 'idle')
const runMetrics = computed(() => activeJob.value?.result?.metrics || latestResult.value?.metrics || null)
const hasArtifacts = computed(() => Boolean(latestResult.value?.artifacts))
const expectedCvDim = computed(() => Number(latestResult.value?.feature_spec?.cv_dim || (mode.value === 'dual' ? 126 : 63)))
const expectedSensorDim = computed(() => Number(latestResult.value?.feature_spec?.sensor_dim || (mode.value === 'dual' ? 22 : 11)))
const cvFeatureColumns = computed(() => {
  const cols = latestResult.value?.feature_spec?.cv_columns
  return Array.isArray(cols) ? cols : []
})
const predictCvInput = ref('')
const predictSensorInput = ref('')
const isPredicting = ref(false)
const predictError = ref('')
const predictResult = ref(null)
const cvVideoEl = ref(null)
const cvCanvasEl = ref(null)
const cvMirror = ref(false)
const cvShowLandmarks = ref(false)
const cvLiveStream = ref(null)
const isCvLive = ref(false)
const cvLiveStatus = ref('CV live is idle.')
const latestLiveCvVector = ref([])
const { startHandTracking, stopHandTracking, onFrame } = useHandTracking(cvMirror, cvShowLandmarks)

const loadSelectionStatus = async () => {
  isLoading.value = true
  error.value = ''
  try {
    const res = await api.admin.csvLibrary.selection.get('late', mode.value)
    selectionStatus.value = res || null
  } catch (e) {
    selectionStatus.value = null
    error.value = e?.response?.data?.detail || 'Failed to load late-fusion dataset selection.'
  } finally {
    isLoading.value = false
  }
}

const loadLatestResult = async () => {
  try {
    const res = await api.training.lateFusion.getLatest(mode.value)
    latestResult.value = res?.data || null
  } catch {
    latestResult.value = null
  }
}

const stopPolling = () => {
  if (jobPollTimer) {
    clearInterval(jobPollTimer)
    jobPollTimer = null
  }
}

const pollJob = async () => {
  if (!activeJobId.value) return
  try {
    const res = await api.training.lateFusion.getJob(activeJobId.value)
    activeJob.value = res?.job || null
    if (['failed', 'succeeded'].includes(activeJob.value?.status)) {
      stopPolling()
      await loadLatestResult()
    }
  } catch (e) {
    runError.value = e?.response?.data?.detail || 'Failed to poll late-fusion job status.'
    stopPolling()
  }
}

const startRun = async () => {
  if (!isCompletePair.value || isSubmittingRun.value) return
  isSubmittingRun.value = true
  runError.value = ''
  try {
    const gwRaw = Number(gloveWeight.value)
    const gw = Number.isFinite(gwRaw) ? Math.min(1, Math.max(0, gwRaw)) : 0.8
    gloveWeight.value = gw
    const res = await api.training.lateFusion.run(mode.value, gw)
    activeJobId.value = res?.job_id || ''
    activeJob.value = {
      status: 'queued',
      mode: mode.value,
      progress: 'Queued',
      glove_weight: gw,
      vision_weight: 1 - gw
    }
    stopPolling()
    jobPollTimer = setInterval(() => {
      void pollJob()
    }, 1200)
    await pollJob()
  } catch (e) {
    runError.value = e?.response?.data?.detail || 'Failed to start late-fusion training.'
  } finally {
    isSubmittingRun.value = false
  }
}

const downloadArtifact = async (artifact) => {
  runError.value = ''
  try {
    const blob = await api.training.lateFusion.downloadLatestArtifact(mode.value, artifact)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const ext = artifact === 'report' ? 'json' : (artifact === 'aligned_preview' ? 'csv' : 'joblib')
    a.download = `late_fusion_${mode.value}_${artifact}.${ext}`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    runError.value = e?.response?.data?.detail || `Failed to download ${artifact} artifact.`
  }
}

const deriveCvVectorFromResults = (results) => {
  const handMap = {}
  const landmarks = results?.landmarks || []
  const handedness = results?.handedness || []
  let leftHand = null
  let rightHand = null

  for (let i = 0; i < landmarks.length; i++) {
    const handLabel = handedness?.[i]?.[0]?.categoryName || ''
    if (handLabel === 'Left') leftHand = landmarks[i]
    else if (handLabel === 'Right') rightHand = landmarks[i]
    else if (!leftHand) leftHand = landmarks[i]
    else if (!rightHand) rightHand = landmarks[i]
  }

  if (leftHand?.length === 21) {
    for (let i = 0; i < 21; i++) {
      handMap[`L_x${i}`] = Number(leftHand[i]?.x ?? 0)
      handMap[`L_y${i}`] = Number(leftHand[i]?.y ?? 0)
      handMap[`L_z${i}`] = Number(leftHand[i]?.z ?? 0)
    }
  }
  if (rightHand?.length === 21) {
    for (let i = 0; i < 21; i++) {
      handMap[`R_x${i}`] = Number(rightHand[i]?.x ?? 0)
      handMap[`R_y${i}`] = Number(rightHand[i]?.y ?? 0)
      handMap[`R_z${i}`] = Number(rightHand[i]?.z ?? 0)
    }
  }

  let vector = []
  if (cvFeatureColumns.value.length) {
    vector = cvFeatureColumns.value.map((key) => Number(handMap[key] ?? 0))
  } else if (mode.value === 'dual') {
    for (let i = 0; i < 21; i++) vector.push(Number(handMap[`L_x${i}`] ?? 0), Number(handMap[`L_y${i}`] ?? 0), Number(handMap[`L_z${i}`] ?? 0))
    for (let i = 0; i < 21; i++) vector.push(Number(handMap[`R_x${i}`] ?? 0), Number(handMap[`R_y${i}`] ?? 0), Number(handMap[`R_z${i}`] ?? 0))
  } else {
    const preferLeft = Object.prototype.hasOwnProperty.call(handMap, 'L_x0')
    const prefix = preferLeft ? 'L' : 'R'
    for (let i = 0; i < 21; i++) vector.push(Number(handMap[`${prefix}_x${i}`] ?? 0), Number(handMap[`${prefix}_y${i}`] ?? 0), Number(handMap[`${prefix}_z${i}`] ?? 0))
  }

  const detectedHands = [leftHand, rightHand].filter(Boolean).length
  return { vector, detectedHands }
}

const stopCvLive = () => {
  stopHandTracking()
  if (cvLiveStream.value) {
    cvLiveStream.value.getTracks().forEach((track) => track.stop())
    cvLiveStream.value = null
  }
  isCvLive.value = false
  cvLiveStatus.value = 'CV live is stopped.'
}

const startCvLive = async () => {
  predictError.value = ''
  cvLiveStatus.value = 'Requesting camera...'
  try {
    stopCvLive()
    const mediaStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    cvLiveStream.value = mediaStream
    await startHandTracking(cvVideoEl.value, cvCanvasEl.value, mediaStream)
    onFrame((results) => {
      if (!results) return
      const { vector, detectedHands } = deriveCvVectorFromResults(results)
      if (vector.length !== expectedCvDim.value) return
      latestLiveCvVector.value = vector
      predictCvInput.value = JSON.stringify(vector)
      cvLiveStatus.value = `CV live updated (${detectedHands} hand${detectedHands === 1 ? '' : 's'} detected).`
    })
    isCvLive.value = true
  } catch (e) {
    cvLiveStatus.value = e?.message || 'Failed to start CV live capture.'
    stopCvLive()
  }
}

const useLatestLiveCv = () => {
  if (!latestLiveCvVector.value.length) {
    predictError.value = 'No live CV vector available yet. Start CV Live first.'
    return
  }
  predictCvInput.value = JSON.stringify(latestLiveCvVector.value)
  predictError.value = ''
}

const useLatestSensorSnapshot = async () => {
  predictError.value = ''
  try {
    const res = await api.utils.latestSensorFrame()
    const raw = Array.isArray(res?.values) ? res.values.map((v) => Number(v)) : []
    if (!raw.length) {
      throw new Error('No sensor values returned from /gesture/latest')
    }
    let vector = raw
    if (expectedSensorDim.value === 22 && raw.length === 11) {
      vector = [...raw, ...raw]
    }
    if (vector.length !== expectedSensorDim.value) {
      throw new Error(`Sensor snapshot length mismatch: expected ${expectedSensorDim.value}, got ${vector.length}`)
    }
    predictSensorInput.value = JSON.stringify(vector)
  } catch (e) {
    predictError.value = e?.response?.data?.detail || e?.message || 'Failed to pull live sensor snapshot.'
  }
}

const fillZeroVectors = () => {
  predictCvInput.value = JSON.stringify(Array.from({ length: expectedCvDim.value }, () => 0))
  predictSensorInput.value = JSON.stringify(Array.from({ length: expectedSensorDim.value }, () => 0))
}

const parsePredictVector = (rawText, expectedLength, fieldName) => {
  let parsed
  try {
    parsed = JSON.parse(rawText)
  } catch {
    throw new Error(`${fieldName} must be valid JSON array`)
  }
  if (!Array.isArray(parsed)) {
    throw new Error(`${fieldName} must be a JSON array`)
  }
  if (parsed.length !== expectedLength) {
    throw new Error(`${fieldName} length must be ${expectedLength}, got ${parsed.length}`)
  }
  const values = parsed.map((v) => Number(v))
  if (values.some((v) => Number.isNaN(v))) {
    throw new Error(`${fieldName} contains non-numeric values`)
  }
  return values
}

const runTestPredict = async () => {
  isPredicting.value = true
  predictError.value = ''
  predictResult.value = null
  try {
    const cvValues = parsePredictVector(predictCvInput.value, expectedCvDim.value, 'CV vector')
    const sensorValues = parsePredictVector(predictSensorInput.value, expectedSensorDim.value, 'Sensor vector')
    const payload = {
      mode: mode.value,
      cv_values: cvValues,
      sensor_values: sensorValues,
      glove_weight: Number(gloveWeight.value)
    }
    const res = await api.training.lateFusion.predict(payload)
    predictResult.value = res?.prediction || null
  } catch (e) {
    predictError.value = e?.response?.data?.detail || e?.message || 'Prediction failed.'
  } finally {
    isPredicting.value = false
  }
}

const openCsvLibrary = () => {
  router.push({
    path: '/csv-library',
    query: {
      pipeline: 'late',
      mode: mode.value
    }
  })
}

const goFusionWorkspace = () => {
  router.push({ path: '/fusion', query: { tab: 'late' } })
}

onMounted(() => {
  void loadSelectionStatus()
  void loadLatestResult()
  fillZeroVectors()
})

watch(mode, () => {
  stopPolling()
  activeJobId.value = ''
  activeJob.value = null
  runError.value = ''
  predictError.value = ''
  predictResult.value = null
  fillZeroVectors()
  void loadSelectionStatus()
  void loadLatestResult()
})

onUnmounted(() => {
  stopPolling()
  stopCvLive()
})
</script>

<template>
  <div class="max-w-5xl mx-auto space-y-6">
    <div class="mb-8 grid grid-cols-[auto_1fr] md:grid-cols-3 items-center gap-3">
      <div class="flex justify-start">
        <BaseBtn
          variant="secondary"
          title="Return to fusion workspace"
          class="px-3"
          @click="goFusionWorkspace"
        >
          &larr;
        </BaseBtn>
      </div>
      <div class="text-left md:text-center">
        <h1 class="text-2xl md:text-3xl font-bold text-white mb-2">Late Fusion Training</h1>
        <p class="text-slate-400">
          Select paired CV + Sensor datasets, then run late-fusion training.
        </p>
      </div>
      <div class="hidden md:block"></div>
    </div>

    <BaseCard>
      <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div class="flex-1">
          <p class="text-sm text-slate-300 mb-2">Mode</p>
          <div class="inline-flex rounded-md border border-slate-700 overflow-hidden">
            <button
              class="px-4 py-2 text-sm"
              :class="mode === 'single' ? 'bg-cyan-500/20 text-cyan-300' : 'bg-slate-900 text-slate-300 hover:bg-slate-800'"
              @click="mode = 'single'"
            >
              Single
            </button>
            <button
              class="px-4 py-2 text-sm border-l border-slate-700"
              :class="mode === 'dual' ? 'bg-cyan-500/20 text-cyan-300' : 'bg-slate-900 text-slate-300 hover:bg-slate-800'"
              @click="mode = 'dual'"
            >
              Dual
            </button>
          </div>
        </div>

        <div class="flex-1">
          <p class="text-sm text-slate-300 mb-2">Fusion Weights</p>
          <div class="grid grid-cols-2 gap-2 text-sm">
            <label class="text-slate-300">
              Glove
              <input
                v-model.number="gloveWeight"
                type="number"
                min="0"
                max="1"
                step="0.05"
                class="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-white"
              />
            </label>
            <label class="text-slate-300">
              Vision
              <input
                :value="visionWeight.toFixed(2)"
                type="text"
                readonly
                class="mt-1 w-full rounded border border-slate-700 bg-slate-800 px-3 py-2 text-slate-300"
              />
            </label>
          </div>
        </div>

        <div class="flex gap-2">
          <BaseBtn variant="secondary" :disabled="isLoading" @click="loadSelectionStatus">
            {{ isLoading ? 'Refreshing...' : 'Refresh Status' }}
          </BaseBtn>
          <BaseBtn variant="primary" @click="openCsvLibrary">
            Open CSV Library
          </BaseBtn>
          <BaseBtn
            variant="primary"
            :disabled="!isCompletePair || isSubmittingRun || runStatus === 'running' || runStatus === 'queued'"
            @click="startRun"
          >
            {{ isSubmittingRun || runStatus === 'running' || runStatus === 'queued' ? 'Running...' : 'Run Late Fusion Training' }}
          </BaseBtn>
        </div>
      </div>
    </BaseCard>

    <BaseCard>
      <p v-if="error" class="text-red-300 text-sm mb-4">{{ error }}</p>
      <p v-if="runError" class="text-red-300 text-sm mb-4">{{ runError }}</p>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="rounded-lg border border-slate-800 p-4 bg-slate-950/50">
          <p class="text-xs text-slate-400 uppercase tracking-wide mb-1">CV Dataset</p>
          <p class="text-sm text-slate-100 break-all">
            {{ selectedCv || 'Not selected' }}
          </p>
        </div>

        <div class="rounded-lg border border-slate-800 p-4 bg-slate-950/50">
          <p class="text-xs text-slate-400 uppercase tracking-wide mb-1">Sensor Dataset</p>
          <p class="text-sm text-slate-100 break-all">
            {{ selectedSensor || 'Not selected' }}
          </p>
        </div>
      </div>

      <div class="mt-4 rounded-lg border p-4" :class="isCompletePair ? 'border-emerald-500/40 bg-emerald-500/10' : 'border-amber-500/40 bg-amber-500/10'">
        <p class="text-sm" :class="isCompletePair ? 'text-emerald-200' : 'text-amber-200'">
          {{ isCompletePair
            ? 'Pair is complete. You can proceed with late-fusion training pipeline.'
            : 'Pair incomplete. Select both CV and Sensor datasets in CSV Library first.' }}
        </p>
      </div>

      <div class="mt-4 rounded-lg border border-slate-800 bg-slate-950/50 p-4">
        <p class="text-xs text-slate-400 uppercase tracking-wide mb-1">Run Status</p>
        <p class="text-sm text-slate-200 capitalize">
          {{ runStatus }}
          <span v-if="activeJob?.progress" class="text-slate-400">| {{ activeJob.progress }}</span>
        </p>
        <p v-if="activeJob?.error" class="mt-2 text-sm text-rose-300">{{ activeJob.error }}</p>
      </div>

      <div v-if="runMetrics" class="mt-4 rounded-lg border border-slate-800 bg-slate-950/50 p-4">
        <p class="text-xs text-slate-400 uppercase tracking-wide mb-2">Latest Metrics</p>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <div>
            <p class="text-slate-400">Accuracy</p>
            <p class="text-slate-100">{{ (runMetrics.accuracy * 100).toFixed(2) }}%</p>
          </div>
          <div>
            <p class="text-slate-400">Macro F1</p>
            <p class="text-slate-100">{{ runMetrics.macro_f1?.toFixed(4) }}</p>
          </div>
          <div>
            <p class="text-slate-400">Train Rows</p>
            <p class="text-slate-100">{{ runMetrics.train_rows }}</p>
          </div>
          <div>
            <p class="text-slate-400">Test Rows</p>
            <p class="text-slate-100">{{ runMetrics.test_rows }}</p>
          </div>
        </div>
        <div v-if="hasArtifacts" class="mt-4 flex flex-wrap gap-2">
          <BaseBtn variant="secondary" @click="downloadArtifact('report')">Download Report</BaseBtn>
          <BaseBtn variant="secondary" @click="downloadArtifact('aligned_preview')">Download Aligned CSV</BaseBtn>
          <BaseBtn variant="secondary" @click="downloadArtifact('cv_model')">Download CV Model</BaseBtn>
          <BaseBtn variant="secondary" @click="downloadArtifact('sensor_model')">Download Sensor Model</BaseBtn>
        </div>
      </div>

      <div class="mt-4 rounded-lg border border-slate-800 bg-slate-950/50 p-4">
        <div class="flex items-center justify-between gap-2 mb-3">
          <p class="text-xs text-slate-400 uppercase tracking-wide">Test Predict (Latest Model)</p>
          <BaseBtn variant="secondary" @click="fillZeroVectors">Fill Zero Vectors</BaseBtn>
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <label class="text-sm text-slate-300">
            CV vector ({{ expectedCvDim }})
            <textarea
              v-model="predictCvInput"
              rows="5"
              class="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 font-mono text-xs"
            ></textarea>
          </label>
          <label class="text-sm text-slate-300">
            Sensor vector ({{ expectedSensorDim }})
            <textarea
              v-model="predictSensorInput"
              rows="5"
              class="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 font-mono text-xs"
            ></textarea>
          </label>
        </div>
        <div class="mt-3 flex items-center gap-2">
          <BaseBtn variant="secondary" :disabled="isCvLive" @click="startCvLive">Start CV Live</BaseBtn>
          <BaseBtn variant="secondary" :disabled="!isCvLive" @click="stopCvLive">Stop CV Live</BaseBtn>
          <BaseBtn variant="secondary" @click="useLatestLiveCv">Use Latest CV Live</BaseBtn>
          <BaseBtn variant="secondary" @click="useLatestSensorSnapshot">Use Live Sensor Snapshot</BaseBtn>
          <BaseBtn variant="primary" :disabled="isPredicting" @click="runTestPredict">
            {{ isPredicting ? 'Predicting...' : 'Run Test Predict' }}
          </BaseBtn>
        </div>
        <p class="mt-2 text-xs text-slate-400">{{ cvLiveStatus }}</p>
        <video ref="cvVideoEl" class="hidden" autoplay playsinline muted></video>
        <canvas ref="cvCanvasEl" class="hidden"></canvas>
        <p v-if="predictError" class="mt-2 text-sm text-rose-300">{{ predictError }}</p>
        <div v-if="predictResult" class="mt-3 rounded border border-slate-700 p-3 bg-slate-900/60">
          <p class="text-sm text-slate-100">
            Predicted: <span class="font-semibold">{{ predictResult.label }}</span>
            ({{ (Number(predictResult.confidence || 0) * 100).toFixed(2) }}%)
          </p>
          <p class="text-xs text-slate-400 mt-1 break-all">
            {{ JSON.stringify(predictResult.probabilities) }}
          </p>
        </div>
      </div>
    </BaseCard>
  </div>
</template>
