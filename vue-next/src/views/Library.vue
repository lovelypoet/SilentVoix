<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import api from '../services/api'
import { useToast } from 'primevue/usetoast' // Import useToast
import Dialog from 'primevue/dialog' // Import Dialog
import InputText from 'primevue/inputtext' // Import InputText

const router = useRouter()
const toast = useToast() // Initialize toast

const gestures = ref([])
const searchQuery = ref('')
const displayDialog = ref(false)
const newGestureNameInput = ref('')

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
  toast.add({ severity: 'info', summary: 'Cancelled', detail: 'Gesture recording cancelled.', life: 3000 })
}

const getStatus = (count) => {
  if (count > 1000) return { label: 'COMPLETE', class: 'bg-emerald-500/10 text-emerald-300' }
  if (count > 500) return { label: 'SUFFICIENT', class: 'bg-teal-500/10 text-teal-300' }
  return { label: 'COLLECTING', class: 'bg-amber-500/10 text-amber-300' }
}

const formatDate = (val) => {
  if (!val) return 'Never'
  const d = new Date(val)
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

const loadGestures = async () => {
  try {
    const res = await api.gestures.getSummary()
    gestures.value = Array.isArray(res?.data) ? res.data : []
  } catch (e) {
    console.error('Failed to load gestures:', e)
    gestures.value = []
  }
}

onMounted(() => {
    loadGestures()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-col sm:flex-row justify-between sm:items-center gap-4">
      <div>
        <h1 class="text-3xl font-bold text-white">Gesture Library</h1>
        <p class="text-slate-400">View and manage your learned signs</p>
      </div>
      <BaseBtn variant="primary" @click="recordNewGesture">Record New</BaseBtn>
    </div>

    <!-- Filter/Search Bar -->
    <div class="flex gap-4">
       <input v-model="searchQuery" type="text" placeholder="Search gestures by label..." class="bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-white w-full sm:w-64 focus:border-teal-500 focus:outline-none" />
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
       <BaseCard v-for="gesture in filteredGestures" :key="gesture.label" class="group hover:border-teal-400/50 transition-all">
          <div class="flex justify-between items-start mb-4">
             <div :class="['px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider', getStatus(gesture.sample_count).class]">
                {{ getStatus(gesture.sample_count).label }}
             </div>
             <button class="text-slate-600 hover:text-teal-300">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 256 256"><path fill="currentColor" d="M192 120a8 8 0 0 1-8 8H72a8 8 0 0 1 0-16h112a8 8 0 0 1 8 8m0 32a8 8 0 0 1-8 8H72a8 8 0 0 1 0-16h112a8 8 0 0 1 8 8m0 32a8 8 0 0 1-8 8H72a8 8 0 0 1 0-16h112a8 8 0 0 1 8 8M216 40H40a16 16 0 0 0-16 16v144a16 16 0 0 0 16 16h176a16 16 0 0 0 16-16V56a16 16 0 0 0-16-16m0 160H40V56h176Z"/></svg>
             </button>
          </div>
          
          <h3 class="text-lg font-bold text-white mb-1">{{ gesture.label }}</h3>
          <div class="text-xs text-slate-400 space-y-1 mt-3">
             <p class="flex justify-between"><span>Samples:</span> <span class="text-slate-200">{{ gesture.sample_count }}</span></p>
             <p class="flex justify-between"><span>Sessions:</span> <span class="text-slate-200">{{ gesture.session_count }}</span></p>
             <p class="flex justify-between pt-2 border-t border-slate-800/50 text-[10px] uppercase font-bold text-slate-500"><span>Model Performance (Active)</span></p>
             <p class="flex justify-between">
                <span>Validation:</span> 
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
             <div class="h-1 bg-slate-800 rounded-full overflow-hidden">
                <div 
                   class="h-full rounded-full transition-all duration-500" 
                   :class="gesture.live_reliability > 0.8 ? 'bg-emerald-500' : 'bg-amber-500'"
                   :style="{ width: (gesture.total_feedback > 0 ? (gesture.live_reliability * 100) : 0) + '%' }"
                ></div>
             </div>
          </div>

          <div class="flex gap-2 mt-6 opacity-0 group-hover:opacity-100 transition-opacity">
             <BaseBtn variant="secondary" class="flex-1 text-xs py-1.5" @click="toast.add({severity:'info', summary:'Coming Soon', detail:'Detail view for gestures is being implemented.'})">View</BaseBtn>
             <BaseBtn variant="secondary" class="flex-1 text-xs py-1.5" @click="router.push({ path: '/training', query: { newGestureName: gesture.label } })">Add Data</BaseBtn>
          </div>
       </BaseCard>

       <BaseCard v-if="filteredGestures.length === 0" class="col-span-full p-12 text-center border-dashed border-2 border-slate-800 bg-transparent">
         <div class="flex flex-col items-center gap-3">
           <svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10 text-slate-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
           </svg>
           <p class="text-slate-500 font-medium">No gestures found in your library.</p>
           <BaseBtn variant="secondary" class="mt-2" @click="recordNewGesture">Start Recording</BaseBtn>
         </div>
       </BaseCard>
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
