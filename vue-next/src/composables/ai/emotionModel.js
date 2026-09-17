/*
 * Emotion recognition — model metadata and pure helpers.
 *
 * Model: FER+ ("emotion-ferplus-8") from the ONNX Model Zoo, a VGG-style CNN
 * trained on the FER+ re-annotation of FER2013. It runs client-side through
 * onnxruntime-web, so no TensorFlow/PyTorch sidecar is involved — see
 * `useFaceEmotion.js` for the runtime wiring.
 *
 * Contract, verified against the published model card and by running the
 * graph locally:
 *   input   'Input3'            float32 [1, 1, 64, 64]  raw 0-255 luminance
 *                                                       (the graph does its
 *                                                       own mean/scale, so do
 *                                                       NOT normalise here)
 *   output  'Plus692_Output_0'  float32 [1, 8]          logits -> softmax
 *
 * Everything in this file is side-effect free so it can be unit tested without
 * a camera, a WebGL context or a WASM runtime.
 */

/** FER+ class order. Position matters — it maps output index to meaning. */
export const EMOTION_LABELS = [
  'neutral',
  'happiness',
  'surprise',
  'sadness',
  'anger',
  'disgust',
  'fear',
  'contempt'
]

/*
 * Presentation metadata per class. This is a categorical data scale, not brand
 * chrome, so the classes that have no semantic token (surprise, disgust) carry
 * an explicit hue — the same exception `useHandTracking.js` makes for its live
 * overlay. `tokenName` wins when present so the tokened classes follow a
 * re-brand; `hex` is the canvas fallback. Tailwind's content scanner sees the
 * class strings below verbatim, which is why they are spelled out rather than
 * assembled at runtime.
 */
export const EMOTION_META = {
  neutral: { display: 'Neutral', emoji: '😐', tokenName: null, hex: '#94a3b8', barClass: 'bg-slate-400', textClass: 'text-slate-300' },
  happiness: { display: 'Happy', emoji: '😄', tokenName: 'success-400', hex: '#34d399', barClass: 'bg-success-400', textClass: 'text-success-300' },
  surprise: { display: 'Surprised', emoji: '😲', tokenName: null, hex: '#22d3ee', barClass: 'bg-cyan-400', textClass: 'text-cyan-300' },
  sadness: { display: 'Sad', emoji: '😢', tokenName: 'brand-400', hex: '#818cf8', barClass: 'bg-brand-400', textClass: 'text-brand-300' },
  anger: { display: 'Angry', emoji: '😠', tokenName: 'danger-400', hex: '#fb7185', barClass: 'bg-danger-400', textClass: 'text-danger-300' },
  disgust: { display: 'Disgusted', emoji: '🤢', tokenName: null, hex: '#a3e635', barClass: 'bg-lime-400', textClass: 'text-lime-300' },
  fear: { display: 'Fearful', emoji: '😨', tokenName: 'brand-alt-400', hex: '#a78bfa', barClass: 'bg-brand-alt-400', textClass: 'text-brand-alt-300' },
  contempt: { display: 'Contempt', emoji: '😒', tokenName: 'warning-400', hex: '#fbbf24', barClass: 'bg-warning-400', textClass: 'text-warning-300' }
}

/** Side length of the square patch the network expects. */
export const FACE_INPUT_SIZE = 64

/** Zero-probability distribution — the "no face yet" state. */
export const emptyDistribution = () =>
  Object.fromEntries(EMOTION_LABELS.map((label) => [label, 0]))

/**
 * Numerically stable softmax over the raw logits.
 *
 * @param {ArrayLike<number>} logits
 * @returns {number[]} probabilities summing to 1
 */
export function softmax(logits) {
  const values = Array.from(logits, Number)
  if (values.length === 0) return []

  const max = Math.max(...values)
  const exps = values.map((v) => Math.exp(v - max))
  const sum = exps.reduce((a, b) => a + b, 0)
  // A degenerate sum can only happen if every logit was -Infinity or NaN.
  if (!Number.isFinite(sum) || sum <= 0) return values.map(() => 1 / values.length)
  return exps.map((v) => v / sum)
}

/**
 * Turn the model's 8 logits into a `{ label: probability }` map.
 *
 * @param {ArrayLike<number>} logits
 * @returns {Record<string, number>}
 */
export function distributionFromLogits(logits) {
  const probs = softmax(logits)
  return Object.fromEntries(EMOTION_LABELS.map((label, i) => [label, probs[i] ?? 0]))
}

/**
 * Square crop around the detected face, in pixels of the source frame.
 *
 * MediaPipe returns 478 normalised landmarks; their bounding box hugs the face
 * tightly, while FER+ was trained on Viola-Jones style crops that include the
 * forehead and chin. `padScale` widens the box to match that framing.
 *
 * @param {Array<{x: number, y: number}>} landmarks normalised 0..1
 * @param {number} width  source frame width in px
 * @param {number} height source frame height in px
 * @param {number} padScale multiplier applied to the longest box side
 * @returns {{x: number, y: number, size: number}|null} integer pixel box
 */
export function faceBoxFromLandmarks(landmarks, width, height, padScale = 1.35) {
  if (!Array.isArray(landmarks) || landmarks.length === 0) return null
  if (!(width > 0) || !(height > 0)) return null

  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity

  for (const point of landmarks) {
    if (!Number.isFinite(point?.x) || !Number.isFinite(point?.y)) continue
    if (point.x < minX) minX = point.x
    if (point.x > maxX) maxX = point.x
    if (point.y < minY) minY = point.y
    if (point.y > maxY) maxY = point.y
  }
  if (!Number.isFinite(minX) || !Number.isFinite(minY)) return null

  const centreX = ((minX + maxX) / 2) * width
  const centreY = ((minY + maxY) / 2) * height
  const longest = Math.max((maxX - minX) * width, (maxY - minY) * height)

  // Never ask for more pixels than the frame has, and never fewer than one.
  const size = Math.max(1, Math.min(Math.round(longest * padScale), Math.min(width, height)))

  // Shift rather than shrink at the edges, so the crop stays square.
  const x = Math.round(Math.min(Math.max(centreX - size / 2, 0), width - size))
  const y = Math.round(Math.min(Math.max(centreY - size / 2, 0), height - size))

  return { x, y, size }
}

/**
 * RGBA patch -> the float32 luminance tensor FER+ wants.
 *
 * Values stay on the 0-255 scale (BT.601 luma) because the ONNX graph applies
 * its own subtract/divide before the first convolution.
 *
 * @param {ArrayLike<number>} rgba RGBA bytes, 4 per pixel
 * @param {number} pixelCount expected number of pixels
 * @returns {Float32Array} length `pixelCount`
 */
export function rgbaToGrayscale(rgba, pixelCount = FACE_INPUT_SIZE * FACE_INPUT_SIZE) {
  const out = new Float32Array(pixelCount)
  for (let i = 0; i < pixelCount; i++) {
    const o = i * 4
    out[i] = 0.299 * rgba[o] + 0.587 * rgba[o + 1] + 0.114 * rgba[o + 2]
  }
  return out
}

/**
 * Exponential moving average over two distributions.
 *
 * Per-frame FER+ output is jittery — a single blink flips the argmax. `inertia`
 * is the weight kept from the previous distribution: 0 disables smoothing,
 * 0.9 is very sticky.
 *
 * @param {Record<string, number>|null} previous
 * @param {Record<string, number>} next
 * @param {number} inertia 0..1
 * @returns {Record<string, number>} renormalised distribution
 */
export function smoothDistribution(previous, next, inertia = 0.6) {
  if (!previous) return { ...next }

  const weight = Math.min(Math.max(Number(inertia) || 0, 0), 0.99)
  const blended = {}
  let sum = 0

  for (const label of EMOTION_LABELS) {
    const value = (Number(previous[label]) || 0) * weight + (Number(next[label]) || 0) * (1 - weight)
    blended[label] = value
    sum += value
  }

  if (sum <= 0) return { ...next }
  for (const label of EMOTION_LABELS) blended[label] /= sum
  return blended
}

/**
 * Distribution -> descending `[{ label, probability }]`.
 *
 * @param {Record<string, number>} distribution
 * @returns {Array<{label: string, probability: number}>}
 */
export function rankDistribution(distribution) {
  return EMOTION_LABELS
    .map((label) => ({ label, probability: Number(distribution?.[label]) || 0 }))
    .sort((a, b) => b.probability - a.probability)
}

/**
 * Winning class, or `null` when nothing clears `threshold`.
 *
 * Reporting "uncertain" beats announcing a 14%-confidence emotion, which is
 * what the argmax alone would do on an ambiguous face.
 *
 * @param {Record<string, number>} distribution
 * @param {number} threshold minimum probability to accept
 * @returns {{label: string, probability: number}|null}
 */
export function dominantEmotion(distribution, threshold = 0.35) {
  const [top] = rankDistribution(distribution)
  if (!top || top.probability < threshold) return null
  return top
}

/**
 * Recorded samples -> CSV text.
 *
 * One row per inference with the full distribution, so a session can be
 * re-analysed offline the same way the gesture CSVs are.
 *
 * @param {Array<{timestamp: number, distribution: Record<string, number>, dominant: string|null, confidence: number}>} samples
 * @returns {string}
 */
export function samplesToCsv(samples) {
  const header = ['timestamp_ms', 'dominant', 'confidence', ...EMOTION_LABELS].join(',')
  const rows = (samples || []).map((sample) => {
    const cells = [
      Math.round(sample.timestamp),
      sample.dominant ?? 'uncertain',
      (Number(sample.confidence) || 0).toFixed(6),
      ...EMOTION_LABELS.map((label) => (Number(sample.distribution?.[label]) || 0).toFixed(6))
    ]
    return cells.join(',')
  })
  return [header, ...rows].join('\n') + '\n'
}
