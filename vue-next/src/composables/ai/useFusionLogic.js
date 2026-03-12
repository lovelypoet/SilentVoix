import { ref } from 'vue'

export function useFusionLogic() {
  const fusionPrediction = ref(null)
  const cvPrediction = ref(null)
  const sensorPrediction = ref(null)
  const isFusionPredicting = ref(false)
  const isEarlyFusionPredicting = ref(false)
  const earlyFusionSource = ref('both')
  const earlyFusionSessionId = ref('realtime-playground')
  const gloveWeight = ref(0.8)

  /**
   * Late Fusion: Weighted average of probabilities from two models.
   */
  const calculateLateFusion = (cvRes, sensorRes, weight) => {
    const cvProbs = cvRes?.probabilities || {}
    const sensorProbs = sensorRes?.probabilities || {}

    const labels = Array.from(new Set([...Object.keys(cvProbs), ...Object.keys(sensorProbs)]))
    const fusedProbs = {}

    labels.forEach(label => {
      const vProb = Number(cvProbs[label] || 0)
      const sProb = Number(sensorProbs[label] || 0)
      fusedProbs[label] = (vProb * (1 - weight)) + (sProb * weight)
    })

    const sorted = Object.entries(fusedProbs).sort((a, b) => b[1] - a[1])
    const winner = sorted[0]

    return {
      label: winner ? winner[0] : 'Unknown',
      confidence: winner ? winner[1] : 0,
      top3: sorted.slice(0, 3).map(([label, conf]) => ({ label, confidence: conf })),
      probabilities: fusedProbs
    }
  }

  return {
    fusionPrediction,
    cvPrediction,
    sensorPrediction,
    isFusionPredicting,
    isEarlyFusionPredicting,
    earlyFusionSource,
    earlyFusionSessionId,
    gloveWeight,
    calculateLateFusion
  }
}
