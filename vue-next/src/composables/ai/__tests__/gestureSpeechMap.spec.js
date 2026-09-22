import { describe, it, expect } from 'vitest'
import { gestureToText, GESTURE_SPEECH_MAP, NONE_GESTURE } from '../gestureSpeechMap'

describe('gestureToText', () => {
  it('maps every known MediaPipe gesture category to its Vietnamese phrase', () => {
    expect(gestureToText('Thumb_Up')).toBe('Tốt')
    expect(gestureToText('Thumb_Down')).toBe('Không')
    expect(gestureToText('Open_Palm')).toBe('Xin chào')
    expect(gestureToText('Victory')).toBe('Chiến thắng')
    expect(gestureToText('ILoveYou')).toBe('Tôi yêu bạn')
    expect(gestureToText('Closed_Fist')).toBe('Nắm tay')
    expect(gestureToText('Pointing_Up')).toBe('Chỉ lên')
  })

  it('returns null for the "None" category', () => {
    expect(gestureToText(NONE_GESTURE)).toBeNull()
  })

  it('returns null for an unmapped or missing gesture', () => {
    expect(gestureToText('Some_Unknown_Gesture')).toBeNull()
    expect(gestureToText(null)).toBeNull()
    expect(gestureToText(undefined)).toBeNull()
    expect(gestureToText('')).toBeNull()
  })

  it('exposes the map itself so the UI can list supported gestures', () => {
    expect(Object.keys(GESTURE_SPEECH_MAP)).toHaveLength(7)
  })
})
