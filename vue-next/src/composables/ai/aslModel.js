/*
 * Pure logic for the ASL sign recognizer (namratha2412/asl-improved-recognition,
 * exported to ONNX by scripts/export_asl_model.py). DOM- and ORT-free so it can
 * be unit tested; the camera/runtime wiring lives in useAslRecognizer.js.
 *
 * Input contract, reverse-engineered because the model repo ships no
 * preprocessing code. Each frame packs 126 floats:
 *   [hand slot 0: 21 landmarks x (x, y, z)] + [hand slot 1: same], a missing hand = zeros
 *   raw MediaPipe normalized image coordinates (NOT wrist-relative)
 *   slot 0 = the hand MediaPipe labels "Left" on the raw, unmirrored frame
 * Evidence: we fed real ASL-alphabet landmarks through the checkpoint's first
 * conv layer and compared the result with its BatchNorm running mean/var. Raw
 * coordinates in this slot order fit best, while wrist-relative coordinates
 * fit worse than an all-zero input.
 *
 * Behaviour worth knowing: the model is very sensitive to sequence length.
 * Short windows lean towards letters, long windows towards words, which is
 * why the window length is exposed as a setting.
 */

export const ASL_LABELS = [
  'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S',
  'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
  'afternoon', 'angry', 'bad', 'book', 'come', 'drink', 'eat', 'evening', 'family', 'feel',
  'food', 'friend', 'go', 'good', 'goodbye', 'happy', 'have', 'hear', 'hello', 'help', 'home',
  'know', 'learn', 'love', 'morning', 'need', 'night', 'no', 'please', 'read', 'sad', 'school',
  'see', 'sign', 'sorry', 'speak', 'student', 'teacher', 'thank_you', 'think', 'time', 'tired',
  'today', 'tomorrow', 'understand', 'want', 'water', 'work', 'write', 'yes', 'yesterday'
]

export const LANDMARKS_PER_HAND = 21
export const HAND_FEATURES = LANDMARKS_PER_HAND * 3
export const FRAME_FEATURES = HAND_FEATURES * 2

/**
 * Pack one HandLandmarker result into the model's 126-float frame.
 * @param {Array<Array<{x:number,y:number,z:number}>>} landmarks result.landmarks
 * @param {Array<Array<{categoryName:string}>>} handedness result.handedness
 * @returns {{ features: Float32Array, handCount: number }}
 */
export function buildFrameFeatures(landmarks = [], handedness = []) {
  const features = new Float32Array(FRAME_FEATURES)
  const used = [false, false]
  let handCount = 0

  for (let i = 0; i < landmarks.length && handCount < 2; i++) {
    const points = landmarks[i]
    if (!points || points.length < LANDMARKS_PER_HAND) continue
    const label = handedness?.[i]?.[0]?.categoryName
    let slot = label === 'Right' ? 1 : 0
    // Two hands with the same label (it happens mid-transition): the second
    // one takes whichever slot is still free instead of overwriting.
    if (used[slot]) slot = 1 - slot
    if (used[slot]) continue
    used[slot] = true
    handCount++

    const offset = slot * HAND_FEATURES
    for (let j = 0; j < LANDMARKS_PER_HAND; j++) {
      const p = points[j]
      features[offset + j * 3] = p.x
      features[offset + j * 3 + 1] = p.y
      features[offset + j * 3 + 2] = p.z
    }
  }
  return { features, handCount }
}

/** Fixed-length sliding window of frames, flattened for the ORT tensor. */
export function createFrameWindow(capacity) {
  let frames = []
  let hands = []

  return {
    push(features, handCount) {
      frames.push(features)
      hands.push(handCount)
      while (frames.length > capacity) {
        frames.shift()
        hands.shift()
      }
    },
    resize(next) {
      capacity = next
      while (frames.length > capacity) {
        frames.shift()
        hands.shift()
      }
    },
    clear() {
      frames = []
      hands = []
    },
    get length() {
      return frames.length
    },
    get capacity() {
      return capacity
    },
    /** How many of the most recent `n` frames had at least one hand. */
    recentHandFrames(n) {
      return hands.slice(-n).filter((c) => c > 0).length
    },
    /** @returns {Float32Array} length = frames * FRAME_FEATURES */
    flatten() {
      const out = new Float32Array(frames.length * FRAME_FEATURES)
      frames.forEach((f, i) => out.set(f, i * FRAME_FEATURES))
      return out
    }
  }
}

export function softmax(logits) {
  const values = Array.from(logits)
  const max = Math.max(...values)
  const exps = values.map((v) => Math.exp(v - max))
  const sum = exps.reduce((a, b) => a + b, 0)
  return exps.map((e) => e / sum)
}

/** @returns {Array<{label:string, index:number, prob:number}>} highest first */
export function topK(probs, k = 5, labels = ASL_LABELS) {
  return Array.from(probs, (prob, index) => ({ label: labels[index] ?? `#${index}`, index, prob }))
    .sort((a, b) => b.prob - a.prob)
    .slice(0, k)
}

/** "thank_you" -> "thank you"; letters are spoken as-is. */
export function labelToSpeech(label) {
  if (!label) return ''
  return String(label).replace(/_/g, ' ')
}
