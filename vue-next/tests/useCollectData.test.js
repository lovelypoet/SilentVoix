import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useCollectData } from '../src/composables/useCollectData'

// Mock landmarks data (21 landmarks with x, y, z)
const createMockLandmarks = () => {
  return Array.from({ length: 21 }, (_, i) => ({
    x: 0.1 + i * 0.01,
    y: 0.2 + i * 0.01,
    z: 0.3 + i * 0.01
  }))
}

// Mock handedness (MediaPipe format)
const createMockHandedness = (label) => {
  // label is 'Right' or 'Left'
  return [{
    score: 0.9,
    index: 0,
    categoryName: label,
    displayName: label
  }]
}

describe('useCollectData', () => {
  let collectData

  beforeEach(() => {
    collectData = useCollectData()
  })

  describe('Initial State', () => {
    it('should initialize with empty landmarks array', () => {
      expect(collectData.collectedLandmarks.value).toEqual([])
    })

    it('should initialize with isCollecting as false', () => {
      expect(collectData.isCollecting.value).toBe(false)
    })

    it('should initialize with empty gesture name', () => {
      expect(collectData.currentGestureName.value).toBe('')
    })
  })

  describe('startCollecting()', () => {
    it('should set isCollecting to true', () => {
      collectData.startCollecting('hello')
      expect(collectData.isCollecting.value).toBe(true)
    })

    it('should set current gesture name', () => {
      collectData.startCollecting('hello')
      expect(collectData.currentGestureName.value).toBe('hello')
    })
  })

  describe('stopCollecting()', () => {
    it('should set isCollecting to false', () => {
      collectData.startCollecting('hello')
      collectData.stopCollecting()
      expect(collectData.isCollecting.value).toBe(false)
    })
  })

  describe('addLandmark()', () => {
    it('should add landmark when collecting', () => {
      collectData.startCollecting('hello')
      const landmarks = createMockLandmarks()
      // Pass arrays as expected by the new implementation
      collectData.addLandmark([landmarks], [createMockHandedness('Right')])

      expect(collectData.collectedLandmarks.value.length).toBe(1)
    })

    it('should not add landmark when not collecting', () => {
      const landmarks = createMockLandmarks()
      collectData.addLandmark([landmarks], [createMockHandedness('Right')])

      expect(collectData.collectedLandmarks.value.length).toBe(0)
    })

    it('should store correct data structure for Right hand', () => {
      collectData.startCollecting('hello')
      const landmarks = createMockLandmarks()
      collectData.addLandmark([landmarks], [createMockHandedness('Right')])

      const frame = collectData.collectedLandmarks.value[0]
      expect(frame).toHaveProperty('gesture', 'hello')
      expect(frame).toHaveProperty('timestamp')
      expect(frame).toHaveProperty('R_exist', 1)
      expect(frame).toHaveProperty('L_exist', 0)
      expect(frame.features).toHaveLength(126) // 21 * 3 * 2

      // Right hand features are collecting at index 63 onwards (Left is 0-62)
      // Check first landmark of Right hand (x)
      expect(frame.features[63]).toBe(landmarks[0].x)
    })

    it('should store correct data structure for Left hand', () => {
      collectData.startCollecting('hello')
      const landmarks = createMockLandmarks()
      collectData.addLandmark([landmarks], [createMockHandedness('Left')])

      const frame = collectData.collectedLandmarks.value[0]
      expect(frame).toHaveProperty('L_exist', 1)
      expect(frame).toHaveProperty('R_exist', 0)

      // Left hand features are at index 0
      expect(frame.features[0]).toBe(landmarks[0].x)
    })

    it('should handle two hands', () => {
      collectData.startCollecting('both')
      const lm1 = createMockLandmarks()
      const lm2 = createMockLandmarks()
      const handednesses = [createMockHandedness('Left'), createMockHandedness('Right')]

      collectData.addLandmark([lm1, lm2], handednesses)

      const frame = collectData.collectedLandmarks.value[0]
      expect(frame.L_exist).toBe(1)
      expect(frame.R_exist).toBe(1)
    })
  })

  describe('convertToCSV()', () => {
    it('should return CSV with correct header', () => {
      const csv = collectData.convertToCSV()
      const lines = csv.split('\n')
      const header = lines[0]

      expect(header).toContain('gesture,timestamp,L_exist,R_exist')
      expect(header).toContain('L_x0,L_y0,L_z0')
      expect(header).toContain('R_x20,R_y20,R_z20')
    })
  })

  describe('downloadCSV()', () => {
    beforeEach(() => {
      global.Blob = vi.fn((content, options) => ({ content, options }))
      global.URL.createObjectURL = vi.fn(() => 'blob:mock-url')
      global.URL.revokeObjectURL = vi.fn()

      const mockAnchor = {
        href: '',
        download: '',
        click: vi.fn()
      }
      vi.spyOn(document, 'createElement').mockReturnValue(mockAnchor)
      vi.spyOn(console, 'log').mockImplementation(() => { })
    })

    it('should create a Blob with CSV content', () => {
      collectData.startCollecting('hello')
      collectData.addLandmark([createMockLandmarks()], [createMockHandedness('Right')])
      collectData.downloadCSV()

      expect(global.Blob).toHaveBeenCalled()
      expect(global.Blob.mock.calls[0][1]).toEqual({ type: 'text/csv' })
    })
  })
})