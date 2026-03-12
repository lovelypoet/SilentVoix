import { watch, onUnmounted } from 'vue'
import { usePlaygroundStore } from '@/stores/playgroundStore'
import { useSensorStream } from '@/composables/playground/useSensorStream'
import { useFusionLogic } from '@/composables/ai/useFusionLogic'

export function usePlaygroundEngine() {
  const store = usePlaygroundStore()
  const sensorStream = useSensorStream()
  const fusionLogic = useFusionLogic()

  // --- Coordination ---

  // 1. When modality changes, start/stop sensor stream
  watch(() => [store.isFusionMode, store.isEarlyFusionMode, store.modelModality, store.isLive], ([fusion, early, modality, isLive]) => {
    const needsSensor = fusion || early || modality === 'sensor'
    if (needsSensor && isLive) {
      sensorStream.start()
    } else {
      sensorStream.stop()
    }
  }, { immediate: true })

  // 2. Clear predictions when active model changes
  watch(() => store.activeModel?.id, () => {
    store.prediction = null
    fusionLogic.fusionPrediction.value = null
    fusionLogic.cvPrediction.value = null
    fusionLogic.sensorPrediction.value = null
  })

  const stopAll = () => {
    store.isLive = false
    sensorStream.stop()
  }

  onUnmounted(() => {
    stopAll()
  })

  return {
    store,
    sensorStream,
    fusionLogic,
    stopAll
  }
}
