import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'; // Import ToastService
import Aura from '@primevue/themes/aura'
import { definePreset } from '@primevue/themes'; // Import definePreset
import './style.css'
import App from './App.vue'
import router from './router'
import Lenis from 'lenis' // Import Lenis

// Define your custom preset
const MyCustomPreset = definePreset(Aura, {
    semantic: {
        focus: {
            ring: {
                color: '{teal.500}',
                width: '2px',
                style: 'solid',
                offset: '2px'
            }
        }
    }
});

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(PrimeVue, {
    theme: {
        preset: MyCustomPreset // Use your custom preset
    }
})
app.use(ToastService); // Install ToastService

// Initialize Lenis for smooth scrolling
const lenis = new Lenis({
  lerp: 0.1, // Lower values for smoother scroll
  smooth: true,
  direction: "vertical"
});

function raf(time) {
  lenis.raf(time);
  requestAnimationFrame(raf);
}

requestAnimationFrame(raf);

app.mount('#app')
