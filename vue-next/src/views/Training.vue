<script setup>
import { ref, watch } from 'vue'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import { useMediaPermissions } from '../composables/useMediaPermissions.js'

const isTraining = ref(false)
const videoEl = ref(null)
const { hasPermissions, isRequesting, error, stream, requestPermissions, stopStream } = useMediaPermissions()

watch(stream, (newStream) => {
  if (newStream && videoEl.value) {
    videoEl.value.srcObject = newStream
  }
})

const startTraining = async () => {
  if (!hasPermissions.value) {
    await requestPermissions()
  }
  if (hasPermissions.value) {
    isTraining.value = true
  }
}

const stopTraining = () => {
  isTraining.value = false
  stopStream()
}
</script>

<template>
  <div class="max-w-4xl mx-auto">
    <div class="mb-8 text-center">
      <h1 class="text-3xl font-bold text-white mb-2">Training Center</h1>
      <p class="text-slate-400">Master your sign language gestures with real-time feedback</p>
    </div>

    <div v-if="!isTraining" class="grid grid-cols-1 md:grid-cols-2 gap-8 mt-12">
      <!-- Quick Start -->
      <BaseCard class="group hover:border-indigo-500/50 transition-colors cursor-pointer" @click="startTraining">
        <div class="h-48 bg-slate-800/50 rounded-lg mb-6 flex items-center justify-center text-slate-600 group-hover:text-indigo-500 transition-colors">
            <span class="text-5xl">▶</span>
        </div>
        <h3 class="text-xl font-bold text-white mb-2">Free Practice</h3>
        <p class="text-slate-400 text-sm mb-6">Practice any gesture freely with real-time analysis and feedback loop.</p>
        <BaseBtn class="w-full" :disabled="isRequesting">
          {{ isRequesting ? 'Requesting...' : (hasPermissions ? 'Start Session' : 'Start Session') }}
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

    <!-- Active Training Interface -->
    <div v-else-if="isTraining && hasPermissions" class="flex flex-col items-center">
      <div class="w-full aspect-video bg-black rounded-2xl border border-slate-700 relative overflow-hidden shadow-2xl">
         <video ref="videoEl" autoplay playsinline class="w-full h-full object-cover"></video>
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
        <BaseBtn variant="secondary" disabled>Settings</BaseBtn>
      </div>
    </div>

    <!-- Permissions Denied -->
    <div v-if="error" class="text-center mt-12">
        <BaseCard class="max-w-md mx-auto">
            <h3 class="text-xl font-bold text-red-400 mb-2">Permissions Required</h3>
            <p class="text-slate-400 mb-4">
                Camera and microphone access is required for training. Please grant permissions in your browser settings.
            </p>
            <p class="text-xs text-slate-500">Error: {{ error.name }} - {{ error.message }}</p>
            <BaseBtn @click="requestPermissions" class="mt-4" :disabled="isRequesting">
                {{ isRequesting ? 'Retrying...' : 'Retry' }}
            </BaseBtn>
        </BaseCard>
    </div>
  </div>
</template>
