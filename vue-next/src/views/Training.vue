<script setup>
// Modified by Gemini CLI
import { ref, watchEffect, computed } from 'vue'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import TrainingSettings from '../components/TrainingSettings.vue'
import { useMediaPermissions } from '../composables/useMediaPermissions.js'
import { useTrainingSettings } from '../composables/useTrainingSettings.js'
import { useHandTracking } from '../composables/useHandTracking.js'

const isTraining = ref(false)
const showSettings = ref(false)
const videoEl = ref(null)
const canvasEl = ref(null)

const { hasPermissions, isRequesting, error, stream, requestPermissions, stopStream } = useMediaPermissions()
const { mirrorCamera, enableCamera } = useTrainingSettings()
const { startHandTracking, stopHandTracking } = useHandTracking()

const videoClasses = computed(() => {
  return [
    'w-full',
    'h-full',
    'object-cover',
    { '-scale-x-100': mirrorCamera.value },
  ]
})

watchEffect(() => {
  if (stream.value && videoEl.value) {
    videoEl.value.srcObject = stream.value
  }
})

const startTraining = async () => {
  await requestPermissions()
  if (hasPermissions.value) {
    isTraining.value = true
  }
}

const stopTraining = () => {
  stopStream()
  stopHandTracking()
  isTraining.value = false
  showSettings.value = false
}

const handlePermissionRequest = async () => {
    await requestPermissions();
    if (hasPermissions.value) {
        isTraining.value = true;
    }
};

const startDrawing = () => {
  startHandTracking(videoEl.value, canvasEl.value, stream.value)
}
</script>

<template>
  <div class="max-w-4xl mx-auto">
    <TrainingSettings v-if="showSettings" @close="showSettings = false" />

    <div class="mb-8 text-center">
      <h1 class="text-3xl font-bold text-white mb-2">Training Center</h1>
      <p class="text-slate-400">Master your sign language gestures with real-time feedback</p>
    </div>

    <!-- Permissions Denied -->
    <div v-if="error" class="text-center mt-12">
        <BaseCard class="max-w-md mx-auto">
            <h3 class="text-xl font-bold text-red-400 mb-2">Permissions Required</h3>
            <p class="text-slate-400 mb-4">
                Camera and microphone access is required for training. Please grant permissions in your browser settings.
            </p>
            <p class="text-xs text-slate-500">Error: {{ error.name }} - {{ error.message }}</p>
            <BaseBtn @click="handlePermissionRequest" class="mt-4" :disabled="isRequesting">
                {{ isRequesting ? 'Retrying...' : 'Retry' }}
            </BaseBtn>
        </BaseCard>
    </div>

    <!-- Active Training Interface -->
    <div v-else-if="isTraining && hasPermissions" class="flex flex-col items-center">
      <div class="w-full aspect-video bg-black rounded-2xl border border-slate-700 relative overflow-hidden shadow-2xl">
         <div v-if="!enableCamera" class="absolute inset-0 flex items-center justify-center text-slate-500 bg-black">
            Camera is disabled
         </div>
         <video ref="videoEl" autoplay playsinline muted :class="videoClasses"></video>
         <canvas ref="canvasEl" class="absolute inset-0 w-full h-full"></canvas>
         <div class="absolute bottom-6 left-6 right-6 flex justify-between items-end">
             <div class="bg-black/60 backdrop-blur px-4 py-2 rounded-lg border border-white/10">
                 <div class="text-xs text-slate-400">Detected Gesture</div>
                 <div class="text-2xl font-bold text-white">Waiting...</div>
             </div>
             <div class="bg-black/60 backdrop-blur px-4 py-2 rounded-lg border border-white/10">
                 <div class="text-xs text-slate-400">Confidence</div>
                 <div class="text-2xl font-bold text-slate-400">--%</div>
             </div>
         </div>
      </div>

      <div class="flex gap-4 mt-8">
        <BaseBtn variant="danger" @click="stopTraining">End Session</BaseBtn>
        <BaseBtn variant="secondary" @click="showSettings = true">Settings</BaseBtn>
        <BaseBtn @click="startDrawing">Start Drawing</BaseBtn>
      </div>
    </div>

    <!-- Initial State -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-8 mt-12">
      <!-- Quick Start -->
      <BaseCard class="group hover:border-indigo-500/50 transition-colors cursor-pointer" @click="startTraining">
        <div class="h-48 bg-slate-800/50 rounded-lg mb-6 flex items-center justify-center text-slate-600 group-hover:text-indigo-500 transition-colors">
            <span class="text-5xl">▶</span>
        </div>
        <h3 class="text-xl font-bold text-white mb-2">Free Practice</h3>
        <p class="text-slate-400 text-sm mb-6">Practice any gesture freely with real-time analysis and feedback loop.</p>
        <BaseBtn class="w-full" :disabled="isRequesting">
          {{ isRequesting ? 'Requesting...' : 'Start Session' }}
        </BaseBtn>
      </BaseCard>

      <!-- Guided Lesson -->
      <BaseCard class="group opacity-50 cursor-not-allowed">
        <div class="h-48 bg-slate-800/50 rounded-lg mb-6 flex items-center justify-center text-slate-600 group-hover:text-emerald-500 transition-colors">
            <span class="text-5xl">★</span>
        </div>
        <h3 class="text-xl font-bold text-white mb-2">Guided Lessons</h3>
        <p class="text-slate-400 text-sm mb-6">Step-by-step curriculum to learn basics to advanced signs.</p>
        <BaseBtn variant="secondary" class="w-full" disabled>Start Lesson 1</BaseBtn>
      </BaseCard>
    </div>
  </div>
</template>
