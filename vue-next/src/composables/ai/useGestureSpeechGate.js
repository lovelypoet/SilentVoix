import { NONE_GESTURE } from './gestureSpeechMap'

/*
 * Decides WHEN a recognized gesture is allowed to trigger speech, separate
 * from WHAT it says (gestureSpeechMap.js). GestureRecognizer reports on
 * every camera frame, so without gating a held gesture would speak dozens
 * of times a second. Pure and DOM-free (an explicit `now` is passed in
 * rather than read from Date.now() internally) so it can be unit tested
 * without mocking timers or the browser.
 *
 * Rules (see PR description / task spec for the worked example):
 *  - below `confidenceThreshold`, or the "None" category -> never speak
 *  - a candidate must hold for `stableFrames` consecutive evaluations
 *    before it counts, to ignore single-frame flicker
 *  - holding the same gesture never re-triggers speech, no matter how long
 *  - a genuinely different gesture may speak, but only once `cooldownMs`
 *    has passed since the last utterance, so rapid A/B flicker can't spam
 */
const DEFAULT_OPTIONS = {
  confidenceThreshold: 0.65,
  cooldownMs: 1300,
  stableFrames: 3,
  ignoredGestures: [NONE_GESTURE, '']
}

export function createGestureSpeechGate(options = {}) {
  const opts = { ...DEFAULT_OPTIONS, ...options }

  // -Infinity, not 0: `now` may legitimately be 0 (a test, or performance.now()
  // shortly after page load), and the very first eligible utterance must
  // never be blocked by "not enough time has passed since last speech".
  let lastSpokenGesture = null
  let lastSpokenAt = -Infinity
  let pendingGesture = null
  let pendingCount = 0

  const reset = () => {
    lastSpokenGesture = null
    lastSpokenAt = -Infinity
    pendingGesture = null
    pendingCount = 0
  }

  /**
   * @param {string|null|undefined} gestureName
   * @param {number} confidence 0..1
   * @param {number} now ms timestamp (Date.now() or performance.now(), just be consistent)
   * @returns {string|null} the gesture name to speak this tick, or null
   */
  const evaluate = (gestureName, confidence, now = Date.now()) => {
    const score = Number(confidence) || 0
    const isRecognized = Boolean(gestureName)
      && !opts.ignoredGestures.includes(gestureName)
      && score >= opts.confidenceThreshold

    if (!isRecognized) {
      pendingGesture = null
      pendingCount = 0
      return null
    }

    pendingCount = pendingGesture === gestureName ? pendingCount + 1 : 1
    pendingGesture = gestureName

    if (pendingCount < opts.stableFrames) return null
    if (gestureName === lastSpokenGesture) return null
    if (now - lastSpokenAt < opts.cooldownMs) return null

    lastSpokenGesture = gestureName
    lastSpokenAt = now
    return gestureName
  }

  return { evaluate, reset }
}
