import { ref, watch } from 'vue'
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

  const expectedFeatureDim = () => {
    const dim = Number(store.activeModel?.metadata?.input_spec?.feature_dim || 0)
    if (dim > 0) return dim
    const inputDim = Number(store.activeModel?.input_dim || 0)
    if (inputDim === 63 || inputDim === 126) return inputDim
    return 63
  }

  const expectedSequenceLength = () => {
    const raw = Number(store.activeModel?.metadata?.input_spec?.sequence_length || 0)
    return Number.isFinite(raw) && raw > 1 ? raw : 1
  }

  const buildFrameVector = (results) => {
    const hands = Array.isArray(results?.landmarks) ? results.landmarks : []
    const firstHand = flattenHand63(hands[0] || [])
    const secondHand = flattenHand63(hands[1] || [])
    const featureDim = expectedFeatureDim()

    if (featureDim >= 126) {
      return [...firstHand, ...secondHand].slice(0, featureDim)
    }
    return firstHand.slice(0, featureDim)
  }

  const buildCvPayload = (results) => {
    const vector = buildFrameVector(results)
    const sequenceLength = expectedSequenceLength()

    if (sequenceLength > 1) {
      cvFrameBuffer.value.push(vector)
      if (cvFrameBuffer.value.length > sequenceLength) {
        cvFrameBuffer.value = cvFrameBuffer.value.slice(-sequenceLength)
      }
      return {
        sequence: [...cvFrameBuffer.value]
      }
    }

    return { cv_values: vector }
  }

  const predictCv = async (results) => {
    if (!store.activeModel || isPredicting.value) return
    const sequenceLength = expectedSequenceLength()
    if (sequenceLength > 1) {
      const vector = buildFrameVector(results)
      cvFrameBuffer.value.push(vector)
      if (cvFrameBuffer.value.length > sequenceLength) {
        cvFrameBuffer.value = cvFrameBuffer.value.slice(-sequenceLength)
      }
      if (cvFrameBuffer.value.length < sequenceLength) {
        return
      }
    }
    isPredicting.value = true
    try {
      const payload = sequenceLength > 1
        ? { sequence: [...cvFrameBuffer.value] }
        : buildCvPayload(results)
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

  watch(() => store.activeModel?.id, () => {
    cvFrameBuffer.value = []
  })

  return {
    isPredicting,
    predictCv,
    predictSensor
  }
}
