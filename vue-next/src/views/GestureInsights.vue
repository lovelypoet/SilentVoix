<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import api from '../services/api'
import { useToast } from 'primevue/usetoast'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'

const router = useRouter()
const toast = useToast()

const gestures = ref([])
const activeModelName = ref(null)
const searchQuery = ref('')
const displayDialog = ref(false)
const newGestureNameInput = ref('')
const isLoading = ref(false)

const filteredGestures = computed(() => {
  if (!searchQuery.value) return gestures.value
  const q = searchQuery.value.toLowerCase()
  return gestures.value.filter(g => g.label.toLowerCase().includes(q))
})

const recordNewGesture = () => {
  newGestureNameInput.value = ''
  displayDialog.value = true
}

const confirmRecordNewGesture = () => {
  if (newGestureNameInput.value.trim()) {
    router.push({ path: '/training', query: { newGestureName: newGestureNameInput.value.trim() } })
    toast.add({ severity: 'success', summary: 'Gesture Recording Started', detail: `Recording for "${newGestureNameInput.value.trim()}"`, life: 3000 })
    displayDialog.value = false
  } else {
    toast.add({ severity: 'error', summary: 'Input Required', detail: 'Please enter a name for the new gesture.', life: 3000 })
  }
}

const cancelRecordNewGesture = () => {
  displayDialog.value = false
  newGestureNameInput.value = ''
}

const getStatus = (count) => {
  if (count > 2000) return { label: 'ROBUST', class: 'bg-emerald-500/10 text-emerald-300' }
  if (count > 1000) return { label: 'READY', class: 'bg-teal-500/10 text-teal-300' }
  if (count > 0) return { label: 'COLLECTING', class: 'bg-amber-500/10 text-amber-300' }
  return { label: 'NO DATA', class: 'bg-slate-500/10 text-slate-400' }
}

const loadInsights = async () => {
  isLoading.value = true
  try {
    const res = await api.admin.csvLibrary.getInsights()
    gestures.value = Array.isArray(res?.data) ? res.data : []
    activeModelName.value = res?.active_model_name
  } catch (e) {
    console.error('Failed to load gesture insights:', e)
    toast.add({ severity: 'error', summary: 'Load Failed', detail: 'Could not retrieve gesture insights from CSV Library.', life: 4000 })
    gestures.value = []
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
    loadInsights()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-col sm:flex-row justify-between sm:items-center gap-4">
      <div>
        <h1 class="text-3xl font-bold text-white">Gesture Insights</h1>
        <p class="text-slate-400">Visual dataset analysis and model reliability metrics.</p>
      </div>
      <div class="flex gap-2">
        <BaseBtn variant="secondary" @click="loadInsights" :disabled="isLoading">Refresh</BaseBtn>
        <BaseBtn variant="primary" @click="recordNewGesture">Record New</BaseBtn>
      </div>
    </div>

    <!-- Active Model Context -->
    <div v-if="activeModelName" class="bg-teal-500/5 border border-teal-500/20 rounded-lg px-4 py-2 flex items-center gap-2">
       <span class="text-[10px] font-bold uppercase tracking-widest text-teal-500">Active Model:</span>
       <span class="text-sm font-medium text-teal-200">{{ activeModelName }}</span>
    </div>

    <!-- Filter/Search Bar -->
    <div class="flex gap-4">
       <input v-model="searchQuery" type="text" placeholder="Search gestures by label..." class="bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-white w-full sm:w-64 focus:border-teal-500 focus:outline-none" />
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
       <BaseCard v-for="gesture in filteredGestures" :key="gesture.label" class="group hover:border-teal-400/50 transition-all flex flex-col">
          <div class="flex justify-between items-start mb-4">
             <div :class="['px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider', getStatus(gesture.sample_count).class]">
                {{ getStatus(gesture.sample_count).label }}
             </div>
             <div class="flex gap-1">
                <div v-for="mod in gesture.modalities" :key="mod" class="w-2 h-2 rounded-full" 
                     :class="mod === 'cv' ? 'bg-blue-400' : mod === 'sensor' ? 'bg-amber-400' : 'bg-purple-400'"
                     :title="mod.toUpperCase()"></div>
             </div>
          </div>
          
          <h3 class="text-lg font-bold text-white mb-1">{{ gesture.label }}</h3>
          
          <div class="text-xs text-slate-400 space-y-1 mt-3 flex-1">
             <p class="flex justify-between"><span>Dataset Volume:</span> <span class="text-slate-200">{{ gesture.sample_count }} rows</span></p>
             <p class="flex justify-between"><span>CSV Files:</span> <span class="text-slate-200">{{ gesture.csv_count }}</span></p>
             <p class="flex justify-between">
                <span>Data Quality:</span> 
                <span :class="gesture.quality_score > 0.8 ? 'text-emerald-400' : 'text-amber-400'">
                   {{ (gesture.quality_score * 100).toFixed(0) }}%
                </span>
             </p>
             
             <p class="flex justify-between pt-2 border-t border-slate-800/50 text-[10px] uppercase font-bold text-slate-500"><span>Model Performance</span></p>
             <p class="flex justify-between">
                <span>Validation Accuracy:</span> 
                <span :class="gesture.offline_accuracy > 0.8 ? 'text-emerald-400' : 'text-amber-400'">
                   {{ (gesture.offline_accuracy * 100).toFixed(1) }}%
                </span>
             </p>
             <p class="flex justify-between">
                <span>Live Reliability:</span> 
                <span v-if="gesture.total_feedback > 0" :class="gesture.live_reliability > 0.8 ? 'text-emerald-400' : 'text-amber-400'">
                   {{ (gesture.live_reliability * 100).toFixed(1) }}%
                </span>
                <span v-else class="text-slate-600 italic">No feedback yet</span>
             </p>
          </div>

          <!-- Reliability/Progress Bar -->
          <div class="mt-4 pt-4 border-t border-slate-800/50">
             <div class="flex items-center justify-between text-[10px] text-slate-500 mb-1 uppercase font-bold">
                <span>Reliability Index</span>
                <span>{{ gesture.total_feedback > 0 ? Math.floor(gesture.live_reliability * 100) : '--' }}%</span>
             </div>
             <div class="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div 
                   class="h-full rounded-full transition-all duration-500" 
                   :class="gesture.live_reliability > 0.8 ? 'bg-emerald-500' : 'bg-amber-500'"
                   :style="{ width: (gesture.total_feedback > 0 ? (gesture.live_reliability * 100) : 0) + '%' }"
                ></div>
             </div>
          </div>

          <div class="flex gap-2 mt-6 opacity-0 group-hover:opacity-100 transition-opacity">
             <BaseBtn variant="secondary" class="flex-1 text-xs py-1.5" @click="router.push({ path: '/csv-library', query: { schema: 'all' } })">Manage CSVs</BaseBtn>
             <BaseBtn variant="secondary" class="flex-1 text-xs py-1.5" @click="router.push({ path: '/training', query: { newGestureName: gesture.label } })">Add Data</BaseBtn>
          </div>
       </BaseCard>

       <BaseCard v-if="filteredGestures.length === 0 && !isLoading" class="col-span-full p-12 text-center border-dashed border-2 border-slate-800 bg-transparent">
         <div class="flex flex-col items-center gap-3">
           <svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10 text-slate-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
           </svg>
           <p class="text-slate-500 font-medium">No gestures found in your CSV Library.</p>
           <BaseBtn variant="secondary" class="mt-2" @click="recordNewGesture">Start Recording</BaseBtn>
         </div>
       </BaseCard>
       
       <div v-if="isLoading" class="col-span-full py-20 text-center">
          <div class="inline-block animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-teal-500 mb-4"></div>
          <p class="text-slate-400">Analyzing dataset insights...</p>
       </div>
    </div>

    <Dialog v-model:visible="displayDialog" modal header="Record New Gesture" :style="{ width: 'min(30rem, 92vw)' }" @hide="cancelRecordNewGesture">
     <div class="p-fluid w-full">
  <div class="field w-full">
    <label
      for="gestureName"
      class="font-bold mb-3 block text-lg"
    >
      Gesture Name
    </label>

    <InputText
      id="gestureName"
      v-model="newGestureNameInput"
      autofocus
      class="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-3 text-slate-200 placeholder-slate-600 focus:outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-500 transition-all duration-200"
      @keyup.enter="confirmRecordNewGesture"
    />
  </div>
</div>

      <template #footer>
        <BaseBtn variant="secondary" @click="cancelRecordNewGesture">Cancel</BaseBtn>
        <BaseBtn variant="primary" @click="confirmRecordNewGesture">Record</BaseBtn>
      </template>
    </Dialog>
  </div>
</template>
