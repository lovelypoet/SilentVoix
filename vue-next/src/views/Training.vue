<script setup>
import { ref } from 'vue'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'

const isTraining = ref(false)

const startTraining = () => {
  isTraining.value = true
}

const stopTraining = () => {
  isTraining.value = false
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
        <BaseBtn class="w-full">Start Session</BaseBtn>
      </BaseCard>

      <!-- Guided Lesson -->
      <BaseCard class="group hover:border-emerald-500/50 transition-colors cursor-pointer">
        <div class="h-48 bg-slate-800/50 rounded-lg mb-6 flex items-center justify-center text-slate-600 group-hover:text-emerald-500 transition-colors">
            <span class="text-5xl">★</span>
        </div>
        <h3 class="text-xl font-bold text-white mb-2">Guided Lessons</h3>
        <p class="text-slate-400 text-sm mb-6">Step-by-step curriculum to learn basics to advanced signs.</p>
        <BaseBtn variant="secondary" class="w-full">Start Lesson 1</BaseBtn>
      </BaseCard>
    </div>

    <!-- Active Training Interface Mockup -->
    <div v-else class="flex flex-col items-center">
      <div class="w-full aspect-video bg-black rounded-2xl border border-slate-700 relative overflow-hidden shadow-2xl">
         <div class="absolute inset-0 flex items-center justify-center text-slate-600">
            Camera Feed Placeholder
         </div>
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
        <BaseBtn variant="secondary">Settings</BaseBtn>
      </div>
    </div>
  </div>
</template>
