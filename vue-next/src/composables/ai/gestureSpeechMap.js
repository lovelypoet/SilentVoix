/*
 * Temporary MediaPipe Gesture Recognizer test feature - centralized
 * gesture -> spoken text mapping. See docs/mediapipe_gesture_tts_test.md
 * for the wider context; this file is intentionally just data + one lookup
 * function so it stays trivial to test and to delete once the test is done.
 */
export const GESTURE_SPEECH_MAP = {
  Thumb_Up: 'Tốt',
  Thumb_Down: 'Không',
  Open_Palm: 'Xin chào',
  Victory: 'Chiến thắng',
  ILoveYou: 'Tôi yêu bạn',
  Closed_Fist: 'Nắm tay',
  Pointing_Up: 'Chỉ lên'
}

// MediaPipe's own "no confident gesture" category - never has spoken text.
export const NONE_GESTURE = 'None'

/**
 * @param {string|null|undefined} gestureName MediaPipe categoryName, e.g. "Thumb_Up".
 * @returns {string|null} The Vietnamese phrase to speak, or null when the
 *   gesture isn't mapped (including "None" and unrecognized categories).
 */
export function gestureToText(gestureName) {
  if (!gestureName || gestureName === NONE_GESTURE) return null
  return GESTURE_SPEECH_MAP[gestureName] || null
}
