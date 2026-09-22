import { ref } from 'vue'

/*
 * Thin wrapper around the browser's native speechSynthesis API, extracted
 * from the "Device Default" engine already used in VoiceStudio.vue
 * (src/views/VoiceStudio.vue - speakText()'s 'os' branch). Reused as-is here
 * because it needs no backend, which is exactly what a temporary
 * camera -> gesture -> spoken-audio test needs: nothing else in this flow
 * has to be running for the test to actually produce sound.
 *
 * Chrome-specific speechSynthesis reliability bugs found while wiring this
 * to MediaPipe's per-frame callback instead of a single button click
 * (VoiceStudio's usage), all well documented in the wild:
 *
 *  1. Calling `speechSynthesis.cancel()` unconditionally right before
 *     `speak()` - fine on an idle queue in isolation, but when a second
 *     gesture speaks shortly after the first, cancel() races the engine's
 *     internal state and can silently drop the *new* utterance instead of
 *     just stopping the old one. Only cancels when something is actually
 *     speaking/queued.
 *  2. `speechSynthesis.getVoices()` loads asynchronously; calling speak()
 *     before the browser has populated its voice list (very likely on the
 *     very first call after page load) is a known cause of speak() being a
 *     silent no-op. Waits one 'voiceschanged' tick (bounded) first if the
 *     list is still empty.
 *  3. Chrome's speech queue can get stuck - `speak()` accepted, nothing
 *     ever happens: no onstart, no onend, no onerror, forever. Reported in
 *     the wild (not reproduced in this session's sandbox, which has no
 *     real audio device) as the UI staying on "Speaking" with total
 *     silence even after a full minute. A watchdog now detects this (no
 *     onstart within START_TIMEOUT_MS) and force-resets the queue + retries
 *     once; if onstart fired but onend never does (END_TIMEOUT_MS), the
 *     watchdog forces the status back out of "speaking" so the UI can't
 *     lie about state forever even when the underlying engine is wedged.
 */

const TAG = '[GestureTTS]'
const START_TIMEOUT_MS = 1500
const END_TIMEOUT_MS = 8000

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

  let startTimer = null
  let endTimer = null
  let keepAliveTimer = null

  const clearWatchdogs = () => {
    clearTimeout(startTimer)
    clearTimeout(endTimer)
    clearInterval(keepAliveTimer)
    startTimer = null
    endTimer = null
    keepAliveTimer = null
  }

  const speakOnce = (text, lang) => new Promise((resolve) => {
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = lang
    let started = false

    utterance.onstart = () => {
      started = true
      clearTimeout(startTimer)
      console.log(`${TAG} onstart:`, text)
      status.value = 'speaking'

      // Chrome has a well-known bug where a long-running utterance gets
      // silently paused (e.g. after ~15s or a focus change). A periodic
      // pause+resume nudge keeps it alive; harmless once the utterance
      // finishes since onend clears this interval.
      keepAliveTimer = setInterval(() => {
        window.speechSynthesis.pause()
        window.speechSynthesis.resume()
      }, 4000)

      // Separate watchdog: if the engine started but never reports
      // finishing, don't let the UI claim "Speaking" forever.
      endTimer = setTimeout(() => {
        console.warn(`${TAG} onend never fired within ${END_TIMEOUT_MS}ms, forcing reset:`, text)
        clearWatchdogs()
        window.speechSynthesis.cancel()
        status.value = 'error'
        lastError.value = 'Speech playback stalled and was reset.'
        resolve(false)
      }, END_TIMEOUT_MS)
    }
    utterance.onend = () => {
      console.log(`${TAG} onend:`, text)
      clearWatchdogs()
      status.value = 'done'
      resolve(true)
    }
    utterance.onerror = (event) => {
      console.warn(`${TAG} onerror:`, event?.error, text)
      clearWatchdogs()
      status.value = 'error'
      lastError.value = event?.error || 'Speech playback failed.'
      resolve(false)
    }

    // Watchdog for the case Chrome silently drops the utterance before
    // ever starting it: nothing fires at all, not even onerror.
    startTimer = setTimeout(() => {
      if (started) return
      console.warn(`${TAG} onstart never fired within ${START_TIMEOUT_MS}ms, treating as dropped:`, text)
      clearWatchdogs()
      resolve(false)
    }, START_TIMEOUT_MS)

    window.speechSynthesis.speak(utterance)
  })

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
    window.speechSynthesis.resume()

    status.value = 'speaking'
    console.log(`${TAG} speechSynthesis.speak() called:`, text)
    const ok = await speakOnce(text, lang)

    if (!ok && status.value !== 'done') {
      // One bounded retry: fully reset the queue first, since a stuck
      // engine often needs a hard cancel() before it will accept anything
      // new. If this also fails, surface it instead of retrying forever.
      console.log(`${TAG} retrying once after a dropped/stalled utterance:`, text)
      window.speechSynthesis.cancel()
      await new Promise((r) => setTimeout(r, 150))
      status.value = 'speaking'
      const retryOk = await speakOnce(text, lang)
      if (!retryOk && status.value !== 'done') {
        status.value = 'error'
        lastError.value = lastError.value || 'Speech playback failed after retry.'
        console.warn(`${TAG} retry also failed:`, text)
      }
    }
  }

  return { speak, status, lastError, isSupported }
}
