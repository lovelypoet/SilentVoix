import { ref } from 'vue'

let speechTimer = null
let currentUtterance = null

export function useTTS() {
  const speaking = ref(false)
  const spokenHistory = ref([])
  const debounceMs = ref(600)

  function speak(text, conf = 0) {
    if (!window.speechSynthesis) return

    if (speechTimer) clearTimeout(speechTimer)

    if (currentUtterance) {
      window.speechSynthesis.cancel()
      currentUtterance = null
    }

    speechTimer = setTimeout(() => {
      speechTimer = null
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.rate = 0.9
      utterance.pitch = 1.0
      utterance.volume = 1.0

      utterance.onstart = () => { speaking.value = true }
      utterance.onend = () => {
        speaking.value = false
        currentUtterance = null
      }
      utterance.onerror = () => {
        speaking.value = false
        currentUtterance = null
      }

      currentUtterance = utterance
      window.speechSynthesis.speak(utterance)

      spokenHistory.value.unshift({ text, conf, time: Date.now() })
      if (spokenHistory.value.length > 50) {
        spokenHistory.value = spokenHistory.value.slice(0, 50)
      }
    }, debounceMs.value)
  }

  function cancel() {
    if (speechTimer) {
      clearTimeout(speechTimer)
      speechTimer = null
    }
    if (currentUtterance) {
      window.speechSynthesis.cancel()
      currentUtterance = null
    }
    speaking.value = false
  }

  function stressTest(words, count = 20) {
    let i = 0
    const interval = setInterval(() => {
      if (i >= count) { clearInterval(interval); return }
      const word = words[i % words.length]
      speak(word, 0.7 + Math.random() * 0.25)
      i++
    }, 300 + Math.random() * 400)
    return () => clearInterval(interval)
  }

  return { speak, cancel, stressTest, speaking, spokenHistory, debounceMs }
}
