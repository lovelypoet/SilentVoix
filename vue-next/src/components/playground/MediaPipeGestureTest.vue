<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'
import { PhFlask, PhVideoCamera } from '@phosphor-icons/vue'
import BaseBtn from '@/components/base/BaseBtn.vue'
import StatusIndicator from '@/components/base/StatusIndicator.vue'
import { useGestureRecognizerCamera } from '@/composables/ai/useGestureRecognizerCamera'
import { createGestureSpeechGate } from '@/composables/ai/useGestureSpeechGate'
import { gestureToText } from '@/composables/ai/gestureSpeechMap'
import { useSpeechSynthesis } from '@/composables/ai/useSpeechSynthesis'

/*
 * Temporary test surface for Google's MediaPipe Gesture Recognizer, wired
 * straight to speech: camera -> gesture -> mapped text -> actual spoken
 * audio. This is deliberately isolated from the real V-Hand playground
 * (its own camera stream, its own model, its own state) so it can be
 * deleted later without touching the production inference path.
 */

const videoEl = ref(null)
const canvasEl = ref(null)

const camera = useGestureRecognizerCamera()
const speechGate = createGestureSpeechGate()
const tts = useSpeechSynthesis()

const currentGesture = ref(null)
const confidence = ref(0)
const spokenText = ref('')

const toggle = async () => {
  if (camera.isActive.value) {
    camera.stop()
    currentGesture.value = null
    confidence.value = 0
    speechGate.reset()
  } else {
    await camera.start(videoEl.value, canvasEl.value)
  }
}

camera.onFrame((result) => {
  const top = result?.gestures?.[0]?.[0]
  const name = top?.categoryName || null
  const score = top?.score || 0

  currentGesture.value = name
  confidence.value = score

  const toSpeak = speechGate.evaluate(name, score, performance.now())
  if (toSpeak) {
    const text = gestureToText(toSpeak)
    if (text) {
      spokenText.value = text
      tts.speak(text)
    }
  }
})

const confidencePct = computed(() => Math.round(confidence.value * 100))

const previewText = computed(() => {
  if (!currentGesture.value) return '—'
  return gestureToText(currentGesture.value) || '(no mapping for this gesture)'
})

const ttsIndicator = computed(() => {
  switch (tts.status.value) {
    case 'speaking': return { state: 'processing', label: 'Speaking' }
    case 'done': return { state: 'connected', label: 'Played' }
    case 'error': return { state: 'error', label: 'Error' }
    case 'unsupported': return { state: 'unavailable', label: 'Unsupported' }
    default: return { state: 'standby', label: 'Idle' }
  }
})

// Fade the "Played" confirmation back to idle so the badge doesn't get stuck.
let doneFadeTimer = null
watch(() => tts.status.value, (status) => {
  if (doneFadeTimer) {
    clearTimeout(doneFadeTimer)
    doneFadeTimer = null
  }
  if (status !== 'done') return
  doneFadeTimer = setTimeout(() => {
    if (tts.status.value === 'done') tts.status.value = 'idle'
    doneFadeTimer = null
  }, 2000)
})

onUnmounted(() => {
  if (doneFadeTimer) clearTimeout(doneFadeTimer)
  camera.stop()
})
</script>

<template>
  <div class="rounded-xl border border-warning-500/30 bg-warning-500/[0.03] p-4 sm:p-5">
    <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
      <div class="flex items-center gap-2.5">
        <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-warning-500/15 text-warning-400">
          <PhFlask size="16" weight="bold" aria-hidden="true" />
        </span>
        <div>
          <div class="flex items-center gap-2">
            <h2 class="text-sm font-semibold text-slate-100">MediaPipe Gesture Test</h2>
            <span class="status-badge status-badge-warning">Temporary</span>
          </div>
          <p class="text-xs text-slate-500 mt-0.5">Google's Gesture Recognizer, isolated from the V-Hand models above — for testing gesture → voice only.</p>
        </div>
      </div>
      <BaseBtn variant="secondary" :disabled="camera.isLoading.value" @click="toggle">
        {{ camera.isActive.value ? 'Stop Test' : 'Start Test' }}
      </BaseBtn>
    </div>

    <p v-if="camera.error.value" role="alert" class="mb-4 rounded-lg border border-danger-400/20 bg-danger-400/10 p-3 text-sm text-danger-300">
      {{ camera.error.value }}
    </p>

    <div class="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,20rem)_1fr]">
      <div class="relative aspect-video w-full max-w-xs overflow-hidden rounded-lg border border-slate-700 bg-black">
        <div v-if="!camera.isActive.value" class="absolute inset-0 flex flex-col items-center justify-center gap-2 text-center px-4">
          <PhVideoCamera size="28" weight="duotone" class="text-slate-600" aria-hidden="true" />
          <p class="text-xs text-slate-500">Start Test to begin</p>
        </div>
        <video ref="videoEl" autoplay playsinline muted class="absolute inset-0 h-full w-full object-cover -scale-x-100"></video>
        <canvas ref="canvasEl" class="absolute inset-0 h-full w-full -scale-x-100"></canvas>
      </div>

      <div class="space-y-3">
        <div class="grid grid-cols-2 gap-3">
          <div class="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
            <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-1">Current Gesture</p>
            <p class="text-lg font-semibold text-slate-100 truncate">{{ currentGesture || '—' }}</p>
          </div>
          <div class="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
            <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-1">Confidence</p>
            <div class="flex items-center gap-2">
              <div class="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-800">
                <div class="h-full rounded-full bg-warning-400 transition-[width] duration-200 ease-out" :style="{ width: `${confidencePct}%` }"></div>
              </div>
              <p class="text-xs text-slate-400 mono w-9 text-right">{{ confidencePct }}%</p>
            </div>
          </div>
        </div>

        <div class="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
          <div class="flex items-center justify-between mb-1">
            <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Text to Speak</p>
            <StatusIndicator :state="ttsIndicator.state" :label="ttsIndicator.label" size="sm" />
          </div>
          <p class="text-base text-slate-100">{{ previewText }}</p>
          <p v-if="tts.lastError.value" class="mt-1 text-xs text-danger-300">{{ tts.lastError.value }}</p>
        </div>

        <p class="text-xs text-slate-500">
          Last spoken: <span class="text-slate-300">{{ spokenText || '—' }}</span>
        </p>
      </div>
    </div>
  </div>
</template>
