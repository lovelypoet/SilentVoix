<script setup>
import { computed } from 'vue'

const props = defineProps({
  points: {
    type: Array,
    default: () => []
  },
  width: {
    type: Number,
    default: 72
  },
  height: {
    type: Number,
    default: 28
  },
  // The "now" point (line end) rides the accent color; the path itself
  // stays in the de-emphasis hue - see dataviz skill, stat-tile contract.
  accent: {
    type: String,
    default: 'rgb(var(--brand-400))'
  }
})

const PAD = 4

const geometry = computed(() => {
  const values = props.points.filter((v) => Number.isFinite(v))
  if (values.length < 2) return null

  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const innerW = props.width - PAD * 2
  const innerH = props.height - PAD * 2
  const step = innerW / (values.length - 1)

  const coords = values.map((v, i) => ({
    x: PAD + i * step,
    y: PAD + innerH - ((v - min) / span) * innerH
  }))

  const linePath = coords.map((c, i) => `${i === 0 ? 'M' : 'L'}${c.x.toFixed(2)},${c.y.toFixed(2)}`).join(' ')
  const areaPath = `${linePath} L${coords[coords.length - 1].x.toFixed(2)},${props.height - PAD} L${coords[0].x.toFixed(2)},${props.height - PAD} Z`
  const end = coords[coords.length - 1]

  return { linePath, areaPath, end }
})
</script>

<template>
  <svg
    v-if="geometry"
    :width="width"
    :height="height"
    :viewBox="`0 0 ${width} ${height}`"
    class="overflow-visible"
    aria-hidden="true"
  >
    <path :d="geometry.areaPath" :fill="accent" fill-opacity="0.1" stroke="none" />
    <path
      :d="geometry.linePath"
      fill="none"
      stroke="rgb(var(--slate-500))"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
    <circle :cx="geometry.end.x" :cy="geometry.end.y" r="4.5" :fill="accent" stroke="rgb(var(--surface))" stroke-width="2" />
  </svg>
</template>
