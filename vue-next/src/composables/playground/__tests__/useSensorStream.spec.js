import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useSensorStream } from '../useSensorStream'
import api from '@/services/api'

// Mock the API service
vi.mock('@/services/api', () => ({
  default: {
    createWebSocket: vi.fn()
  }
}))

describe('useSensorStream', () => {
  let mockWs

  beforeEach(() => {
    vi.useFakeTimers()
    mockWs = {
      send: vi.fn(),
      close: vi.fn(),
      onopen: null,
      onmessage: null,
      onerror: null,
      onclose: null
    }
    // Correctly mock the default export's createWebSocket method
    api.createWebSocket.mockReturnValue(mockWs)
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
  })

  it('initializes with default state', () => {
    const { sensorSnapshot, isConnected, isDesired } = useSensorStream()
    expect(sensorSnapshot.value.values).toEqual([])
    expect(isConnected.value).toBe(false)
    expect(isDesired.value).toBe(false)
  })

  it('starts connection and sends subscribe message', () => {
    const { start, isConnected, isDesired } = useSensorStream()
    
    start()
    expect(isDesired.value).toBe(true)
    expect(api.createWebSocket).toHaveBeenCalledWith('/ws/stream')
    
    // Simulate open
    if (mockWs.onopen) mockWs.onopen()
    expect(isConnected.value).toBe(true)
    expect(mockWs.send).toHaveBeenCalledWith(JSON.stringify({ type: 'subscribe' }))
  })

  it('updates sensor data on message', () => {
    const { start, sensorSnapshot } = useSensorStream()
    start()
    
    const mockData = {
      type: 'sensor_frame',
      values: [1, 2, 3]
    }
    
    if (mockWs.onmessage) {
      mockWs.onmessage({ data: JSON.stringify(mockData) })
    }
    
    expect(sensorSnapshot.value.values).toEqual([1, 2, 3])
    expect(sensorSnapshot.value.realSensor).toBe(true)
    expect(sensorSnapshot.value.updatedAt).not.toBeNull()
  })

  it('handles connection closure and retries if desired', () => {
    const { start, isConnected } = useSensorStream()
    start()
    
    if (mockWs.onopen) mockWs.onopen()
    expect(isConnected.value).toBe(true)
    
    // Simulate unexpected close
    if (mockWs.onclose) mockWs.onclose()
    expect(isConnected.value).toBe(false)
    
    // Should retry after 1000ms
    vi.advanceTimersByTime(1100)
    expect(api.createWebSocket).toHaveBeenCalledTimes(2)
  })

  it('stops connection and does not retry', () => {
    const { start, stop, isDesired } = useSensorStream()
    start()
    stop()
    
    expect(isDesired.value).toBe(false)
    expect(mockWs.close).toHaveBeenCalled()
    
    if (mockWs.onclose) mockWs.onclose()
    vi.advanceTimersByTime(1100)
    // Should NOT have called createWebSocket again
    expect(api.createWebSocket).toHaveBeenCalledTimes(1)
  })

  it('updates updatedAtText correctly', () => {
    const { sensorSnapshot, updatedAtText } = useSensorStream()
    
    expect(updatedAtText.value).toBe('--')
    
    const now = new Date('2026-03-12T10:00:00').getTime()
    sensorSnapshot.value.updatedAt = now
    
    expect(updatedAtText.value).not.toBe('--')
    // Note: exact format depends on locale, but it should not be '--'
  })
})
