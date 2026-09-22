import { ref } from 'vue'

/*
 * Thin wrapper around the browser's native speechSynthesis API, extracted
 * from the "Device Default" engine already used in VoiceStudio.vue
 * (src/views/VoiceStudio.vue - speakText()'s 'os' branch). Reused as-is here
 * because it needs no backend, which is exactly what a temporary
 * camera -> gesture -> spoken-audio test needs: nothing else in this flow
 * has to be running for the test to actually produce sound.
 */
export function useSpeechSynthesis() {
  const isSupported = typeof window !== 'undefined' && 'speechSynthesis' in window
  const status = ref('idle') // idle | speaking | done | unsupported | error
  const lastError = ref('')

  const speak = (text, { lang = 'vi-VN' } = {}) => {
    if (!text) return

    if (!isSupported) {
      status.value = 'unsupported'
      lastError.value = 'speechSynthesis is not supported in this browser.'
      return
    }

    window.speechSynthesis.cancel()

    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = lang

    utterance.onstart = () => {
      status.value = 'speaking'
    }
    utterance.onend = () => {
      status.value = 'done'
    }
    utterance.onerror = (event) => {
      status.value = 'error'
      lastError.value = event?.error || 'Speech playback failed.'
    }

    status.value = 'speaking'
    window.speechSynthesis.speak(utterance)
  }

  return { speak, status, lastError, isSupported }
}
