<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import BaseBtn from '../components/base/BaseBtn.vue'
import BaseInput from '../components/base/BaseInput.vue'
import LoginGalaxyBackground from '../components/LoginGalaxyBackground.vue'

const router = useRouter()
const authStore = useAuthStore()

const email = ref('')
const password = ref('')
const isLoading = ref(false)
const error = ref('')
const isGraphicsMenuOpen = ref(false)
const autoStatus = ref('Evaluating this device...')
const autoThreeEnabled = ref(false)
let autoEvaluationId = 0

const GRAPHICS_MODE_KEY = 'silentvoix_login_graphics_mode'
const graphicsModeOptions = ['auto', 'on', 'off']

const readStoredGraphicsMode = () => {
  if (typeof window === 'undefined') return 'auto'
  const stored = window.localStorage.getItem(GRAPHICS_MODE_KEY)
  return graphicsModeOptions.includes(stored) ? stored : 'auto'
}

const graphicsMode = ref(readStoredGraphicsMode())

const persistGraphicsMode = (mode) => {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(GRAPHICS_MODE_KEY, mode)
}

const probeFps = (durationMs = 1800) =>
  new Promise((resolve) => {
    if (typeof window === 'undefined' || typeof window.requestAnimationFrame !== 'function') {
      resolve({ fps: 0, slowFrameRatio: 1 })
      return
    }

    let frameCount = 0
    let slowFrames = 0
    let startedAt = 0
    let lastFrameAt = 0

    const tick = (timestamp) => {
      if (!startedAt) {
        startedAt = timestamp
        lastFrameAt = timestamp
      }
      frameCount += 1
      const deltaMs = timestamp - lastFrameAt
      if (deltaMs > 34) slowFrames += 1
      lastFrameAt = timestamp

      if (timestamp - startedAt >= durationMs) {
        const elapsedMs = Math.max(timestamp - startedAt, 1)
        resolve({
          fps: (frameCount * 1000) / elapsedMs,
          slowFrameRatio: frameCount ? slowFrames / frameCount : 1
        })
        return
      }
      window.requestAnimationFrame(tick)
    }

    window.requestAnimationFrame(tick)
  })

const evaluateAutoGraphicsMode = async () => {
  const currentEvaluationId = ++autoEvaluationId

  if (typeof window === 'undefined' || typeof navigator === 'undefined') {
    if (currentEvaluationId !== autoEvaluationId || graphicsMode.value !== 'auto') return
    autoThreeEnabled.value = false
    autoStatus.value = 'Auto unavailable. Using lightweight mode.'
    return
  }

  let score = 0
  const reasons = []
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ?? false
  if (reducedMotion) {
    score += 2
    reasons.push('reduced motion preference')
  }

  const memory = navigator.deviceMemory ?? null
  if (typeof memory === 'number') {
    if (memory <= 2) {
      score += 2
      reasons.push(`low memory (${memory}GB)`)
    } else if (memory <= 4) {
      score += 1
      reasons.push(`limited memory (${memory}GB)`)
    }
  }

  const cores = navigator.hardwareConcurrency ?? null
  if (typeof cores === 'number') {
    if (cores <= 2) {
      score += 2
      reasons.push(`very low CPU concurrency (${cores})`)
    } else if (cores <= 4) {
      score += 1
      reasons.push(`limited CPU concurrency (${cores})`)
    }
  }

  const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection
  if (connection?.saveData) {
    score += 2
    reasons.push('data saver enabled')
  }
  if (['slow-2g', '2g', '3g'].includes(connection?.effectiveType)) {
    score += 1
    reasons.push(`slow network (${connection.effectiveType})`)
  }

  const fpsProbe = await probeFps()
  if (currentEvaluationId !== autoEvaluationId || graphicsMode.value !== 'auto') return

  if (fpsProbe.fps < 45 || fpsProbe.slowFrameRatio > 0.2) {
    score += 2
    reasons.push(`low frame rate (${Math.round(fpsProbe.fps)} FPS)`)
  } else if (fpsProbe.fps < 54) {
    score += 1
    reasons.push(`borderline frame rate (${Math.round(fpsProbe.fps)} FPS)`)
  }

  autoThreeEnabled.value = score < 3
  if (autoThreeEnabled.value) {
    autoStatus.value = 'Auto: 3D background enabled.'
  } else if (reasons.length) {
    autoStatus.value = `Auto: lightweight mode (${reasons.join(', ')}).`
  } else {
    autoStatus.value = 'Auto: lightweight mode selected.'
  }
}

const isGalaxyEnabled = computed(() => {
  if (graphicsMode.value === 'on') return true
  if (graphicsMode.value === 'off') return false
  return autoThreeEnabled.value
})

watch(
  graphicsMode,
  async (mode) => {
    persistGraphicsMode(mode)
    if (mode === 'auto') {
      autoStatus.value = 'Evaluating this device...'
      await evaluateAutoGraphicsMode()
      return
    }
    autoEvaluationId += 1
    autoStatus.value = mode === 'on' ? 'Forced on by user.' : 'Forced off by user.'
  },
  { immediate: true }
)

const handleLogin = async () => {
  isLoading.value = true
  error.value = ''
  try {
    await authStore.login(email.value, password.value)
    router.push('/')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Login failed. Please check your credentials.'
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen login-page flex items-center justify-center p-4">
    <LoginGalaxyBackground v-if="isGalaxyEnabled" />
    <div class="graphics-settings">
      <button
        type="button"
        class="graphics-settings-trigger"
        aria-label="Open graphics settings"
        @click="isGraphicsMenuOpen = !isGraphicsMenuOpen"
      >
        <svg viewBox="0 0 24 24" fill="none" class="graphics-gear-icon" aria-hidden="true">
          <path
            d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.427 1.756 2.925 0 3.351a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.427 1.756-2.925 1.756-3.351 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.427-1.756-2.925 0-3.351a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
            stroke="currentColor"
            stroke-width="1.5"
          />
          <path d="M12 15.25a3.25 3.25 0 100-6.5 3.25 3.25 0 000 6.5z" stroke="currentColor" stroke-width="1.5" />
        </svg>
      </button>
      <div v-if="isGraphicsMenuOpen" class="graphics-settings-menu">
        <p class="graphics-settings-title">Graphics</p>
        <div class="graphics-settings-options">
          <button
            type="button"
            class="graphics-option-btn"
            :class="{ active: graphicsMode === 'auto' }"
            @click="graphicsMode = 'auto'"
          >
            Auto
          </button>
          <button
            type="button"
            class="graphics-option-btn"
            :class="{ active: graphicsMode === 'on' }"
            @click="graphicsMode = 'on'"
          >
            On
          </button>
          <button
            type="button"
            class="graphics-option-btn"
            :class="{ active: graphicsMode === 'off' }"
            @click="graphicsMode = 'off'"
          >
            Off
          </button>
        </div>
        <p class="graphics-status">{{ autoStatus }}</p>
      </div>
    </div>
    <div class="login-card bg-slate-900/75 backdrop-blur-md border border-teal-500/20 p-8 rounded-2xl w-full max-w-md shadow-2xl">
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold text-teal-300 mb-2">SilentVoix</h1>
        <p class="text-slate-300">Sign Language Translation System</p>
      </div>

      <form class="space-y-6" @submit.prevent="handleLogin">
        <BaseInput 
            v-model="email" 
            label="Email" 
            type="email" 
            placeholder="admin@example.com"
            required
        />
        <BaseInput 
            v-model="password" 
            label="Password" 
            type="password" 
            placeholder="••••••••"
            required
        />

        <div v-if="error" class="text-red-500 text-sm bg-red-500/10 p-3 rounded-lg border border-red-500/20">
            {{ error }}
        </div>

        <BaseBtn 
            variant="primary" 
            class="w-full justify-center login-button-twinkle" 
            :disabled="isLoading"
        >
            <span v-if="isLoading">Signing in...</span>
            <span v-else>Sign In</span>
        </BaseBtn>
      </form>

      <div class="mt-6 text-center text-sm text-slate-300">
        New here?
        <button class="text-teal-300 hover:text-teal-200 underline underline-offset-2 ml-1" @click="router.push('/register')">
          Create account
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  position: relative;
  isolation: isolate;
  background: radial-gradient(circle at 20% 20%, #0f2633 0%, #020617 55%, #000000 100%);
}

.login-card {
  position: relative;
  z-index: 2;
}

.graphics-settings {
  position: fixed;
  top: 1rem;
  right: 1rem;
  z-index: 3;
}

.graphics-settings-trigger {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 9999px;
  border: 1px solid rgba(45, 212, 191, 0.35);
  background: rgba(2, 6, 23, 0.65);
  backdrop-filter: blur(8px);
  color: #99f6e4;
  display: grid;
  place-items: center;
}

.graphics-settings-trigger:hover {
  border-color: rgba(45, 212, 191, 0.7);
}

.graphics-gear-icon {
  width: 1.1rem;
  height: 1.1rem;
}

.graphics-settings-menu {
  margin-top: 0.5rem;
  width: min(18rem, 90vw);
  border: 1px solid rgba(45, 212, 191, 0.3);
  border-radius: 0.85rem;
  background: rgba(2, 6, 23, 0.86);
  backdrop-filter: blur(12px);
  padding: 0.75rem;
  color: #d1fae5;
}

.graphics-settings-title {
  font-size: 0.86rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.graphics-settings-options {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.graphics-option-btn {
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 0.55rem;
  background: rgba(15, 23, 42, 0.9);
  color: #cbd5e1;
  font-size: 0.8rem;
  padding: 0.45rem 0.35rem;
}

.graphics-option-btn.active {
  border-color: rgba(45, 212, 191, 0.9);
  background: rgba(13, 35, 44, 0.95);
  color: #99f6e4;
}

.graphics-status {
  font-size: 0.75rem;
  color: #94a3b8;
  line-height: 1.25;
}

@keyframes fadeToTransparent {
  to {
    opacity: 0;
  }
}

@keyframes twinkle {
  from {
    opacity: var(--twinkle-amount);
  }
  to {
    opacity: 1;
  }
}

.login-button-twinkle {
  --twinkle-amount: 0.5; /* Adjust as needed */
  --twinkle-duration: 1.5s; /* Adjust as needed */
  --fade-duration: 1s; /* Adjust as needed */
  animation:
    twinkle var(--twinkle-duration) infinite alternate ease-in-out,
    fadeToTransparent var(--fade-duration) 500ms;
}
</style>
