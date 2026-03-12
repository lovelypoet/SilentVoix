import { describe, it, expect } from 'vitest'
import { useFusionLogic } from '../useFusionLogic'

describe('useFusionLogic', () => {
  it('calculates late fusion winner correctly based on weights', () => {
    const { calculateLateFusion } = useFusionLogic()
    
    const cvRes = {
      probabilities: { 'Hello': 0.8, 'ThankYou': 0.2 }
    }
    const sensorRes = {
      probabilities: { 'Hello': 0.1, 'ThankYou': 0.9 }
    }
    
    // Case 1: High vision weight (glove weight 0.2)
    const visionHeavy = calculateLateFusion(cvRes, sensorRes, 0.2)
    expect(visionHeavy.label).toBe('Hello')
    // (0.8 * 0.8) + (0.1 * 0.2) = 0.64 + 0.02 = 0.66
    expect(visionHeavy.confidence).toBeCloseTo(0.66)
    
    // Case 2: High glove weight (glove weight 0.8)
    const gloveHeavy = calculateLateFusion(cvRes, sensorRes, 0.8)
    expect(gloveHeavy.label).toBe('ThankYou')
    // (0.2 * 0.2) + (0.9 * 0.8) = 0.04 + 0.72 = 0.76
    expect(gloveHeavy.confidence).toBeCloseTo(0.76)
  })

  it('handles mismatching labels in probabilities', () => {
    const { calculateLateFusion } = useFusionLogic()
    
    const cvRes = {
      probabilities: { 'A': 1.0 }
    }
    const sensorRes = {
      probabilities: { 'B': 1.0 }
    }
    
    const equalWeight = calculateLateFusion(cvRes, sensorRes, 0.5)
    expect(equalWeight.probabilities['A']).toBe(0.5)
    expect(equalWeight.probabilities['B']).toBe(0.5)
  })
  
  it('provides top 3 alternatives', () => {
    const { calculateLateFusion } = useFusionLogic()
    
    const cvRes = {
      probabilities: { 'A': 0.6, 'B': 0.3, 'C': 0.1 }
    }
    const sensorRes = {
      probabilities: { 'A': 0.6, 'B': 0.3, 'C': 0.1 }
    }
    
    const result = calculateLateFusion(cvRes, sensorRes, 0.5)
    expect(result.top3.length).toBe(3)
    expect(result.top3[0].label).toBe('A')
    expect(result.top3[1].label).toBe('B')
    expect(result.top3[2].label).toBe('C')
  })
})
