import { describe, it, expect } from 'vitest'
import {
  ASL_LABELS,
  FRAME_FEATURES,
  HAND_FEATURES,
  buildFrameFeatures,
  createFrameWindow,
  labelToSpeech,
  softmax,
  topK
} from '../aslModel'

const hand = (base) => Array.from({ length: 21 }, (_, j) => ({ x: base + j, y: base + j + 0.1, z: base + j + 0.2 }))
const label = (name) => [{ categoryName: name }]

describe('ASL_LABELS', () => {
  it('matches the 77-class model_config order', () => {
    expect(ASL_LABELS).toHaveLength(77)
    expect(ASL_LABELS[0]).toBe('A')
    expect(ASL_LABELS[25]).toBe('Z')
    expect(ASL_LABELS[26]).toBe('afternoon')
    expect(ASL_LABELS[64]).toBe('thank_you')
    expect(ASL_LABELS[76]).toBe('yesterday')
  })
})

describe('buildFrameFeatures', () => {
  it('returns zeros when no hand is visible', () => {
    const { features, handCount } = buildFrameFeatures([], [])
    expect(features).toHaveLength(FRAME_FEATURES)
    expect(handCount).toBe(0)
    expect(features.every((v) => v === 0)).toBe(true)
  })

  it('puts a "Left"-labelled hand in slot 0 as raw x,y,z triples', () => {
    const { features, handCount } = buildFrameFeatures([hand(1)], [label('Left')])
    expect(handCount).toBe(1)
    expect(Array.from(features.slice(0, 6)).map((v) => +v.toFixed(3))).toEqual([1, 1.1, 1.2, 2, 2.1, 2.2])
    expect(features.slice(HAND_FEATURES).every((v) => v === 0)).toBe(true)
  })

  it('puts a "Right"-labelled hand in slot 1 regardless of result order', () => {
    const { features } = buildFrameFeatures([hand(5), hand(1)], [label('Right'), label('Left')])
    expect(features[0]).toBeCloseTo(1)
    expect(features[HAND_FEATURES]).toBeCloseTo(5)
  })

  it('does not let two same-labelled hands overwrite each other', () => {
    const { features, handCount } = buildFrameFeatures([hand(1), hand(5)], [label('Left'), label('Left')])
    expect(handCount).toBe(2)
    expect(features[0]).toBeCloseTo(1)
    expect(features[HAND_FEATURES]).toBeCloseTo(5)
  })
})

describe('createFrameWindow', () => {
  it('keeps only the most recent `capacity` frames, in order', () => {
    const win = createFrameWindow(2)
    for (const v of [1, 2, 3]) win.push(new Float32Array(FRAME_FEATURES).fill(v), v === 2 ? 0 : 1)
    expect(win.length).toBe(2)
    const flat = win.flatten()
    expect(flat).toHaveLength(2 * FRAME_FEATURES)
    expect(flat[0]).toBe(2)
    expect(flat[FRAME_FEATURES]).toBe(3)
    expect(win.recentHandFrames(2)).toBe(1)
  })

  it('shrinks on resize', () => {
    const win = createFrameWindow(5)
    for (let i = 0; i < 5; i++) win.push(new Float32Array(FRAME_FEATURES), 1)
    win.resize(3)
    expect(win.length).toBe(3)
    expect(win.capacity).toBe(3)
  })
})

describe('softmax / topK / labelToSpeech', () => {
  it('normalises logits and ranks them', () => {
    const probs = softmax([0, Math.log(3), 0])
    expect(probs.reduce((a, b) => a + b, 0)).toBeCloseTo(1)
    expect(probs[1]).toBeCloseTo(0.6)
    const [best] = topK(probs, 1, ['a', 'b', 'c'])
    expect(best).toMatchObject({ label: 'b', index: 1 })
  })

  it('speaks underscores as spaces', () => {
    expect(labelToSpeech('thank_you')).toBe('thank you')
    expect(labelToSpeech('A')).toBe('A')
    expect(labelToSpeech(null)).toBe('')
  })
})
