<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'
import {
  PhCircleNotch,
  PhHandWaving,
  PhSpeakerHigh,
  PhStop,
  PhVideoCamera,
  PhWarningCircle
} from '@phosphor-icons/vue'
import BasePageHeader from '@/components/base/BasePageHeader.vue'
import BaseBtn from '@/components/base/BaseBtn.vue'
import StatusIndicator from '@/components/base/StatusIndicator.vue'
import { useAslRecognizer, DETECT_FPS } from '@/composables/ai/useAslRecognizer'
import { createGestureSpeechGate } from '@/composables/ai/useGestureSpeechGate'
import { useSpeechSynthesis } from '@/composables/ai/useSpeechSynthesis'
import { labelToSpeech } from '@/composables/ai/aslModel'

/*
 * ASL Studio: in-browser ASL sign recognition + speech. HandLandmarker feeds
 * a sliding window of two-hand landmarks into the 77-class ONNX model from
 * namratha2412/asl-improved-recognition, and a stable, confident prediction
 * is spoken with the browser's speechSynthesis (the same gate and TTS wrapper
 * as the MediaPipe Gesture Test). Nothing here calls the backend.
 */

const videoEl = ref(null)
const canvasEl = ref(null)

const asl = useAslRecognizer()
const tts = useSpeechSynthesis()

const windowFrames = ref(30)
const confidenceThreshold = ref(0.5)
const speechEnabled = ref(true)
const lastSpoken = ref('')
const transcript = ref([])

let gate = createGestureSpeechGate({ confidenceThreshold: confidenceThreshold.value, stableFrames: 2 })

watch(windowFrames, (frames) => {
  asl.configure({ windowFrames: frames, minHandFrames: Math.min(8, Math.ceil(frames / 2)) })
}, { immediate: true })

watch(confidenceThreshold, (threshold) => {
  gate = createGestureSpeechGate({ confidenceThreshold: threshold, stableFrames: 2 })
})

asl.onPrediction((ranked) => {
  const top = ranked[0]
  const toSpeak = gate.evaluate(top?.label, top?.prob ?? 0, performance.now())
  if (!toSpeak) return
  const text = labelToSpeech(toSpeak)
  lastSpoken.value = text
  transcript.value = [...transcript.value, text].slice(-20)
  if (speechEnabled.value) tts.speak(text, { lang: 'en-US' })
})

// Once the hands drop out, predictions clear; reset the gate so signing the
// same word again (a new attempt) is allowed to speak.
watch(() => asl.predictions.value.length, (count) => {
  if (count === 0) gate.reset()
})

const start = () => asl.start(videoEl.value, canvasEl.value)
const stop = () => {
  asl.stop()
  gate.reset()
}

const top = computed(() => asl.predictions.value[0] || null)
const pct = (p) => `${Math.round((p || 0) * 100)}%`
const windowSeconds = computed(() => (windowFrames.value / DETECT_FPS).toFixed(1))
const bufferPct = computed(() => Math.round((asl.bufferFill.value / windowFrames.value) * 100))

const ttsIndicator = computed(() => {
  switch (tts.status.value) {
    case 'speaking': return { state: 'processing', label: 'Speaking' }
    case 'done': return { state: 'connected', label: 'Played' }
    case 'error': return { state: 'error', label: 'Error' }
    case 'unsupported': return { state: 'unavailable', label: 'Unsupported' }
    default: return { state: 'standby', label: 'Idle' }
  }
})

const speakAgain = () => {
  if (lastSpoken.value) tts.speak(lastSpoken.value, { lang: 'en-US' })
}

onUnmounted(() => asl.stop())
</script>

<template>
  <div class="space-y-6">
    <BasePageHeader
      title="ASL Studio"
      description="Two-hand MediaPipe landmarks feed a 77-sign ASL model (CNN + BiLSTM, ONNX), and the browser speaks the result, all in this tab."
    >
      <template #actions>
        <BaseBtn v-if="!asl.isActive.value" variant="primary" :disabled="asl.isLoading.value" @click="start">
          <span class="flex items-center gap-2">
            <PhCircleNotch v-if="asl.isLoading.value" size="18" weight="bold" class="animate-spin" />
            <PhVideoCamera v-else size="18" weight="bold" />
            {{ asl.isLoading.value ? 'Loading model…' : 'Start camera' }}
          </span>
        </BaseBtn>
        <BaseBtn v-else variant="danger" @click="stop">
          <span class="flex items-center gap-2">
            <PhStop size="18" weight="bold" />
            Stop
          </span>
        </BaseBtn>
      </template>
    </BasePageHeader>

    <div
      v-if="asl.error.value"
      role="alert"
      class="flex items-start gap-2 rounded-lg border border-danger-500/30 bg-danger-500/5 px-4 py-3 text-sm text-danger-300"
    >
      <PhWarningCircle size="18" weight="bold" class="mt-0.5 shrink-0" />
      <span>{{ asl.error.value }}</span>
    </div>

    <div class="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
      <!-- Camera -->
      <div class="space-y-3">
        <div class="relative aspect-video w-full overflow-hidden rounded-xl border border-slate-700 bg-black">
          <div v-if="!asl.isActive.value" class="absolute inset-0 flex flex-col items-center justify-center gap-2 px-4 text-center">
            <PhHandWaving size="32" weight="duotone" class="text-slate-600" aria-hidden="true" />
            <p class="text-sm text-slate-500">Start the camera and sign in front of it</p>
          </div>
          <video ref="videoEl" autoplay playsinline muted class="absolute inset-0 h-full w-full object-cover -scale-x-100"></video>
          <canvas ref="canvasEl" class="absolute inset-0 h-full w-full object-cover -scale-x-100"></canvas>
          <div v-if="asl.isActive.value" class="absolute left-3 top-3 flex gap-2 text-xs">
            <span class="rounded-md bg-black/60 px-2 py-1 text-slate-200">Hands: {{ asl.handsVisible.value }}</span>
            <span class="rounded-md bg-black/60 px-2 py-1 text-slate-200 mono">{{ asl.inferenceMs.value }} ms</span>
          </div>
        </div>

        <div class="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
          <div class="mb-1 flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            <span>Frame window</span>
            <span class="mono normal-case">{{ asl.bufferFill.value }} / {{ windowFrames }}</span>
          </div>
          <div class="h-1.5 overflow-hidden rounded-full bg-slate-800">
            <div class="h-full rounded-full bg-brand-400 transition-[width] duration-150" :style="{ width: `${bufferPct}%` }"></div>
          </div>
        </div>
      </div>

      <!-- Results -->
      <div class="space-y-4">
        <div class="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
          <p class="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Detected sign</p>
          <div class="flex items-baseline justify-between gap-3">
            <p class="truncate text-3xl font-semibold text-slate-100">{{ top ? labelToSpeech(top.label) : '—' }}</p>
            <p class="mono text-sm text-slate-400">{{ top ? pct(top.prob) : '' }}</p>
          </div>
          <ul class="mt-4 space-y-2">
            <li v-for="p in asl.predictions.value" :key="p.index" class="flex items-center gap-3 text-sm">
              <span class="w-24 truncate text-slate-300">{{ labelToSpeech(p.label) }}</span>
              <div class="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-800">
                <div
                  class="h-full rounded-full transition-[width] duration-200"
                  :class="p.prob >= confidenceThreshold ? 'bg-success-400' : 'bg-slate-500'"
                  :style="{ width: pct(p.prob) }"
                ></div>
              </div>
              <span class="mono w-10 text-right text-xs text-slate-400">{{ pct(p.prob) }}</span>
            </li>
            <li v-if="!asl.predictions.value.length" class="text-xs text-slate-500">
              {{ asl.isActive.value ? 'Show your hands to the camera…' : 'Not running.' }}
            </li>
          </ul>
        </div>

        <div class="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
          <div class="mb-2 flex items-center justify-between">
            <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Speech</p>
            <StatusIndicator :state="ttsIndicator.state" :label="ttsIndicator.label" size="sm" />
          </div>
          <div class="flex items-center justify-between gap-3">
            <p class="text-lg text-slate-100">{{ lastSpoken || '—' }}</p>
            <BaseBtn variant="secondary" :disabled="!lastSpoken" @click="speakAgain">
              <span class="flex items-center gap-2"><PhSpeakerHigh size="16" weight="bold" /> Replay</span>
            </BaseBtn>
          </div>
          <p v-if="tts.lastError.value" class="mt-1 text-xs text-danger-300">{{ tts.lastError.value }}</p>
          <p class="mt-3 text-xs text-slate-500">
            Transcript: <span class="text-slate-300">{{ transcript.join(' · ') || '—' }}</span>
          </p>
        </div>

        <div class="space-y-4 rounded-xl border border-slate-800 bg-slate-950/40 p-4">
          <label class="flex items-center justify-between gap-3 text-sm text-slate-300">
            <span>Speak detected signs</span>
            <input v-model="speechEnabled" type="checkbox" class="h-4 w-4 accent-brand-400" />
          </label>
          <label class="block text-sm text-slate-300">
            <span class="flex justify-between">
              <span>Speak when confidence ≥</span><span class="mono text-slate-400">{{ pct(confidenceThreshold) }}</span>
            </span>
            <input v-model.number="confidenceThreshold" type="range" min="0.2" max="0.95" step="0.05" class="mt-2 w-full accent-brand-400" />
          </label>
          <label class="block text-sm text-slate-300">
            <span class="flex justify-between">
              <span>Window length</span><span class="mono text-slate-400">{{ windowFrames }} frames · {{ windowSeconds }} s</span>
            </span>
            <input v-model.number="windowFrames" type="range" min="10" max="60" step="5" class="mt-2 w-full accent-brand-400" />
          </label>
          <p class="text-xs leading-relaxed text-slate-500">
            The model reports 64.6% validation accuracy on its own data and is sensitive to clip length.
            Shorter windows favour letters (A–Z) and longer ones favour words, so adjust the window to fit how you sign.
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
