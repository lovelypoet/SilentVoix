import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useCollectData } from '../src/composables/useCollectData.js'

describe('useCollectData (JS)', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-01-01T00:00:00Z'))

    // Mock browser APIs
    global.URL.createObjectURL = vi.fn(() => 'blob:url')
    global.URL.revokeObjectURL = vi.fn()
    global.Blob = vi.fn(() => ({}))

    const click = vi.fn()
    vi.spyOn(document, 'createElement').mockReturnValue({
      click,
      set href(_) {},
      set download(_) {}
    })
  })

  it('starts and stops collecting', () => {
    const {
      isCollecting,
      startCollecting,
      stopCollecting,
      currentGestureName
    } = useCollectData()

    startCollecting('wave')
    expect(isCollecting.value).toBe(true)
    expect(currentGestureName.value).toBe('wave')

    stopCollecting()
    expect(isCollecting.value).toBe(false)
  })

  it('does nothing when not collecting', () => {
    const { collectedLandmarks, addLandmark } = useCollectData()

    addLandmark([], [])
    expect(collectedLandmarks.value.length).toBe(0)
  })

  it('adds zero-filled frame when no hands detected', () => {
    const { collectedLandmarks, startCollecting, addLandmark } =
      useCollectData()

    startCollecting('idle')

    addLandmark([], [], { frame_id: 0, timestamp_ms: 1000 })

    const frame = collectedLandmarks.value[0]

    expect(collectedLandmarks.value.length).toBe(1)
    expect(frame.L_exist).toBe(0)
    expect(frame.R_exist).toBe(0)
    expect(frame.features.length).toBe(126)
    expect(frame.features.every(v => v === 0)).toBe(true)
  })

  it('correctly maps left and right hands', () => {
    const { collectedLandmarks, startCollecting, addLandmark } =
      useCollectData()

    startCollecting('gesture')

    const leftHand = Array.from({ length: 21 }, (_, i) => ({
      x: i,
      y: i + 0.1,
      z: i + 0.2
    }))

    const rightHand = Array.from({ length: 21 }, (_, i) => ({
      x: i + 100,
      y: i + 100.1,
      z: i + 100.2
    }))

    addLandmark(
      [leftHand, rightHand],
      [
        [{ categoryName: 'Left' }],
        [{ categoryName: 'Right' }]
      ],
      { frame_id: 1, timestamp_ms: 2000 }
    )

    const frame = collectedLandmarks.value[0]

    expect(frame.L_exist).toBe(1)
    expect(frame.R_exist).toBe(1)
    expect(frame.features.length).toBe(126)

    // spot checks
    expect(frame.features[0]).toBe(0)        // L_x0
    expect(frame.features[63]).toBe(100)     // R_x0
  })

  it('converts frames to CSV', () => {
    const {
      startCollecting,
      addLandmark,
      convertToCSV
    } = useCollectData()

    startCollecting('test')

    addLandmark([], [], { frame_id: 0, timestamp_ms: 123 })

    const csv = convertToCSV()
    const lines = csv.trim().split('\n')

    expect(lines.length).toBe(2)
    expect(lines[0]).toContain('frame_id,timestamp_ms,gesture')
    expect(lines[1]).toContain('0,123,test,0,0')
  })

  it('clears collected data', () => {
    const {
      collectedLandmarks,
      startCollecting,
      addLandmark,
      clearData
    } = useCollectData()

    startCollecting('wipe')
    addLandmark([], [])

    expect(collectedLandmarks.value.length).toBe(1)

    clearData()
    expect(collectedLandmarks.value.length).toBe(0)
  })
})
