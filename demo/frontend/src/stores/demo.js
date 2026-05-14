import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const STABILITY_WINDOW = 5
const STABILITY_THRESHOLD = 3

export const useDemoStore = defineStore('demo', () => {
  const connected = ref(false)
  const predictions = ref([])
  const currentPrediction = ref(null)
  const anomaly = ref(null)
  const lastLatency = ref(0)
  const mode = ref('live')
  const stressTesting = ref(false)

  const predictionWindow = ref([])
  const stableGesture = ref('—')
  const stableConfidence = ref(0)
  const stableLatency = ref(0)

  const latestGesture = computed(() => currentPrediction.value?.gesture || '—')
  const latestConfidence = computed(() => currentPrediction.value?.confidence || 0)

  function addPrediction(pred) {
    currentPrediction.value = pred

    predictions.value.push({ ...pred, id: Date.now() + Math.random() })
    if (predictions.value.length > 200) {
      predictions.value = predictions.value.slice(-200)
    }

    if (pred.anomaly) {
      anomaly.value = pred.anomaly
    }
    lastLatency.value = pred.latency_ms || 0

    if (pred.gesture && pred.confidence > 0.3) {
      predictionWindow.value.push(pred.gesture)
      if (predictionWindow.value.length > STABILITY_WINDOW) {
        predictionWindow.value.shift()
      }

      if (predictionWindow.value.length < STABILITY_THRESHOLD) {
        const g = pred.gesture
        if (g !== stableGesture.value) {
          stableGesture.value = g
          stableConfidence.value = pred.confidence
          stableLatency.value = pred.latency_ms || 0
        }
      } else {
        const counts = {}
        for (const g of predictionWindow.value) {
          counts[g] = (counts[g] || 0) + 1
        }
        let best = ''
        let bestCount = 0
        for (const [g, c] of Object.entries(counts)) {
          if (c > bestCount) { best = g; bestCount = c }
        }
        if (bestCount >= STABILITY_THRESHOLD && best !== stableGesture.value) {
          stableGesture.value = best
          stableConfidence.value = pred.confidence
          stableLatency.value = pred.latency_ms || 0
        }
      }
    }
  }

  function setConnected(val) {
    connected.value = val
  }

  function setStressTesting(val) {
    stressTesting.value = val
  }

  function clearAnomaly() {
    anomaly.value = null
  }

  function reset() {
    predictions.value = []
    currentPrediction.value = null
    anomaly.value = null
    lastLatency.value = 0
    predictionWindow.value = []
    stableGesture.value = '—'
    stableConfidence.value = 0
    stableLatency.value = 0
  }

  return {
    connected, predictions, currentPrediction, anomaly, lastLatency,
    mode, stressTesting, latestGesture, latestConfidence,
    stableGesture, stableConfidence, stableLatency,
    addPrediction, setConnected, setStressTesting, clearAnomaly, reset,
  }
})
