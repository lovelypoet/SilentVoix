<script setup>
import { computed, ref, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { PhCamera, PhCpu, PhWaveform, PhVideoCamera, PhCaretRight } from '@phosphor-icons/vue'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import BasePageHeader from '../components/base/BasePageHeader.vue'
import StatusIndicator from '../components/base/StatusIndicator.vue'

// Refactored Imports
import { usePlaygroundEngine } from '@/engine/playgroundEngine'
import ModelSelector from '@/components/playground/ModelSelector.vue'
import CameraStream from '@/components/playground/CameraStream.vue'
import PredictionOutput from '@/components/playground/PredictionOutput.vue'
import FusionControls from '@/components/playground/FusionControls.vue'
import SerialMonitor from '@/components/playground/SerialMonitor.vue'
import { useInferencePipeline } from '@/composables/ai/useInferencePipeline'

const router = useRouter()
const engine = usePlaygroundEngine()
const pipeline = useInferencePipeline()
const store = engine.store

// UI State
const mirrorCamera = ref(true)
const showLandmarks = ref(true)
const styleSettings = ref({
  landmarkColor: '#22d3ee',
  pointColor: '#ffffff',
  lineWidth: 3,
  pointRadius: 4
})

const cameraRef = ref(null)

const toggleLive = async () => {
  if (store.isLive) {
    cameraRef.value?.stop()
  } else {
    await cameraRef.value?.start()
  }
}

const handleResults = (results) => {
  if (store.isFusionMode) {
    // Fusion logic to be moved to Engine
  } else if (!store.useIntegratedMode) {
    if (results?.landmarks?.length) {
      pipeline.predictCv(results)
    }
  }
}

// --- Pipeline status strip: Sensor/Camera -> AI Model -> Gesture -> Voice.
// Only stages we can genuinely observe get a live/processing state; nothing
// here is faked when the runtime hasn't reported anything yet.
const needsSensor = computed(() => store.isFusionMode || store.isEarlyFusionMode || store.modelModality === 'sensor')

const inputState = computed(() => {
  if (needsSensor.value) return engine.sensorStream.isConnected.value ? 'connected' : (store.isLive ? 'disconnected' : 'standby')
  return store.isLive ? 'active' : 'standby'
})

const modelState = computed(() => (store.activeModel ? 'ready' : 'unavailable'))

const outputState = computed(() => {
  if (!store.isLive) return 'standby'
  return store.prediction ? 'active' : 'processing'
})

// Pipeline rail labels - what's actually active, not just a category name,
// so the answer to "what input / which model" is readable at a glance
// instead of only living in the sidebar.
const inputLabel = computed(() => {
  if (store.isFusionMode || store.isEarlyFusionMode) return 'Camera + Sensor'
  if (!store.activeModel) return 'Sensor / Camera'
  return store.modelModality === 'sensor' ? 'Glove Sensor' : 'Camera'
})

const modelLabel = computed(() => store.activeModel?.display_name || store.activeModel?.id || 'AI Model')

onUnmounted(() => {
  engine.stopAll()
})
</script>

<template>
  <div class="max-w-7xl mx-auto space-y-6">
    <BasePageHeader
      title="Realtime AI Playground"
      description="Live inference control room — validate a model package against camera or sensor input in real time."
      eyebrow="Mission Control"
      back-label="Return to training"
      @back="router.push('/training')"
    />

    <!-- Pipeline telemetry rail: the product's core concept, made literal -->
    <div class="telemetry-rail grid-texture">
      <div class="flex min-w-[8.5rem] items-center gap-2.5">
        <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-500/10 text-brand-400">
          <PhCamera size="15" weight="bold" aria-hidden="true" />
        </span>
        <div class="min-w-0">
          <p class="text-[11px] font-medium text-slate-300 truncate max-w-[9rem]" :title="inputLabel">{{ inputLabel }}</p>
          <StatusIndicator :state="inputState" size="sm" />
        </div>
      </div>
      <PhCaretRight size="14" weight="bold" class="pipeline-arrow" aria-hidden="true" />
      <div class="pipeline-rail"></div>
      <div class="flex min-w-[8.5rem] items-center gap-2.5">
        <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-alt-500/10 text-brand-alt-400">
          <PhCpu size="15" weight="bold" aria-hidden="true" />
        </span>
        <div class="min-w-0">
          <p class="text-[11px] font-medium text-slate-300 truncate max-w-[9rem]" :title="modelLabel">{{ modelLabel }}</p>
          <StatusIndicator :state="modelState" size="sm" />
        </div>
      </div>
      <PhCaretRight size="14" weight="bold" class="pipeline-arrow" aria-hidden="true" />
      <div class="pipeline-rail"></div>
      <div class="flex min-w-[8.5rem] items-center gap-2.5">
        <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-pink-500/10 text-brand-pink-400">
          <PhWaveform size="15" weight="bold" aria-hidden="true" />
        </span>
        <div>
          <p class="text-[11px] font-medium text-slate-300">Prediction</p>
          <StatusIndicator :state="outputState" size="sm" :label="outputState === 'active' ? 'Recognized' : undefined" />
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start">
      <!-- Viewport + signal output -->
      <div class="space-y-6 lg:min-w-0">
        <BaseCard class="!p-3 sm:!p-4">
          <div class="flex flex-wrap items-center justify-between gap-2 px-1 pb-3">
            <div class="flex items-center gap-2">
              <PhVideoCamera size="17" weight="bold" class="text-brand-400" aria-hidden="true" />
              <h2 class="text-sm font-semibold uppercase tracking-wide text-slate-200">Live Viewport</h2>
            </div>
            <BaseBtn :variant="store.isLive ? 'secondary' : 'primary'" @click="toggleLive">
              {{ store.isLive ? 'Stop Live' : 'Start Live' }}
            </BaseBtn>
          </div>

          <CameraStream
            ref="cameraRef"
            :mirror="mirrorCamera"
            :show-landmarks="showLandmarks"
            :style-settings="styleSettings"
            @results="handleResults"
          >
            <template #overlay>
              <SerialMonitor :sensor-stream="engine.sensorStream" />
            </template>
          </CameraStream>

          <PredictionOutput />
        </BaseCard>
      </div>

      <!-- Model + pipeline controls -->
      <div class="space-y-6 lg:sticky lg:top-6">
        <BaseCard>
          <div class="flex flex-col gap-6">
            <div>
              <h2 class="text-sm font-semibold uppercase tracking-wide text-slate-200 mb-3">Active Model</h2>
              <ModelSelector />
            </div>
            <div class="border-t border-slate-800 pt-6">
              <FusionControls :fusion-logic="engine.fusionLogic" />
            </div>
            <div class="border-t border-slate-800 pt-6">
              <h2 class="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">Display</h2>
              <p class="text-xs text-slate-500 mb-3">Viewport rendering — takes effect on the next frame.</p>
              <div class="space-y-2.5">
                <label class="flex items-center justify-between cursor-pointer">
                  <span class="text-sm text-slate-300">Mirror camera</span>
                  <button
                    type="button"
                    role="switch"
                    :aria-checked="mirrorCamera"
                    aria-label="Mirror camera"
                    class="focus-ring relative inline-flex h-6 w-11 items-center rounded-full transition-colors"
                    :class="mirrorCamera ? 'bg-brand-500' : 'bg-slate-700'"
                    @click="mirrorCamera = !mirrorCamera"
                  >
                    <span class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform" :class="mirrorCamera ? 'translate-x-6' : 'translate-x-1'"></span>
                  </button>
                </label>
                <label class="flex items-center justify-between cursor-pointer">
                  <span class="text-sm text-slate-300">Hand landmarks</span>
                  <button
                    type="button"
                    role="switch"
                    :aria-checked="showLandmarks"
                    aria-label="Show hand landmarks"
                    class="focus-ring relative inline-flex h-6 w-11 items-center rounded-full transition-colors"
                    :class="showLandmarks ? 'bg-brand-500' : 'bg-slate-700'"
                    @click="showLandmarks = !showLandmarks"
                  >
                    <span class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform" :class="showLandmarks ? 'translate-x-6' : 'translate-x-1'"></span>
                  </button>
                </label>
              </div>
            </div>
          </div>
        </BaseCard>
      </div>
    </div>
  </div>
</template>
