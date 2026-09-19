import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const STORAGE_KEY = 'silentvoix_theme'

// index.html runs an inline script before Vue mounts that applies whatever
// is in localStorage (or 'dark') to <html> synchronously, so there is no
// flash of the wrong theme on reload. This store just needs to agree with
// that script's default and pick up the value it already applied.
const readStored = () => {
  if (typeof window === 'undefined') return 'dark'
  const stored = window.localStorage.getItem(STORAGE_KEY)
  return stored === 'light' ? 'light' : 'dark'
}

export const useThemeStore = defineStore('theme', () => {
  const theme = ref(readStored())

  const apply = (value) => {
    // Always set the attribute explicitly (never omit it) - PrimeVue's
    // darkModeSelector in main.js matches [data-theme="dark"], and our own
    // light overrides in style.css match [data-theme="light"], so both need
    // an explicit value rather than "absence means dark".
    document.documentElement.setAttribute('data-theme', value)
    window.localStorage.setItem(STORAGE_KEY, value)
  }

  watch(theme, apply, { immediate: true })

  const toggleTheme = () => {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }

  const setTheme = (value) => {
    theme.value = value === 'light' ? 'light' : 'dark'
  }

  return { theme, toggleTheme, setTheme }
})
