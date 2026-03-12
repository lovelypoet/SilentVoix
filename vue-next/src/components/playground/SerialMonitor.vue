<script setup>
import { usePlaygroundStore } from '@/stores/playgroundStore'

const props = defineProps({
  sensorStream: { type: Object, required: true },
  earlyFusionInputStats: { type: Object, default: null },
  earlyFusionSensorOrder: { type: String, default: '' }
})

const store = usePlaygroundStore()
</script>

<template>
  <!-- Input Stats Overlay -->
  <div v-if="store.isFusionMode || store.isEarlyFusionMode || store.modelModality === 'sensor'" class="absolute right-0 top-0 bottom-0 w-56 overflow-auto bg-slate-950/80 p-3 border-l border-slate-700 backdrop-blur-sm">
    <p class="text-[10px] text-amber-500 font-bold uppercase mb-2">Input Stats</p>
    <div class="mb-2 rounded border border-slate-800 bg-slate-900/60 px-2 py-1">
      <div class="flex items-center justify-between text-[10px]">
        <span class="text-slate-500">Sensor</span>
        <span :class="props.sensorStream.sensorSnapshot.value.realSensor ? 'text-teal-400' : 'text-amber-300'">
          {{ props.sensorStream.sensorSnapshot.value.realSensor ? 'Live' : 'No Signal' }}
        </span>
      </div>
      <div class="flex items-center justify-between text-[10px]">
        <span class="text-slate-500">WS</span>
        <span :class="props.sensorStream.isConnected.value ? 'text-teal-400' : 'text-slate-400'">
          {{ props.sensorStream.isConnected.value ? 'Connected' : 'Disconnected' }}
        </span>
      </div>
      <div class="flex items-center justify-between text-[10px]">
        <span class="text-slate-500">Updated</span>
        <span class="text-slate-300">{{ props.sensorStream.updatedAtText.value }}</span>
      </div>
      <div v-if="props.earlyFusionSensorOrder" class="flex items-center justify-between text-[10px]">
        <span class="text-slate-500">Order</span>
        <span class="text-slate-300">{{ props.earlyFusionSensorOrder }}</span>
      </div>
    </div>
    <div v-if="props.earlyFusionInputStats" class="space-y-1">
      <div class="flex justify-between text-[10px] border-b border-slate-800 pb-1">
        <span class="text-slate-500">Len</span>
        <span class="text-slate-200 font-mono">{{ props.earlyFusionInputStats.len }}</span>
      </div>
      <div class="flex justify-between text-[10px] border-b border-slate-800 pb-1">
        <span class="text-slate-500">Zeros</span>
        <span class="text-slate-200 font-mono">{{ props.earlyFusionInputStats.zeros }}</span>
      </div>
      <div class="flex justify-between text-[10px] border-b border-slate-800 pb-1">
        <span class="text-slate-500">Min</span>
        <span class="text-slate-200 font-mono">{{ Number(props.earlyFusionInputStats.min).toFixed(4) }}</span>
      </div>
      <div class="flex justify-between text-[10px] border-b border-slate-800 pb-1">
        <span class="text-slate-500">Max</span>
        <span class="text-slate-200 font-mono">{{ Number(props.earlyFusionInputStats.max).toFixed(4) }}</span>
      </div>
      <div class="flex justify-between text-[10px] border-b border-slate-800 pb-1">
        <span class="text-slate-500">Mean</span>
        <span class="text-slate-200 font-mono">{{ Number(props.earlyFusionInputStats.mean).toFixed(4) }}</span>
      </div>
    </div>
    <p v-else-if="store.isEarlyFusionMode" class="text-[10px] text-slate-500">Waiting for early-fusion stats...</p>
  </div>
</template>
