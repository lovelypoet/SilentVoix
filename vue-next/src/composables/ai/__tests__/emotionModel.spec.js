import { describe, it, expect } from 'vitest'
import {
  EMOTION_LABELS,
  EMOTION_META,
  FACE_INPUT_SIZE,
  distributionFromLogits,
  dominantEmotion,
  emptyDistribution,
  faceBoxFromLandmarks,
  rankDistribution,
  rgbaToGrayscale,
  samplesToCsv,
  smoothDistribution,
  softmax
} from '../emotionModel'

describe('emotionModel metadata', () => {
  it('keeps the FER+ class order the ONNX graph was trained with', () => {
    // The model outputs a bare 8-vector; this order is the only thing that
    // gives those numbers meaning. Verified against the model card and by
    // running the graph on smiling faces (index 1 wins).
    expect(EMOTION_LABELS).toEqual([
      'neutral',
      'happiness',
      'surprise',
      'sadness',
      'anger',
      'disgust',
      'fear',
      'contempt'
    ])
  })

  it('describes every class', () => {
    for (const label of EMOTION_LABELS) {
      expect(EMOTION_META[label]).toMatchObject({
        display: expect.any(String),
        emoji: expect.any(String),
        barClass: expect.any(String)
      })
    }
  })
})

describe('softmax', () => {
  it('normalises logits to a distribution', () => {
    const probs = softmax([1, 2, 3])
    expect(probs.reduce((a, b) => a + b, 0)).toBeCloseTo(1)
    expect(probs[2]).toBeGreaterThan(probs[0])
  })

  it('survives large logits without overflowing', () => {
    const probs = softmax([1000, 1001])
    expect(probs.every(Number.isFinite)).toBe(true)
    expect(probs[1]).toBeCloseTo(Math.E / (1 + Math.E))
  })

  it('falls back to a uniform distribution when every logit is unusable', () => {
    expect(softmax([-Infinity, -Infinity])).toEqual([0.5, 0.5])
  })
})

describe('distributionFromLogits', () => {
  it('maps output indices onto class names', () => {
    const logits = [0, 9, 0, 0, 0, 0, 0, 0]
    const distribution = distributionFromLogits(logits)
    expect(Object.keys(distribution)).toEqual(EMOTION_LABELS)
    expect(distribution.happiness).toBeGreaterThan(0.99)
  })
})

describe('faceBoxFromLandmarks', () => {
  it('returns a padded square box around the landmarks', () => {
    const box = faceBoxFromLandmarks([{ x: 0.4, y: 0.4 }, { x: 0.6, y: 0.6 }], 1000, 1000, 1.5)
    // 0.2 of 1000 = 200px wide, padded to 300px, centred on (500, 500).
    expect(box).toEqual({ x: 350, y: 350, size: 300 })
  })

  it('shifts rather than shrinks the box at a frame edge, staying square', () => {
    const box = faceBoxFromLandmarks([{ x: 0.02, y: 0.5 }, { x: 0.1, y: 0.6 }], 1000, 1000, 2)
    expect(box.x).toBe(0)
    expect(box.size).toBeGreaterThan(0)
    expect(box.x + box.size).toBeLessThanOrEqual(1000)
  })

  it('never asks for more pixels than the frame has', () => {
    const box = faceBoxFromLandmarks([{ x: 0, y: 0 }, { x: 1, y: 1 }], 640, 480, 2)
    expect(box.size).toBe(480)
    expect(box.y).toBe(0)
    expect(box.x + box.size).toBeLessThanOrEqual(640)
  })

  it('ignores non-finite landmarks instead of producing NaN geometry', () => {
    const box = faceBoxFromLandmarks(
      [{ x: 0.4, y: 0.4 }, { x: Number.NaN, y: 0.5 }, { x: 0.6, y: 0.6 }],
      1000,
      1000,
      1
    )
    expect(box).toEqual({ x: 400, y: 400, size: 200 })
  })

  it('returns null when there is nothing to crop', () => {
    expect(faceBoxFromLandmarks([], 640, 480)).toBeNull()
    expect(faceBoxFromLandmarks(null, 640, 480)).toBeNull()
    expect(faceBoxFromLandmarks([{ x: 0.5, y: 0.5 }], 0, 480)).toBeNull()
  })
})

describe('rgbaToGrayscale', () => {
  it('applies BT.601 luma and keeps the 0-255 scale the graph expects', () => {
    // FER+ normalises internally, so scaling to 0-1 here would wreck it.
    const rgba = [255, 255, 255, 255, 0, 0, 0, 255]
    const grey = rgbaToGrayscale(rgba, 2)
    expect(grey[0]).toBeCloseTo(255, 3)
    expect(grey[1]).toBeCloseTo(0, 3)
  })

  it('produces one float per pixel of the network input', () => {
    const pixels = FACE_INPUT_SIZE * FACE_INPUT_SIZE
    const grey = rgbaToGrayscale(new Uint8ClampedArray(pixels * 4))
    expect(grey).toBeInstanceOf(Float32Array)
    expect(grey).toHaveLength(pixels)
  })
})

describe('smoothDistribution', () => {
  it('passes the first frame through untouched', () => {
    const next = { ...emptyDistribution(), happiness: 1 }
    expect(smoothDistribution(null, next, 0.9)).toEqual(next)
  })

  it('blends towards the new frame and stays normalised', () => {
    const previous = { ...emptyDistribution(), neutral: 1 }
    const next = { ...emptyDistribution(), happiness: 1 }
    const blended = smoothDistribution(previous, next, 0.75)

    expect(blended.neutral).toBeCloseTo(0.75)
    expect(blended.happiness).toBeCloseTo(0.25)
    expect(Object.values(blended).reduce((a, b) => a + b, 0)).toBeCloseTo(1)
  })

  it('treats zero inertia as no smoothing at all', () => {
    const previous = { ...emptyDistribution(), neutral: 1 }
    const next = { ...emptyDistribution(), anger: 1 }
    expect(smoothDistribution(previous, next, 0).anger).toBeCloseTo(1)
  })

  it('clamps inertia below 1 so a stuck distribution cannot freeze the readout', () => {
    const previous = { ...emptyDistribution(), neutral: 1 }
    const next = { ...emptyDistribution(), anger: 1 }
    expect(smoothDistribution(previous, next, 5).anger).toBeGreaterThan(0)
  })
})

describe('rankDistribution', () => {
  it('sorts descending and covers every class', () => {
    const ranked = rankDistribution({ ...emptyDistribution(), sadness: 0.6, anger: 0.4 })
    expect(ranked).toHaveLength(EMOTION_LABELS.length)
    expect(ranked[0]).toEqual({ label: 'sadness', probability: 0.6 })
    expect(ranked[1]).toEqual({ label: 'anger', probability: 0.4 })
  })
})

describe('dominantEmotion', () => {
  it('returns the winner once it clears the threshold', () => {
    const distribution = { ...emptyDistribution(), fear: 0.7 }
    expect(dominantEmotion(distribution, 0.35)).toEqual({ label: 'fear', probability: 0.7 })
  })

  it('reports nothing rather than naming a low-confidence argmax', () => {
    const distribution = { ...emptyDistribution(), fear: 0.2, anger: 0.18 }
    expect(dominantEmotion(distribution, 0.35)).toBeNull()
  })
})

describe('samplesToCsv', () => {
  it('writes a header and one row per classification', () => {
    const csv = samplesToCsv([
      {
        timestamp: 1234.6,
        dominant: 'happiness',
        confidence: 0.9,
        distribution: { ...emptyDistribution(), happiness: 0.9 }
      }
    ])
    const [header, row] = csv.trim().split('\n')

    expect(header).toBe(`timestamp_ms,dominant,confidence,${EMOTION_LABELS.join(',')}`)
    expect(row.startsWith('1235,happiness,0.900000,')).toBe(true)
    expect(row.split(',')).toHaveLength(3 + EMOTION_LABELS.length)
  })

  it('labels an unresolved frame instead of writing an empty cell', () => {
    const csv = samplesToCsv([
      { timestamp: 0, dominant: null, confidence: 0, distribution: emptyDistribution() }
    ])
    expect(csv.trim().split('\n')[1]).toContain('uncertain')
  })

  it('still emits the header for an empty session', () => {
    expect(samplesToCsv([]).trim().split('\n')).toHaveLength(1)
  })
})
