import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const usePlaygroundStore = defineStore('playground', () => {
  // --- Modality State ---
  const isFusionMode = ref(false)
  const isEarlyFusionMode = ref(false)
  const useIntegratedMode = ref(false)
  const useHybridIntegrated = ref(true)

  // --- Active Model State ---
  const activeModel = ref(null)
  const savedModels = ref([])
  const activeDetectorId = ref('')

  // --- Late Fusion State ---
  const activeCvModel = ref(null)
  const activeSensorModel = ref(null)

  // --- Live Status ---
  const isLive = ref(false)
  const liveStatus = ref('Camera idle.')

  // --- Predictions (Final Output) ---
  const prediction = ref(null)

  // --- Computed ---
  const modelModality = computed(() => {
    const raw = String(activeModel.value?.metadata?.modality || '').trim().toLowerCase()
    if (raw === 'cv' || raw === 'sensor') return raw
    const dim = Number(activeModel.value?.input_dim || 0)
    if (dim === 11 || dim === 22) return 'sensor'
    return 'cv'
  })

  return {
    isFusionMode,
    isEarlyFusionMode,
    useIntegratedMode,
    useHybridIntegrated,
    activeModel,
    savedModels,
    activeDetectorId,
    activeCvModel,
    activeSensorModel,
    isLive,
    liveStatus,
    prediction,
    modelModality
  }
})
