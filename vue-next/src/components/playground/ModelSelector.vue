<script setup>
import { computed, ref, onMounted } from 'vue'
import { PhStack } from '@phosphor-icons/vue'
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
    await api.modelLibrary.activateModel(selectedId.value)
    const activeRes = await api.modelLibrary.getActiveModel()
    store.activeModel = activeRes?.model || null
  } catch (e) {
    error.value = e?.response?.data?.detail || 'Failed to activate model.'
  } finally {
    isSwitching.value = false
  }
}

onMounted(loadModels)

const activeMeta = computed(() => store.activeModel?.metadata || {})
</script>

<template>
  <div class="space-y-4">
    <div v-if="store.activeModel" class="flex items-start gap-3 rounded-lg border border-brand-400/20 bg-brand-500/5 p-3">
      <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-500/15 text-brand-400">
        <PhStack size="18" weight="bold" aria-hidden="true" />
      </span>
      <div class="min-w-0">
        <p class="text-sm font-medium text-slate-100 truncate">{{ store.activeModel.display_name || store.activeModel.id }}</p>
        <div class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-slate-400">
          <span class="uppercase tracking-wide">{{ activeMeta.export_format || '--' }}</span>
          <span class="text-slate-700">•</span>
          <span class="uppercase tracking-wide">{{ store.modelModality }}</span>
          <span v-if="activeMeta.f1 != null" class="text-slate-700">•</span>
          <span v-if="activeMeta.f1 != null">F1 {{ activeMeta.f1 }}</span>
        </div>
      </div>
    </div>
    <p v-else class="text-xs text-slate-500">No model activated yet — select one below.</p>

    <div v-if="!store.isFusionMode && !store.isEarlyFusionMode">
      <label class="field-label" for="model-selector-classifier">Switch Classifier</label>
      <div class="flex flex-col gap-2 md:flex-row">
        <select id="model-selector-classifier" v-model="selectedId" class="field-control">
          <option value="">Select a classifier...</option>
          <option v-for="model in store.savedModels.filter(m => m.metadata?.model_family !== 'yolo-pose')" :key="model.id" :value="model.id">
            {{ model.display_name || model.id }} | {{ model.metadata?.export_format || '--' }}
          </option>
        </select>
        <BaseBtn variant="secondary" :disabled="isSwitching || !selectedId" @click="activateModel">
          {{ isSwitching ? 'Activating...' : 'Activate' }}
        </BaseBtn>
      </div>
    </div>

    <div v-if="error" role="alert" class="p-3 rounded-lg bg-danger-400/10 text-danger-300 border border-danger-400/20 text-sm">
      {{ error }}
    </div>
  </div>
</template>
