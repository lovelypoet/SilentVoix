<script setup>
import BaseCard from './base/BaseCard.vue'
defineProps({
  sparkPath: { type: String, default: '' },
  cvPath: { type: String, default: '' },
  sparkThreshold: { type: [Number, null], default: null },
  cvThreshold: { type: [Number, null], default: null },
  sparkPeak: { type: Object, default: () => ({ x: 0, y: 0 }) },
  cvPeak: { type: Object, default: () => ({ x: 0, y: 0 }) },
  sparkSpike: { type: Object, default: null },
  cvSpike: { type: Object, default: null },
  sensorSpikeActive: { type: Boolean, default: false },
  cvSpikeActive: { type: Boolean, default: false },
  syncWsConnected: { type: Boolean, default: false },
  expectedSyncLabel: { type: String, default: '' }
})
</script>

<template>
  <BaseCard class="flex-1 h-12 px-3 py-2 border border-slate-800 bg-slate-950/70">
    <div class="h-full flex items-center gap-3">
      <div class="text-[10px] uppercase tracking-wider text-slate-500">Sync Spike</div>
      <div class="flex-1 h-full">
        <svg viewBox="0 0 100 24" class="w-full h-full">
          <defs>
            <linearGradient id="spark" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="#14b8a6" stop-opacity="0.2" />
              <stop offset="100%" stop-color="#14b8a6" stop-opacity="0.9" />
            </linearGradient>
          </defs>
          <rect x="0" y="0" width="100" height="24" fill="transparent" />
          <path
            :d="sparkPath"
            fill="none"
            stroke="url(#spark)"
            stroke-width="2"
          />
          <path
            :d="cvPath"
            fill="none"
            stroke="#f472b6"
            stroke-width="1.6"
            opacity="0.9"
          />
          <line
            v-if="sparkThreshold !== null"
            x1="0"
            x2="100"
            :y1="sparkThreshold"
            :y2="sparkThreshold"
            stroke="#f59e0b"
            stroke-width="1"
            stroke-dasharray="4 3"
            opacity="0.9"
          />
          <line
            v-if="cvThreshold !== null"
            x1="0"
            x2="100"
            :y1="cvThreshold"
            :y2="cvThreshold"
            stroke="#f472b6"
            stroke-width="1"
            stroke-dasharray="2 3"
            opacity="0.7"
          />
          <circle v-if="sparkPath" :cx="sparkPeak.x" :cy="sparkPeak.y" r="2.5" fill="#22c55e" />
          <circle v-if="cvPath" :cx="cvPeak.x" :cy="cvPeak.y" r="2.2" fill="#f472b6" />
          <circle v-if="sparkSpike" :cx="sparkSpike.x" :cy="sparkSpike.y" r="2.8" fill="#f59e0b" />
          <circle v-if="cvSpike" :cx="cvSpike.x" :cy="cvSpike.y" r="2.6" fill="#f472b6" />
        </svg>
      </div>
      <div
        class="text-[10px] font-semibold"
        :class="sensorSpikeActive || cvSpikeActive ? 'text-amber-300' : 'text-slate-500'"
      >
        {{ sensorSpikeActive || cvSpikeActive ? 'spike' : 'live' }}
      </div>
      <div
        class="text-[10px] font-semibold"
        :class="syncWsConnected ? 'text-emerald-400' : 'text-slate-500'"
      >
        {{ syncWsConnected ? 'ws:on' : 'ws:off' }}
      </div>
      <div v-if="expectedSyncLabel" class="text-[10px] text-slate-500">
        {{ expectedSyncLabel }}
      </div>
    </div>
  </BaseCard>
</template>
