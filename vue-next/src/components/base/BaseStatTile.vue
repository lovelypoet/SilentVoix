<script setup>
import { computed } from 'vue'
import { PhArrowUp, PhArrowDown } from '@phosphor-icons/vue'
import BaseCard from './BaseCard.vue'
import BaseSparkline from './BaseSparkline.vue'

const props = defineProps({
  icon: {
    type: [Object, Function],
    required: true
  },
  label: {
    type: String,
    required: true
  },
  value: {
    type: String,
    required: true
  },
  // Signed change vs the previous reading, already formatted (e.g. "2.1ms", "0.4%").
  // Omit when there isn't at least two data points yet.
  delta: {
    type: String,
    default: ''
  },
  deltaDirection: {
    type: String,
    default: 'neutral' // 'up', 'down', 'neutral' - which way the raw value moved
  },
  // Whether a rising value is the good outcome for this metric (uptime: true,
  // latency/error-rate: false, throughput: null -> purely informational, no color).
  risingIsGood: {
    type: Boolean,
    default: null
  },
  points: {
    type: Array,
    default: () => []
  },
  accent: {
    type: String,
    default: 'rgb(var(--brand-400))'
  }
})

const deltaTone = computed(() => {
  if (!props.delta || props.deltaDirection === 'neutral' || props.risingIsGood === null) return 'neutral'
  const favorable = props.deltaDirection === 'up' ? props.risingIsGood : !props.risingIsGood
  return favorable ? 'good' : 'bad'
})
</script>

<template>
  <BaseCard class="flex flex-col gap-3 stat-tile">
    <div class="flex items-start justify-between">
      <div class="flex items-center gap-2.5">
        <span
          class="stat-icon flex h-9 w-9 shrink-0 items-center justify-center rounded-xl"
          :style="{
            background: `linear-gradient(135deg, color-mix(in srgb, ${accent} 26%, transparent), color-mix(in srgb, ${accent} 6%, transparent))`,
            boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${accent} 30%, transparent), 0 0 18px -4px color-mix(in srgb, ${accent} 55%, transparent)`,
            color: accent
          }"
        >
          <component :is="icon" size="17" weight="bold" aria-hidden="true" />
        </span>
        <p class="stat-label">{{ label }}</p>
      </div>
      <BaseSparkline v-if="points.length >= 2" :points="points" :accent="accent" />
    </div>

    <div class="flex items-end justify-between gap-2">
      <Transition name="stat-swap" mode="out-in">
        <p :key="value" class="stat-value">{{ value }}</p>
      </Transition>
      <div
        v-if="delta"
        class="mb-0.5 flex items-center gap-1 text-xs font-medium"
        :class="{
          'text-success-400': deltaTone === 'good',
          'text-danger-400': deltaTone === 'bad',
          'text-slate-500': deltaTone === 'neutral'
        }"
      >
        <PhArrowUp v-if="deltaDirection === 'up'" size="12" weight="bold" />
        <PhArrowDown v-else-if="deltaDirection === 'down'" size="12" weight="bold" />
        {{ delta }}
      </div>
    </div>
  </BaseCard>
</template>

<style scoped>
.stat-icon {
  transition: transform var(--dur) var(--ease-spring);
}

.stat-tile:hover .stat-icon {
  transform: rotate(-8deg) scale(1.1);
}

/* Live values tick over with a short vertical slide instead of snapping. */
.stat-swap-enter-active {
  transition: opacity 220ms var(--ease-out), transform 220ms var(--ease-out);
}

.stat-swap-leave-active {
  transition: opacity 120ms var(--ease-in), transform 120ms var(--ease-in);
}

.stat-swap-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.stat-swap-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
