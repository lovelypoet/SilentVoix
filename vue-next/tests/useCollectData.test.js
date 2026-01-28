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

    it('should update gesture name when called multiple times', () => {
      collectData.startCollecting('hello')
      collectData.startCollecting('thanks')
      expect(collectData.currentGestureName.value).toBe('thanks')
    })
  })

  describe('stopCollecting()', () => {
    it('should set isCollecting to false', () => {
      collectData.startCollecting('hello')
      collectData.stopCollecting()
      expect(collectData.isCollecting.value).toBe(false)
    })

    it('should not clear gesture name', () => {
      collectData.startCollecting('hello')
      collectData.stopCollecting()
      expect(collectData.currentGestureName.value).toBe('hello')
    })

    it('should not clear collected landmarks', () => {
      collectData.startCollecting('hello')
      collectData.addLandmark(createMockLandmarks(), 'Right')
      collectData.stopCollecting()
      expect(collectData.collectedLandmarks.value.length).toBe(1)
    })
  })

  describe('addLandmark()', () => {
    it('should add landmark when collecting', () => {
      collectData.startCollecting('hello')
      const landmarks = createMockLandmarks()
      collectData.addLandmark(landmarks, 'Right')
      
      expect(collectData.collectedLandmarks.value.length).toBe(1)
    })

    it('should not add landmark when not collecting', () => {
      const landmarks = createMockLandmarks()
      collectData.addLandmark(landmarks, 'Right')
      
      expect(collectData.collectedLandmarks.value.length).toBe(0)
    })

    it('should store correct data structure', () => {
      collectData.startCollecting('hello')
      const landmarks = createMockLandmarks()
      collectData.addLandmark(landmarks, 'Right')
      
      const frame = collectData.collectedLandmarks.value[0]
      expect(frame).toHaveProperty('gesture', 'hello')
      expect(frame).toHaveProperty('timestamp')
      expect(frame).toHaveProperty('handedness', 'Right')
      expect(frame).toHaveProperty('landmarks')
      expect(frame.landmarks).toEqual(landmarks)
    })

    it('should store timestamp as number', () => {
      collectData.startCollecting('hello')
      collectData.addLandmark(createMockLandmarks(), 'Right')
      
      const frame = collectData.collectedLandmarks.value[0]
      expect(typeof frame.timestamp).toBe('number')
      expect(frame.timestamp).toBeGreaterThan(0)
    })


    it('should handle Left handedness', () => {
      collectData.startCollecting('hello')
      collectData.addLandmark(createMockLandmarks(), 'Left')
      
      const frame = collectData.collectedLandmarks.value[0]
      expect(frame.handedness).toBe('Left')
    })

    it('should add multiple landmarks sequentially', () => {
      collectData.startCollecting('hello')
      collectData.addLandmark(createMockLandmarks(), 'Right')
      collectData.addLandmark(createMockLandmarks(), 'Right')
      collectData.addLandmark(createMockLandmarks(), 'Left')
      
      expect(collectData.collectedLandmarks.value.length).toBe(3)
    })

    it('should store exactly 21 landmarks', () => {
      collectData.startCollecting('hello')
      const landmarks = createMockLandmarks()
      collectData.addLandmark(landmarks, 'Right')
      
      expect(collectData.collectedLandmarks.value[0].landmarks.length).toBe(21)
    })
  })

  describe('convertToCSV()', () => {
    it('should return CSV with correct header', () => {
      const csv = collectData.convertToCSV()
      const lines = csv.split('\n')
      const header = lines[0]
      
      expect(header).toContain('gesture,timestamp,handedness')
      expect(header).toContain('x0,y0,z0')
      expect(header).toContain('x20,y20,z20')
    })

    it('should have 66 columns in header', () => {
      const csv = collectData.convertToCSV()
      const header = csv.split('\n')[0]
      const columns = header.split(',')
      
      // 3 metadata + 21 landmarks * 3 coords = 66
      expect(columns.length).toBe(66)
    })

    it('should return only header when no data collected', () => {
      const csv = collectData.convertToCSV()
      const lines = csv.split('\n').filter(line => line.length > 0)
      
      expect(lines.length).toBe(1) // Only header
    })

    it('should include data rows when landmarks collected', () => {
      collectData.startCollecting('hello')
      collectData.addLandmark(createMockLandmarks(), 'Right')
      collectData.addLandmark(createMockLandmarks(), 'Right')
      
      const csv = collectData.convertToCSV()
      const lines = csv.split('\n').filter(line => line.length > 0)
      
      expect(lines.length).toBe(3) // Header + 2 data rows
    })

    it('should format data row correctly', () => {
      collectData.startCollecting('hello')
      const landmarks = createMockLandmarks()
      collectData.addLandmark(landmarks, 'Right')
      
      const csv = collectData.convertToCSV()
      const lines = csv.split('\n')
      const dataRow = lines[1]
      const values = dataRow.split(',')
      
      expect(values[0]).toBe('hello') // gesture
      expect(values[2]).toBe('Right') // handedness
      expect(values.length).toBe(66) // Total columns
    })

    it('should include all landmark coordinates', () => {
      collectData.startCollecting('hello')
      const landmarks = createMockLandmarks()
      collectData.addLandmark(landmarks, 'Right')
      
      const csv = collectData.convertToCSV()
      const lines = csv.split('\n')
      const dataRow = lines[1]
      const values = dataRow.split(',')
      
      // Check first landmark (x0, y0, z0)
      expect(values[3]).toBe(landmarks[0].x.toString())
      expect(values[4]).toBe(landmarks[0].y.toString())
      expect(values[5]).toBe(landmarks[0].z.toString())
      
      // Check last landmark (x20, y20, z20)
      expect(values[63]).toBe(landmarks[20].x.toString())
      expect(values[64]).toBe(landmarks[20].y.toString())
      expect(values[65]).toBe(landmarks[20].z.toString())
    })

    it('should handle multiple gestures', () => {
      collectData.startCollecting('hello')
      collectData.addLandmark(createMockLandmarks(), 'Right')
      collectData.stopCollecting()
      
      collectData.startCollecting('thanks')
      collectData.addLandmark(createMockLandmarks(), 'Left')
      
      const csv = collectData.convertToCSV()
      const lines = csv.split('\n')
      
      expect(lines[1]).toContain('hello')
      expect(lines[2]).toContain('thanks')
    })
  })

  describe('downloadCSV()', () => {
    // Mock DOM APIs
    beforeEach(() => {
      // Mock Blob
      global.Blob = vi.fn((content, options) => ({
        content,
        options
      }))
      
      // Mock URL.createObjectURL and revokeObjectURL
      global.URL.createObjectURL = vi.fn(() => 'blob:mock-url')
      global.URL.revokeObjectURL = vi.fn()
      
      // Mock document.createElement and click
      const mockAnchor = {
        href: '',
        download: '',
        click: vi.fn()
      }
      vi.spyOn(document, 'createElement').mockReturnValue(mockAnchor)
      
      // Mock console.log
      vi.spyOn(console, 'log').mockImplementation(() => {})
    })

    it('should create a Blob with CSV content', () => {
      collectData.startCollecting('hello')
      collectData.addLandmark(createMockLandmarks(), 'Right')
      collectData.downloadCSV()
      
      expect(global.Blob).toHaveBeenCalled()
      expect(global.Blob.mock.calls[0][1]).toEqual({ type: 'text/csv' })
    })

    it('should create download link with correct filename', () => {
      collectData.startCollecting('hello')
      collectData.addLandmark(createMockLandmarks(), 'Right')
      collectData.downloadCSV()
      
      const mockAnchor = document.createElement('a')
      expect(mockAnchor.download).toContain('landmarks_hello_')
      expect(mockAnchor.download).toContain('.csv')
    })

    it('should use "data" as filename when gesture name is empty', () => {
      collectData.downloadCSV()
      
      const mockAnchor = document.createElement('a')
      expect(mockAnchor.download).toContain('landmarks_data_')
    })

    it('should trigger click on anchor element', () => {
      collectData.startCollecting('hello')
      collectData.addLandmark(createMockLandmarks(), 'Right')
      collectData.downloadCSV()
      
      const mockAnchor = document.createElement('a')
      expect(mockAnchor.click).toHaveBeenCalled()
    })

    it('should revoke object URL after download', () => {
      collectData.downloadCSV()
      expect(global.URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-url')
    })

    it('should log download confirmation', () => {
      collectData.startCollecting('hello')
      collectData.addLandmark(createMockLandmarks(), 'Right')
      collectData.downloadCSV()
      
      expect(console.log).toHaveBeenCalled()
    })
  })

  describe('clearData()', () => {
    it('should clear all collected landmarks', () => {
      collectData.startCollecting('hello')
      collectData.addLandmark(createMockLandmarks(), 'Right')
      collectData.addLandmark(createMockLandmarks(), 'Right')
      
      collectData.clearData()
      
      expect(collectData.collectedLandmarks.value).toEqual([])
    })

    it('should not affect other state', () => {
      collectData.startCollecting('hello')
      collectData.addLandmark(createMockLandmarks(), 'Right')
      
      collectData.clearData()
      
      expect(collectData.isCollecting.value).toBe(true)
      expect(collectData.currentGestureName.value).toBe('hello')
    })

    it('should work when already empty', () => {
      collectData.clearData()
      expect(collectData.collectedLandmarks.value).toEqual([])
    })
  })

  describe('Edge Cases', () => {
    it('should handle very long gesture names', () => {
      const longName = 'a'.repeat(1000)
      collectData.startCollecting(longName)
      
      expect(collectData.currentGestureName.value).toBe(longName)
    })

    it('should handle special characters in gesture name', () => {
      collectData.startCollecting('hello@#$%^&*()')
      collectData.addLandmark(createMockLandmarks(), 'Right')
      
      const csv = collectData.convertToCSV()
      expect(csv).toContain('hello@#$%^&*()')
    })

    it('should handle collecting many frames (performance)', () => {
      collectData.startCollecting('hello')
      
      // Add 1000 frames
      for (let i = 0; i < 1000; i++) {
        collectData.addLandmark(createMockLandmarks(), 'Right')
      }
      
      expect(collectData.collectedLandmarks.value.length).toBe(1000)
      
      // Should still generate valid CSV
      const csv = collectData.convertToCSV()
      const lines = csv.split('\n').filter(line => line.length > 0)
      expect(lines.length).toBe(1001) // Header + 1000 rows
    })

    it('should handle landmarks with zero values', () => {
      collectData.startCollecting('hello')
      const zeroLandmarks = Array.from({ length: 21 }, () => ({
        x: 0,
        y: 0,
        z: 0
      }))
      collectData.addLandmark(zeroLandmarks, 'Right')
      
      const csv = collectData.convertToCSV()
      expect(csv).toContain(',0,0,0')
    })

    it('should handle landmarks with negative values', () => {
      collectData.startCollecting('hello')
      const negativeLandmarks = Array.from({ length: 21 }, () => ({
        x: -0.5,
        y: -0.3,
        z: -0.1
      }))
      collectData.addLandmark(negativeLandmarks, 'Right')
      
      const csv = collectData.convertToCSV()
      expect(csv).toContain('-0.5,-0.3,-0.1')
    })
  })

  describe('Workflow Tests', () => {
    it('should support complete data collection workflow', () => {
      // Start collecting
      collectData.startCollecting('hello')
      expect(collectData.isCollecting.value).toBe(true)
      
      // Add some frames
      for (let i = 0; i < 5; i++) {
        collectData.addLandmark(createMockLandmarks(), 'Right')
      }
      expect(collectData.collectedLandmarks.value.length).toBe(5)
      
      // Stop collecting
      collectData.stopCollecting()
      expect(collectData.isCollecting.value).toBe(false)
      
      // Generate CSV
      const csv = collectData.convertToCSV()
      expect(csv).toBeTruthy()
      
      // Clear for next gesture
      collectData.clearData()
      expect(collectData.collectedLandmarks.value.length).toBe(0)
    })

    it('should support collecting multiple gestures sequentially', () => {
      // Gesture 1
      collectData.startCollecting('hello')
      collectData.addLandmark(createMockLandmarks(), 'Right')
      collectData.stopCollecting()
      
      // Gesture 2
      collectData.startCollecting('thanks')
      collectData.addLandmark(createMockLandmarks(), 'Left')
      collectData.stopCollecting()
      
      // Both should be in CSV
      const csv = collectData.convertToCSV()
      expect(csv).toContain('hello')
      expect(csv).toContain('thanks')
      expect(collectData.collectedLandmarks.value.length).toBe(2)
    })

    it('should support collecting, clearing, and collecting again', () => {
      // First collection
      collectData.startCollecting('hello')
      collectData.addLandmark(createMockLandmarks(), 'Right')
      collectData.clearData()
      
      // Second collection
      collectData.startCollecting('thanks')
      collectData.addLandmark(createMockLandmarks(), 'Right')
      
      // Only second gesture should remain
      const csv = collectData.convertToCSV()
      expect(csv).not.toContain('hello')
      expect(csv).toContain('thanks')
      expect(collectData.collectedLandmarks.value.length).toBe(1)
    })
  })
})