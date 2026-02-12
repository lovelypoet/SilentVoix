import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useCollectData } from '../src/composables/useCollectData'

function mockHand(offset = 0) {
  return Array.from({ length: 21 }, (_, i) => ({
    x: i + offset,
    y: i + 1,
    z: i + 2
  }))
}

describe('useCollectData (JS)', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('does nothing when not collecting', () => {
    const { addLandmark, collectedLandmarks } = useCollectData()

    addLandmark([], [])
    expect(collectedLandmarks.value.length).toBe(0)
  })

  it('startCollecting sets gesture and flag', () => {
    const { startCollecting, isCollecting, currentGestureName } =
      useCollectData()

    startCollecting('wave')

    expect(isCollecting.value).toBe(true)
    expect(currentGestureName.value).toBe('wave')
  })

  it('stopCollecting disables collecting', () => {
    const { startCollecting, stopCollecting, isCollecting } = useCollectData()

    startCollecting('x')
    stopCollecting()

    expect(isCollecting.value).toBe(false)
  })

  it('adds zero-filled frame when no landmarks exist', () => {
    const { startCollecting, addLandmark, collectedLandmarks } =
      useCollectData()

    startCollecting('idle')
    addLandmark([], [], { frame_id: 0, timestamp_ms: 123 })

    expect(collectedLandmarks.value.length).toBe(1)

    const frame = collectedLandmarks.value[0]
    expect(frame.L_exist).toBe(0)
    expect(frame.R_exist).toBe(0)
    expect(frame.features.length).toBe(126)

    frame.features.forEach(v => {
      expect(v).toBe(0)
    })
  })

  it('handles left + right hands correctly', () => {
    const { startCollecting, addLandmark, collectedLandmarks } =
      useCollectData()

    startCollecting('both')

    addLandmark(
      [mockHand(0), mockHand(100)],
      [
        [{ categoryName: 'Left' }],
        [{ categoryName: 'Right' }]
      ],
      { frame_id: 1, timestamp_ms: 1000 }
    )

    const frame = collectedLandmarks.value[0]

    expect(frame.L_exist).toBe(1)
    expect(frame.R_exist).toBe(1)
    expect(frame.features.length).toBe(126)

    // first left landmark
    expect(frame.features[0]).toBe(0)
    expect(frame.features[1]).toBe(1)
    expect(frame.features[2]).toBe(2)

    // first right landmark starts at index 63
    expect(frame.features[63]).toBe(100)
  })

  it('pads missing hand with zeros', () => {
    const { startCollecting, addLandmark, collectedLandmarks } =
      useCollectData()

    startCollecting('left-only')

    addLandmark(
      [mockHand(0)],
      [[{ categoryName: 'Left' }]],
      { frame_id: 2, timestamp_ms: 2000 }
    )

    const frame = collectedLandmarks.value[0]

    expect(frame.L_exist).toBe(1)
    expect(frame.R_exist).toBe(0)

    const rightPart = frame.features.slice(63)
    rightPart.forEach(v => {
      expect(v).toBe(0)
    })
  })

  it('produces valid CSV output', () => {
    const { startCollecting, addLandmark, convertToCSV } =
      useCollectData()

    startCollecting('csv')

    addLandmark([], [], { frame_id: 0, timestamp_ms: 1 })
    addLandmark([], [], { frame_id: 1, timestamp_ms: 2 })

    const csv = convertToCSV()
    const lines = csv.trim().split('\n')

    expect(lines.length).toBe(3)
    expect(lines[0].includes('frame_id')).toBe(true)
    expect(lines[1].includes('csv')).toBe(true)
  })

  it('clearData wipes all frames', () => {
    const { startCollecting, addLandmark, clearData, collectedLandmarks } =
      useCollectData()

    startCollecting('wipe')
    addLandmark([], [])

    expect(collectedLandmarks.value.length).toBe(1)

    clearData()
    expect(collectedLandmarks.value.length).toBe(0)
  })

  it('downloadCSV triggers anchor click safely', () => {
    const { startCollecting, addLandmark, downloadCSV } =
      useCollectData()

    global.URL.createObjectURL = vi.fn(() => 'blob:url')
    global.URL.revokeObjectURL = vi.fn()

    const click = vi.fn()
    vi.spyOn(document, 'createElement').mockImplementation(() => ({
      set href(_) {},
      set download(_) {},
      click
    }))

    startCollecting('dl')
    addLandmark([], [])

    expect(() => downloadCSV()).not.toThrow()
    expect(click).toHaveBeenCalled()
  })
})
