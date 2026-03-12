import { ref } from 'vue'
import api from '@/services/api'
import { usePlaygroundStore } from '@/stores/playgroundStore'

export function useInferencePipeline() {
  const store = usePlaygroundStore()
  const isPredicting = ref(false)
  const cvFrameBuffer = ref([])
  
  const flattenHand63 = (hand) => {
    if (!Array.isArray(hand) || hand.length !== 21) {
      return Array.from({ length: 63 }, () => 0)
    }
    const values = []
    for (let i = 0; i < 21; i++) {
      values.push(Number(hand[i]?.x ?? 0), Number(hand[i]?.y ?? 0), Number(hand[i]?.z ?? 0))
    }
    return values
  }

  const buildCvPayload = (results) => {
    const hands = results?.landmarks || []
    const hand = hands[0] || []
    const vector = flattenHand63(hand)
    return { cv_values: vector }
  }

  const predictCv = async (results) => {
    if (!store.activeModel || isPredicting.value) return
    isPredicting.value = true
    try {
      const payload = buildCvPayload(results)
      payload.model_id = store.activeModel.id
      const res = await api.modelLibrary.predictCv(payload)
      if (res?.prediction) {
        store.prediction = {
          ...res.prediction,
          note: `CV Inference (${res.model_name || 'Active Model'})`
        }
      }
    } catch (e) {
      console.error('CV Inference failed:', e)
    } finally {
      isPredicting.value = false
    }
  }

  const predictSensor = async (sensorValues) => {
    if (!store.activeModel || isPredicting.value) return
    isPredicting.value = true
    try {
      const res = await api.modelLibrary.predictSensor({
        sensor_values: sensorValues,
        model_id: store.activeModel.id
      })
      if (res?.prediction) {
        store.prediction = {
          ...res.prediction,
          note: `Sensor Inference (${res.model_name || 'Active Model'})`
        }
      }
    } catch (e) {
      console.error('Sensor Inference failed:', e)
    } finally {
      isPredicting.value = false
    }
  }

  return {
    isPredicting,
    predictCv,
    predictSensor
  }
}
