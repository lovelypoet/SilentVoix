<script setup>
import { ref, onMounted } from 'vue'
import { usePlaygroundStore } from '@/stores/playgroundStore'
import BaseBtn from '@/components/base/BaseBtn.vue'
import api from '@/services/api'

const store = usePlaygroundStore()
const isSwitching = ref(false)
const selectedId = ref('')
const error = ref('')

const loadModels = async () => {
  try {
    const res = await api.modelLibrary.listModels()
    store.savedModels = Array.isArray(res?.models) ? res.models : []
    
    const activeRes = await api.modelLibrary.getActiveModel()
    store.activeModel = activeRes?.model || null
    selectedId.value = store.activeModel?.id || ''
  } catch (e) {
    error.value = 'Failed to load models.'
  }
}

const activateModel = async () => {
  if (!selectedId.value) return
  isSwitching.value = true
  error.value = ''
  try {
    await api.modelLibrary.activateModel(selectedId.id)
    const activeRes = await api.modelLibrary.getActiveModel()
    store.activeModel = activeRes?.model || null
  } catch (e) {
    error.value = e?.response?.data?.detail || 'Failed to activate model.'
  } finally {
    isSwitching.value = false
  }
}

onMounted(loadModels)
</script>

<template>
  <div class="space-y-4">
    <div v-if="!store.isFusionMode && !store.isEarlyFusionMode">
      <label class="text-sm text-slate-300">
        Switch Classifier
        <div class="mt-1 flex flex-col gap-2 md:flex-row">
          <select v-model="selectedId" class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white">
            <option value="">Select a classifier...</option>
            <option v-for="model in store.savedModels.filter(m => m.metadata?.model_family !== 'yolo-pose')" :key="model.id" :value="model.id">
              {{ model.display_name || model.id }} | {{ model.metadata?.export_format || '--' }}
            </option>
          </select>
          <BaseBtn variant="secondary" :disabled="isSwitching || !selectedId" @click="activateModel">
            {{ isSwitching ? 'Activating...' : 'Activate' }}
          </BaseBtn>
        </div>
      </label>
    </div>

    <div v-if="error" class="p-3 rounded bg-rose-400/10 text-rose-300 border border-rose-400/20 text-sm italic">
      {{ error }}
    </div>
  </div>
</template>
