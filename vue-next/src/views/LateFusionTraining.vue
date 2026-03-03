<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import api from '../services/api'

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

const openCsvLibrary = () => {
  router.push({
    path: '/csv-library',
    query: {
      pipeline: 'late',
      mode: mode.value
    }
  })
}

onMounted(() => {
  void loadSelectionStatus()
  void loadLatestResult()
})

watch(mode, () => {
  stopPolling()
  activeJobId.value = ''
  activeJob.value = null
  runError.value = ''
  void loadSelectionStatus()
  void loadLatestResult()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <div class="max-w-5xl mx-auto space-y-6">
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
      </div>
    </BaseCard>
  </div>
</template>
