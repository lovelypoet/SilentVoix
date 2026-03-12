<script setup>
import { usePlaygroundStore } from '@/stores/playgroundStore'

const props = defineProps({
  fusionLogic: { type: Object, required: true }
})

const store = usePlaygroundStore()
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-xl text-white font-semibold">Inference Modes</h2>
        <p class="text-xs text-slate-400">Toggle between Single Model, Early Fusion, or Late Fusion pipelines.</p>
      </div>
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-2">
           <span class="text-xs font-bold uppercase tracking-widest text-slate-500">Early:</span>
           <button 
             class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none"
             :class="store.isEarlyFusionMode ? 'bg-teal-500' : 'bg-slate-700'"
             @click="store.isEarlyFusionMode = !store.isEarlyFusionMode; store.isFusionMode = false"
           >
             <span class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform" :class="store.isEarlyFusionMode ? 'translate-x-6' : 'translate-x-1'"></span>
           </button>
        </div>
        <div class="flex items-center gap-2">
           <span class="text-xs font-bold uppercase tracking-widest text-slate-500">Late:</span>
           <button 
             class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none"
             :class="store.isFusionMode ? 'bg-teal-500' : 'bg-slate-700'"
             @click="store.isFusionMode = !store.isFusionMode; store.isEarlyFusionMode = false"
           >
             <span class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform" :class="store.isFusionMode ? 'translate-x-6' : 'translate-x-1'"></span>
           </button>
        </div>
      </div>
    </div>

    <div v-if="store.isFusionMode" class="mt-4 space-y-4 animate-in fade-in slide-in-from-top-2">
       <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="space-y-1">
             <label class="text-xs font-bold text-slate-500 uppercase">Vision (CV) Model</label>
             <select v-model="store.activeCvModel" class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white text-sm">
               <option :value="null">Select CV model...</option>
               <option v-for="model in store.savedModels.filter(m => m.metadata?.modality === 'cv')" :key="model.id" :value="model">
                 {{ model.display_name || model.id }}
               </option>
             </select>
          </div>
          <div class="space-y-1">
             <label class="text-xs font-bold text-slate-500 uppercase">Glove (Sensor) Model</label>
             <select v-model="store.activeSensorModel" class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white text-sm">
               <option :value="null">Select Sensor model...</option>
               <option v-for="model in store.savedModels.filter(m => m.metadata?.modality === 'sensor')" :key="model.id" :value="model">
                 {{ model.display_name || model.id }}
               </option>
             </select>
          </div>
       </div>

       <div class="p-3 bg-slate-900 rounded-lg border border-slate-800">
          <div class="flex items-center justify-between mb-2">
             <span class="text-xs font-bold text-slate-500 uppercase">Glove vs. Vision Weight</span>
             <div class="flex gap-4">
                <span class="text-[10px] text-teal-400 font-bold uppercase tracking-widest">Vision: {{ (1 - props.fusionLogic.gloveWeight.value).toFixed(2) }}</span>
                <span class="text-[10px] text-amber-400 font-bold uppercase tracking-widest">Glove: {{ props.fusionLogic.gloveWeight.value.toFixed(2) }}</span>
             </div>
          </div>
          <input type="range" v-model.number="props.fusionLogic.gloveWeight.value" min="0" max="1" step="0.05" class="w-full accent-teal-500 bg-slate-800 h-2 rounded-lg cursor-pointer" />
       </div>
    </div>
  </div>
</template>
