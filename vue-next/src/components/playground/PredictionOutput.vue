<script setup>
import { ref } from 'vue'
import { usePlaygroundStore } from '@/stores/playgroundStore'
import BaseBtn from '@/components/base/BaseBtn.vue'
import Dialog from 'primevue/dialog'
import api from '@/services/api'
import { useToast } from 'primevue/usetoast'

const store = usePlaygroundStore()
const toast = useToast()

const feedbackSent = ref(false)
const showCorrectionDialog = ref(false)
const correctedLabel = ref('')
const isSubmittingFeedback = ref(false)

const submitFeedback = async (correct, trueLabel = null) => {
  if (!store.prediction || !store.activeModel || feedbackSent.value) return
  
  isSubmittingFeedback.value = true
  try {
    const payload = {
      model_id: store.activeModel.id,
      predicted_label: store.prediction.label,
      true_label: trueLabel || (correct ? store.prediction.label : 'unknown'),
      confidence: store.prediction.confidence,
    }
    await api.modelFeedback.submit(payload)
    feedbackSent.value = true
    toast.add({ severity: 'success', summary: 'Feedback Recorded', detail: 'Thank you!', life: 3000 })
    showCorrectionDialog.value = false
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Feedback Failed', detail: 'Could not record feedback.' })
  } finally {
    isSubmittingFeedback.value = false
  }
}

const openCorrectionDialog = () => {
  correctedLabel.value = ''
  showCorrectionDialog.value = true
}
</script>

<template>
  <div class="mt-4 rounded-lg border border-slate-800 bg-slate-950/40 p-3 text-sm">
    <div class="flex items-center justify-between mb-2">
       <p class="text-slate-400">Final Prediction</p>
       <span v-if="store.isFusionMode" class="text-[10px] bg-teal-500/20 text-teal-400 px-2 py-0.5 rounded font-bold uppercase">Weighted Fusion</span>
    </div>

    <div v-if="store.prediction" class="flex items-end justify-between">
       <div>
          <p class="text-2xl font-bold text-white">
            {{ store.prediction.label }}
          </p>
          <p class="text-xs text-slate-500 mt-1">
            Confidence: {{ (store.prediction.confidence * 100).toFixed(2) }}% | {{ store.prediction.note }}
          </p>
       </div>
       <div v-if="store.prediction.top3" class="text-right">
          <p class="text-[10px] text-slate-500 uppercase font-bold mb-1">Top Alternatives</p>
          <div class="flex flex-col gap-1">
             <div v-for="alt in store.prediction.top3.slice(1)" :key="alt.label" class="text-[11px] text-slate-400">
                {{ alt.label }} ({{ (alt.confidence * 100).toFixed(1) }}%)
             </div>
          </div>
       </div>
    </div>
    <p v-else class="text-slate-500 mt-1">Ready to predict...</p>

    <!-- Feedback UI -->
    <div v-if="store.prediction && store.prediction.label !== 'Waiting...' && store.prediction.label !== 'error'" class="mt-4 pt-3 border-t border-slate-800/50 flex items-center justify-between">
       <span class="text-[10px] text-slate-500 uppercase font-bold tracking-widest">Was this correct?</span>
       <div class="flex gap-2">
          <template v-if="!feedbackSent">
            <button 
              @click="submitFeedback(true)"
              class="flex items-center gap-1.5 px-2 py-1 rounded bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 text-xs font-semibold transition-colors"
            >
              Correct
            </button>
            <button 
              @click="openCorrectionDialog"
              class="flex items-center gap-1.5 px-2 py-1 rounded bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 text-xs font-semibold transition-colors"
            >
              Wrong
            </button>
          </template>
          <div v-else class="flex items-center gap-1.5 text-xs text-teal-400 font-medium italic opacity-80">
             Feedback saved
          </div>
       </div>
    </div>

    <Dialog v-model:visible="showCorrectionDialog" modal header="Correct Prediction" :style="{ width: '25rem' }">
      <div class="space-y-4 py-2">
        <p class="text-sm text-slate-400">
          What was the actual gesture?
        </p>
        <div class="space-y-2">
          <label class="text-xs font-bold text-slate-500 uppercase">Select True Gesture</label>
          <select v-model="correctedLabel" class="w-full bg-slate-900 text-white rounded border border-slate-700 px-3 py-2 outline-none">
            <option value="" disabled>-- Select Gesture --</option>
            <option v-for="l in store.activeModel?.metadata?.labels || []" :key="l" :value="l">{{ l }}</option>
            <option value="Unknown">Other / Not in list</option>
          </select>
        </div>
        <div class="flex justify-end gap-2 pt-2">
          <BaseBtn variant="secondary" @click="showCorrectionDialog = false">Cancel</BaseBtn>
          <BaseBtn variant="primary" :disabled="!correctedLabel || isSubmittingFeedback" @click="submitFeedback(false, correctedLabel)">
            {{ isSubmittingFeedback ? 'Submitting...' : 'Submit' }}
          </BaseBtn>
        </div>
      </div>
    </Dialog>
  </div>
</template>
