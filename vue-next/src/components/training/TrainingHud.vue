<script setup>
import { computed } from 'vue'

/*
 * Heads-up display layered over the live camera feed in Training (free and
 * advanced modes share it). Four glass chips in the corners plus a REC
 * badge while a take is being captured.
 */
const props = defineProps({
  fps: {
    type: Number,
    default: 0
  },
  lighting: {
    type: Object,
    default: () => ({ status: '--', colorClass: 'text-slate-400' })
  },
  gesture: {
    type: String,
    default: 'Waiting...'
  },
  // Pre-formatted, e.g. "87%" or "--%".
  confidence: {
    type: String,
    default: '--%'
  },
  recording: {
    type: Boolean,
    default: false
  }
})

const confidencePct = computed(() => {
  const value = Number.parseFloat(props.confidence)
  return Number.isFinite(value) ? Math.min(100, Math.max(0, value)) : 0
})

const confidenceTone = computed(() => {
  if (confidencePct.value >= 75) return 'hud-meter-good'
  if (confidencePct.value >= 45) return 'hud-meter-mid'
  return 'hud-meter-low'
})

const hasHand = computed(() => !['Waiting...', 'No Hand Detected'].includes(props.gesture))
</script>

<template>
  <div class="pointer-events-none absolute inset-0 p-4 sm:p-6">
    <Transition name="hud-rec">
      <div v-if="recording" class="hud-rec" role="status">
        <span class="hud-rec-dot" aria-hidden="true"></span>
        REC
      </div>
    </Transition>

    <div class="flex items-start justify-between gap-3">
      <div class="hud-chip">
        <div class="hud-label">FPS <span class="text-slate-500">/ 30</span></div>
        <div class="hud-value tabular-nums" :class="fps > 0 ? 'text-slate-50' : 'text-slate-500'">
          {{ fps || '--' }}
        </div>
      </div>
      <div class="hud-chip text-right">
        <div class="hud-label">Lighting</div>
        <div class="hud-value" :class="lighting.colorClass">{{ lighting.status }}</div>
      </div>
    </div>

    <div class="absolute inset-x-4 bottom-4 flex items-end justify-between gap-3 sm:inset-x-6 sm:bottom-6">
      <div class="hud-chip min-w-0">
        <div class="hud-label">Detected gesture</div>
        <Transition name="hud-swap" mode="out-in">
          <div
            :key="gesture"
            class="hud-value truncate"
            :class="hasHand ? 'hud-gesture' : 'text-slate-400'"
          >
            {{ gesture }}
          </div>
        </Transition>
      </div>
      <div class="hud-chip w-40 shrink-0 sm:w-48">
        <div class="flex items-baseline justify-between">
          <span class="hud-label">Confidence</span>
          <span class="text-sm font-semibold tabular-nums text-slate-100">{{ confidence }}</span>
        </div>
        <div class="hud-meter mt-2" role="meter" :aria-valuenow="confidencePct" aria-valuemin="0" aria-valuemax="100" aria-label="Confidence">
          <div class="hud-meter-fill" :class="confidenceTone" :style="{ transform: `scaleX(${confidencePct / 100})` }"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Always dark glass - it sits on a camera feed in both themes. */
.hud-chip {
  padding: 0.55rem 0.9rem;
  border-radius: 0.875rem;
  border: 1px solid rgb(255 255 255 / 0.1);
  background: rgb(2 6 23 / 0.62);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  box-shadow: 0 10px 30px -12px rgb(0 0 0 / 0.6);
  color: rgb(241 245 249);
}

.hud-label {
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgb(148 163 184);
}

.hud-value {
  margin-top: 0.125rem;
  font-size: 1.375rem;
  font-weight: 700;
  line-height: 1.2;
}

.hud-gesture {
  background: linear-gradient(100deg, rgb(103 232 249), rgb(196 181 253));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.hud-meter {
  height: 0.375rem;
  border-radius: 9999px;
  background: rgb(255 255 255 / 0.1);
  overflow: hidden;
}

.hud-meter-fill {
  height: 100%;
  border-radius: inherit;
  transform-origin: left;
  transition: transform 320ms var(--ease-out), background 320ms ease;
}

.hud-meter-good {
  background: linear-gradient(90deg, rgb(16 185 129), rgb(52 211 153));
  box-shadow: 0 0 10px rgb(52 211 153 / 0.6);
}

.hud-meter-mid {
  background: linear-gradient(90deg, rgb(245 158 11), rgb(251 191 36));
}

.hud-meter-low {
  background: linear-gradient(90deg, rgb(244 63 94), rgb(251 113 133));
}

.hud-rec {
  position: absolute;
  top: 1rem;
  left: 50%;
  translate: -50% 0;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.85rem;
  border-radius: 9999px;
  background: rgb(225 29 72 / 0.85);
  color: white;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  box-shadow: 0 0 24px rgb(244 63 94 / 0.55);
}

.hud-rec-dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 9999px;
  background: white;
  animation: hud-rec-blink 1s steps(2, start) infinite;
}

@keyframes hud-rec-blink {
  to { visibility: hidden; }
}

.hud-rec-enter-active {
  transition: opacity 240ms var(--ease-out), scale 360ms var(--ease-spring);
}

.hud-rec-leave-active {
  transition: opacity 160ms var(--ease-in), scale 160ms var(--ease-in);
}

.hud-rec-enter-from,
.hud-rec-leave-to {
  opacity: 0;
  scale: 0.7;
}

.hud-swap-enter-active {
  transition: opacity 180ms var(--ease-out), transform 180ms var(--ease-out);
}

.hud-swap-leave-active {
  transition: opacity 100ms var(--ease-in);
}

.hud-swap-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.hud-swap-leave-to {
  opacity: 0;
}
</style>
