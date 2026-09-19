import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import Aura from '@primevue/themes/aura'
import { definePreset } from '@primevue/themes'
import './style.css'
import App from './App.vue'
import router from './router'
import Lenis from 'lenis'

// Aura ships an emerald `primary` palette, which would leave every PrimeVue
// component (toasts, dropdowns, sliders) green regardless of our Tailwind
// tokens. Point PrimeVue at the same --brand-* variables so the whole UI
// stays on one palette and a re-brand remains a single-file change.
const brandPalette = Object.fromEntries(
  [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950].map((shade) => [
    shade,
    `rgb(var(--brand-${shade}))`,
  ])
)

const MyCustomPreset = definePreset(Aura, {
  semantic: {
    primary: brandPalette,
    focus: {
      ring: {
        color: 'rgb(var(--brand-500))',
        width: '2px',
        style: 'solid',
        offset: '2px'
      }
    }
  }
})

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(PrimeVue, {
  theme: {
    preset: MyCustomPreset,
    // Matches the attribute src/stores/theme.js sets on <html>, so Toast /
    // Dialog / Popover switch their own light-dark tokens in sync with the
    // rest of the app instead of staying stuck on PrimeVue's light default.
    options: {
      darkModeSelector: '[data-theme="dark"]'
    }
  }
})
app.use(ToastService)

// Smooth scrolling is a decorative enhancement, so honour the OS-level
// "reduce motion" preference instead of hijacking the scroll for everyone.
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')

let lenis = null
let rafId = null

const startSmoothScroll = () => {
  if (lenis) return
  lenis = new Lenis({
    lerp: 0.1,
    smooth: true,
    direction: 'vertical'
  })

  const raf = (time) => {
    lenis.raf(time)
    rafId = requestAnimationFrame(raf)
  }
  rafId = requestAnimationFrame(raf)
}

const stopSmoothScroll = () => {
  if (rafId !== null) {
    cancelAnimationFrame(rafId)
    rafId = null
  }
  if (lenis) {
    lenis.destroy()
    lenis = null
  }
}

const syncScrollBehaviour = () => {
  if (prefersReducedMotion.matches) stopSmoothScroll()
  else startSmoothScroll()
}

syncScrollBehaviour()
prefersReducedMotion.addEventListener('change', syncScrollBehaviour)

app.mount('#app')
