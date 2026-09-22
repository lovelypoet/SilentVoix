import { describe, it, expect } from 'vitest'
import { createGestureSpeechGate } from '../useGestureSpeechGate'

// Small helper: feed the same gesture/confidence for `count` ticks, 40ms apart
// (comfortably above the default 3-frame stability requirement, comfortably
// below the cooldown), returning the LAST evaluate() result.
const feed = (gate, gesture, confidence, startTime, count = 3, stepMs = 40) => {
  let result = null
  for (let i = 0; i < count; i++) {
    result = gate.evaluate(gesture, confidence, startTime + i * stepMs)
  }
  return result
}

describe('createGestureSpeechGate', () => {
  it('ignores low-confidence detections', () => {
    const gate = createGestureSpeechGate({ confidenceThreshold: 0.65 })
    const result = feed(gate, 'Thumb_Up', 0.4, 0)
    expect(result).toBeNull()
  })

  it('ignores the "None" gesture even at high confidence', () => {
    const gate = createGestureSpeechGate()
    const result = feed(gate, 'None', 0.99, 0)
    expect(result).toBeNull()
  })

  it('requires several consecutive stable frames before speaking', () => {
    const gate = createGestureSpeechGate({ stableFrames: 3 })
    expect(gate.evaluate('Thumb_Up', 0.9, 0)).toBeNull()
    expect(gate.evaluate('Thumb_Up', 0.9, 40)).toBeNull()
    // third consecutive frame reaches the stability threshold
    expect(gate.evaluate('Thumb_Up', 0.9, 80)).toBe('Thumb_Up')
  })

  it('does not repeat speech while the same gesture is held', () => {
    const gate = createGestureSpeechGate({ stableFrames: 1, cooldownMs: 1300 })
    expect(gate.evaluate('Thumb_Up', 0.9, 0)).toBe('Thumb_Up')
    // held for a while, well past the cooldown window - still no repeat
    expect(gate.evaluate('Thumb_Up', 0.9, 500)).toBeNull()
    expect(gate.evaluate('Thumb_Up', 0.9, 2000)).toBeNull()
    expect(gate.evaluate('Thumb_Up', 0.9, 5000)).toBeNull()
  })

  it('lets a changed gesture speak once the cooldown has elapsed', () => {
    const gate = createGestureSpeechGate({ stableFrames: 1, cooldownMs: 1300 })
    expect(gate.evaluate('Thumb_Up', 0.9, 0)).toBe('Thumb_Up')
    // different gesture, but still inside the cooldown window
    expect(gate.evaluate('Open_Palm', 0.9, 500)).toBeNull()
    // same gesture, now past the cooldown
    expect(gate.evaluate('Open_Palm', 0.9, 1400)).toBe('Open_Palm')
  })

  it('matches the worked example from the task spec', () => {
    const gate = createGestureSpeechGate({ stableFrames: 1, cooldownMs: 1300 })
    // Thumb_Up -> speaks
    expect(gate.evaluate('Thumb_Up', 0.9, 0)).toBe('Thumb_Up')
    // hold Thumb_Up -> no repeated speech
    expect(gate.evaluate('Thumb_Up', 0.9, 300)).toBeNull()
    expect(gate.evaluate('Thumb_Up', 0.9, 600)).toBeNull()
    // Open_Palm -> speaks (past cooldown)
    expect(gate.evaluate('Open_Palm', 0.85, 1600)).toBe('Open_Palm')
  })

  it('resets pending stability when a different candidate interrupts the streak', () => {
    const gate = createGestureSpeechGate({ stableFrames: 3, cooldownMs: 0 })
    expect(gate.evaluate('Thumb_Up', 0.9, 0)).toBeNull()
    expect(gate.evaluate('Thumb_Up', 0.9, 40)).toBeNull()
    // a different gesture flickers in - resets the counter for Thumb_Up
    expect(gate.evaluate('Victory', 0.9, 80)).toBeNull()
    expect(gate.evaluate('Thumb_Up', 0.9, 120)).toBeNull()
    expect(gate.evaluate('Thumb_Up', 0.9, 160)).toBeNull()
    expect(gate.evaluate('Thumb_Up', 0.9, 200)).toBe('Thumb_Up')
  })

  it('reset() clears memory so a previously spoken gesture can speak again', () => {
    const gate = createGestureSpeechGate({ stableFrames: 1, cooldownMs: 0 })
    expect(gate.evaluate('Thumb_Up', 0.9, 0)).toBe('Thumb_Up')
    expect(gate.evaluate('Thumb_Up', 0.9, 40)).toBeNull()
    gate.reset()
    expect(gate.evaluate('Thumb_Up', 0.9, 80)).toBe('Thumb_Up')
  })
})
