<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { PhCircleNotch, PhHandWaving } from '@phosphor-icons/vue'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import BaseInput from '../components/base/BaseInput.vue'
import BaseModal from '../components/base/BaseModal.vue'
import BaseEmptyState from '../components/base/BaseEmptyState.vue'
import BasePageHeader from '../components/base/BasePageHeader.vue'
import api from '../services/api'
import { useToast } from 'primevue/usetoast'

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
  if (count > 2000) return { label: 'ROBUST', class: 'bg-success-500/10 text-success-300' }
  if (count > 1000) return { label: 'READY', class: 'bg-brand-500/10 text-brand-300' }
  if (count > 0) return { label: 'COLLECTING', class: 'bg-warning-500/10 text-warning-300' }
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
    <BasePageHeader title="Gesture Insights" description="Visual dataset analysis and model reliability metrics.">
      <template #actions>
        <BaseBtn variant="secondary" @click="loadInsights" :disabled="isLoading">Refresh</BaseBtn>
        <BaseBtn variant="primary" @click="recordNewGesture">Record New</BaseBtn>
      </template>
    </BasePageHeader>

    <!-- Active Model Context -->
    <div v-if="activeModelName" class="bg-brand-500/5 border border-brand-500/20 rounded-lg px-4 py-2 flex items-center gap-2">
       <span class="text-[10px] font-bold uppercase tracking-widest text-brand-500">Active Model:</span>
       <span class="text-sm font-medium text-brand-200">{{ activeModelName }}</span>
    </div>

    <!-- Filter/Search Bar -->
    <div class="flex gap-4">
       <label class="w-full sm:w-64">
         <span class="sr-only">Search gestures by label</span>
         <input v-model="searchQuery" type="search" placeholder="Search gestures by label..." class="field-control" />
       </label>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
       <BaseCard v-for="gesture in filteredGestures" :key="gesture.label" class="group hover:border-brand-400/50 transition-all flex flex-col">
          <div class="flex justify-between items-start mb-4">
             <div :class="['px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider', getStatus(gesture.sample_count).class]">
                {{ getStatus(gesture.sample_count).label }}
             </div>
             <div class="flex gap-1">
                <div v-for="mod in gesture.modalities" :key="mod" class="w-2 h-2 rounded-full"
                     :class="mod === 'cv' ? 'bg-brand-400' : mod === 'sensor' ? 'bg-warning-400' : 'bg-brand-alt-400'"
                     :title="mod.toUpperCase()"
                     role="img"
                     :aria-label="`Modality: ${mod}`"></div>
             </div>
          </div>
          
          <h3 class="text-lg font-bold text-slate-100 mb-1">{{ gesture.label }}</h3>
          
          <div class="text-xs text-slate-400 space-y-1 mt-3 flex-1">
             <p class="flex justify-between"><span>Dataset Volume:</span> <span class="text-slate-200">{{ gesture.sample_count }} rows</span></p>
             <p class="flex justify-between"><span>CSV Files:</span> <span class="text-slate-200">{{ gesture.csv_count }}</span></p>
             <p class="flex justify-between">
                <span>Data Quality:</span> 
                <span :class="gesture.quality_score > 0.8 ? 'text-success-400' : 'text-warning-400'">
                   {{ (gesture.quality_score * 100).toFixed(0) }}%
                </span>
             </p>
             
             <p class="flex justify-between pt-2 border-t border-slate-800/50 text-[10px] uppercase font-bold text-slate-500"><span>Model Performance</span></p>
             <p class="flex justify-between">
                <span>Validation Accuracy:</span> 
                <span :class="gesture.offline_accuracy > 0.8 ? 'text-success-400' : 'text-warning-400'">
                   {{ (gesture.offline_accuracy * 100).toFixed(1) }}%
                </span>
             </p>
             <p class="flex justify-between">
                <span>Live Reliability:</span> 
                <span v-if="gesture.total_feedback > 0" :class="gesture.live_reliability > 0.8 ? 'text-success-400' : 'text-warning-400'">
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
                   :class="gesture.live_reliability > 0.8 ? 'bg-success-500' : 'bg-warning-500'"
                   :style="{ width: (gesture.total_feedback > 0 ? (gesture.live_reliability * 100) : 0) + '%' }"
                ></div>
             </div>
          </div>

          <div class="flex gap-2 mt-6 sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100 transition-opacity">
             <BaseBtn variant="secondary" class="flex-1 text-xs py-1.5" @click="router.push({ path: '/csv-library', query: { schema: 'all' } })">Manage CSVs</BaseBtn>
             <BaseBtn variant="secondary" class="flex-1 text-xs py-1.5" @click="router.push({ path: '/training', query: { newGestureName: gesture.label } })">Add Data</BaseBtn>
          </div>
       </BaseCard>

       <BaseCard v-if="filteredGestures.length === 0 && !isLoading" class="col-span-full border-2 border-dashed border-[rgb(var(--border-default))] bg-transparent">
         <BaseEmptyState
           :icon="PhHandWaving"
           title="No gestures found in your CSV Library"
           description="Record a new gesture to start building a dataset."
         >
           <BaseBtn variant="secondary" @click="recordNewGesture">Start Recording</BaseBtn>
         </BaseEmptyState>
       </BaseCard>

       <div v-if="isLoading" role="status" class="col-span-full flex flex-col items-center gap-3 py-20 text-center text-slate-400">
          <PhCircleNotch size="24" weight="bold" class="animate-spin text-brand-400" aria-hidden="true" />
          Analyzing dataset insights…
       </div>
    </div>

    <BaseModal
      :model-value="displayDialog"
      title="Record New Gesture"
      max-width="max-w-md"
      @update:model-value="(v) => !v && cancelRecordNewGesture()"
    >
      <BaseInput
        id="gestureName"
        v-model="newGestureNameInput"
        label="Gesture Name"
        placeholder="e.g. thumbs_up"
        autofocus
        @keyup.enter="confirmRecordNewGesture"
      />

      <template #footer>
        <BaseBtn variant="secondary" @click="cancelRecordNewGesture">Cancel</BaseBtn>
        <BaseBtn variant="primary" @click="confirmRecordNewGesture">Record</BaseBtn>
      </template>
    </BaseModal>
  </div>
</template>
