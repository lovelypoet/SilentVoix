import { ref } from 'vue'

/*
 * Thin wrapper around the browser's native speechSynthesis API, extracted
 * from the "Device Default" engine already used in VoiceStudio.vue
 * (src/views/VoiceStudio.vue - speakText()'s 'os' branch). Reused as-is here
 * because it needs no backend, which is exactly what a temporary
 * camera -> gesture -> spoken-audio test needs: nothing else in this flow
 * has to be running for the test to actually produce sound.
 *
 * Two Chrome-specific reliability bugs, both well documented, showed up
 * while wiring this to MediaPipe's per-frame callback instead of a single
 * button click (VoiceStudio's usage):
 *
 *  1. Calling `speechSynthesis.cancel()` unconditionally right before
 *     `speak()` - fine on an idle queue in isolation, but when a second
 *     gesture speaks shortly after the first, cancel() races the engine's
 *     internal state and can silently drop the *new* utterance instead of
 *     just stopping the old one. Now only cancels when something is
 *     actually speaking/queued.
 *  2. `speechSynthesis.getVoices()` loads asynchronously; calling speak()
 *     before the browser has populated its voice list (very likely on the
 *     very first call after page load, which is exactly the first gesture
 *     a tester makes) is a known cause of speak() being a silent no-op -
 *     no error, no onstart, nothing. Now waits one 'voiceschanged' tick
 *     (bounded) before the first call if the list is still empty.
 */

const TAG = '[GestureTTS]'

const voicesReady = () => window.speechSynthesis.getVoices().length > 0

const waitForVoices = (timeoutMs = 1000) => new Promise((resolve) => {
  if (voicesReady()) {
    resolve()
    return
  }
  let settled = false
  const done = () => {
    if (settled) return
    settled = true
    window.speechSynthesis.removeEventListener('voiceschanged', done)
    resolve()
  }
  window.speechSynthesis.addEventListener('voiceschanged', done)
  setTimeout(done, timeoutMs)
})

export function useSpeechSynthesis() {
  const isSupported = typeof window !== 'undefined' && 'speechSynthesis' in window
  const status = ref('idle') // idle | speaking | done | unsupported | error
  const lastError = ref('')

  const speak = async (text, { lang = 'vi-VN' } = {}) => {
    if (!text) return
    console.log(`${TAG} speak() requested:`, text)

    if (!isSupported) {
      status.value = 'unsupported'
      lastError.value = 'speechSynthesis is not supported in this browser.'
      console.warn(`${TAG} speechSynthesis unsupported`)
      return
    }

    if (!voicesReady()) {
      console.log(`${TAG} voices not loaded yet, waiting...`)
      await waitForVoices()
      console.log(`${TAG} voices ready: ${window.speechSynthesis.getVoices().length}`)
    }

    // Only interrupt an utterance that's actually in flight. Calling
    // cancel() on an already-idle queue is the part that races speak().
    if (window.speechSynthesis.speaking || window.speechSynthesis.pending) {
      console.log(`${TAG} cancelling in-flight speech before speaking new text`)
      window.speechSynthesis.cancel()
    }

    // Chrome has a long-standing bug where the queue can end up paused
    // (e.g. after the tab loses focus) without anything having called
    // pause(). resume() is a harmless no-op when not paused.
    window.speechSynthesis.resume()

    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = lang

    utterance.onstart = () => {
      console.log(`${TAG} onstart:`, text)
      status.value = 'speaking'
    }
    utterance.onend = () => {
      console.log(`${TAG} onend:`, text)
      status.value = 'done'
    }
    utterance.onerror = (event) => {
      console.warn(`${TAG} onerror:`, event?.error, text)
      status.value = 'error'
      lastError.value = event?.error || 'Speech playback failed.'
    }

    status.value = 'speaking'
    console.log(`${TAG} speechSynthesis.speak() called:`, text)
    window.speechSynthesis.speak(utterance)
  }

  return { speak, status, lastError, isSupported }
}
