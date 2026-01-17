import { describe, it, expect } from 'vitest'
import { useTrainingSettings } from '../src/composables/useTrainingSettings'

describe('useTrainingSettings (unit)', () => {
  it('correct initial values', () => {
    const settings = useTrainingSettings()

    expect(settings.enableCamera.value).toBe(true)
    expect(settings.mirrorCamera.value).toBe(true)
    expect(settings.resolution.value).toBe('Medium')
    expect(settings.showLandmarks.value).toBe(true)
    expect(settings.trainingMode.value).toBe('Practice')
  })

  it('can toggle showLandmarks', () => {
    const settings = useTrainingSettings()

    settings.showLandmarks.value = false
    expect(settings.showLandmarks.value).toBe(false)

    settings.showLandmarks.value = true
    expect(settings.showLandmarks.value).toBe(true)
  })

  it('resetSettings restores defaults', () => {
    const settings = useTrainingSettings()

    settings.enableCamera.value = false
    settings.mirrorCamera.value = false
    settings.showLandmarks.value = false

    settings.resetSettings()

    expect(settings.enableCamera.value).toBe(true)
    expect(settings.mirrorCamera.value).toBe(true)
    expect(settings.showLandmarks.value).toBe(true)
  })
})
