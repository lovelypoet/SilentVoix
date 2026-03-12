<script setup>
import { ref, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'

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

onUnmounted(() => {
  engine.stopAll()
})
</script>

<template>
  <div class="max-w-7xl mx-auto space-y-6">
    <section class="mb-2 grid grid-cols-[auto_1fr] md:grid-cols-3 items-center gap-3">
      <div class="flex justify-start">
        <BaseBtn variant="secondary" title="Return" class="px-3" @click="router.push('/training')">
          &larr;
        </BaseBtn>
      </div>
      <div class="text-left md:text-center">
        <h1 class="text-2xl md:text-3xl font-bold text-white mb-2">Realtime AI Playground</h1>
        <p class="text-slate-400">Upload exported model package metadata and test live CV or sensor inference.</p>
      </div>
    </section>

    <!-- Model Management -->
    <BaseCard>
      <div class="flex flex-col gap-6">
        <ModelSelector />
        <div class="border-t border-slate-800 pt-6">
          <FusionControls :fusion-logic="engine.fusionLogic" />
        </div>
      </div>
    </BaseCard>

    <!-- Preview & Inference -->
    <BaseCard>
      <div class="flex flex-wrap items-center justify-between gap-2 mb-4">
        <h2 class="text-xl text-white font-semibold">Live Preview</h2>
        <div class="flex gap-2">
           <BaseBtn variant="secondary" @click="toggleLive">
             {{ store.isLive ? 'Stop Live' : 'Start Live' }}
           </BaseBtn>
        </div>
      </div>

      <div class="relative">
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
      </div>

      <PredictionOutput />
      
      <p class="mt-3 text-xs text-slate-500 flex justify-end">
        Supported inference adapters: exported `.tflite`, `.keras`, `.h5`, `.pth`, `.pt` with valid metadata contract.
      </p>
    </BaseCard>
  </div>
</template>
