<script setup>
import { computed } from 'vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import BaseCard from '../components/base/BaseCard.vue'
import { useSensorTraining } from '../composables/useSensorTraining'

const {
  canExport,
  clearLiveFrames,
  connect,
  connectionError,
  connectionState,
  disconnect,
  estimatedFps,
  exportRecordedCsv,
  exportRecordedJson,
  isConnected,
  isRecording,
  label,
  lastFrameAt,
  latestChannels,
  latestFrame,
  liveFrames,
  maxLiveFrames,
  recordedFrames,
  resetRecording,
  sessionId,
  startRecording,
  stopRecording
} = useSensorTraining()

const lastFrames = computed(() => {
  if (!liveFrames.value.length) return []
  return [...liveFrames.value].slice(-20).reverse()
})

const formatTime = (timestampMs) => {
  if (!timestampMs) return '--'
  return new Date(timestampMs).toLocaleTimeString()
}

const channelPercent = (value, index) => {
  const numeric = Number(value)
  if (Number.isNaN(numeric)) return 0

  if (index < 5) {
    const clamped = Math.min(Math.max(numeric, 0), 1023)
    return Math.round((clamped / 1023) * 100)
  }

  const imuMin = -4
  const imuMax = 4
  const clamped = Math.min(Math.max(numeric, imuMin), imuMax)
  return Math.round(((clamped - imuMin) / (imuMax - imuMin)) * 100)
}
</script>

<template>
  <div class="max-w-7xl mx-auto">
    <section class="mb-6">
      <h1 class="text-3xl font-bold text-teal-300">Sensor Training</h1>
      <p class="text-slate-400 mt-1">
        Live websocket capture from <code>/ws/stream</code> with label-aware recording and export.
      </p>
    </section>

    <section class="grid gap-4 md:grid-cols-2 xl:grid-cols-4 mb-6">
      <BaseCard>
        <p class="text-xs uppercase tracking-wide text-slate-400">Connection</p>
        <p class="text-lg font-semibold mt-2" :class="isConnected ? 'text-emerald-300' : 'text-amber-300'">
          {{ connectionState }}
        </p>
        <p class="text-xs text-slate-500 mt-2">Endpoint: /ws/stream</p>
      </BaseCard>

      <BaseCard>
        <p class="text-xs uppercase tracking-wide text-slate-400">Live Frames</p>
        <p class="text-2xl font-semibold text-slate-100 mt-2">{{ liveFrames.length }}</p>
        <p class="text-xs text-slate-500 mt-2">Est. rate: {{ estimatedFps }} fps</p>
      </BaseCard>

      <BaseCard>
        <p class="text-xs uppercase tracking-wide text-slate-400">Recording</p>
        <p class="text-2xl font-semibold text-slate-100 mt-2">{{ recordedFrames.length }}</p>
        <p class="text-xs mt-2" :class="isRecording ? 'text-emerald-300' : 'text-slate-500'">
          {{ isRecording ? 'active' : 'idle' }}
        </p>
      </BaseCard>

      <BaseCard>
        <p class="text-xs uppercase tracking-wide text-slate-400">Last Frame</p>
        <p class="text-lg font-semibold text-slate-100 mt-2">
          {{ lastFrameAt ? lastFrameAt.toLocaleTimeString() : '--' }}
        </p>
        <p class="text-xs text-slate-500 mt-2">Schema: silentvoix.sensor_frame.v1</p>
      </BaseCard>
    </section>

    <section class="grid gap-6 xl:grid-cols-3">
      <BaseCard class="xl:col-span-2">
        <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
          <h2 class="text-xl font-semibold text-slate-100">Live Channel Readout</h2>
          <div class="flex items-center gap-2">
            <BaseBtn v-if="!isConnected" variant="primary" @click="connect">Connect</BaseBtn>
            <BaseBtn v-else variant="secondary" @click="disconnect">Disconnect</BaseBtn>
            <BaseBtn variant="danger" @click="clearLiveFrames">Clear Live</BaseBtn>
          </div>
        </div>

        <p v-if="connectionError" class="text-sm text-rose-300 mb-4">{{ connectionError }}</p>

        <div v-if="latestFrame" class="space-y-4">
          <div>
            <p class="text-sm font-medium text-slate-300 mb-2">Flex (0-1023)</p>
            <div class="space-y-2">
              <div
                v-for="(value, idx) in latestChannels.flex"
                :key="`flex_${idx}`"
                class="rounded-lg border border-slate-700 bg-slate-950/40 p-2"
              >
                <div class="flex justify-between text-xs text-slate-300 mb-1">
                  <span>flex{{ idx + 1 }}</span>
                  <span>{{ Number(value).toFixed(2) }}</span>
                </div>
                <div class="h-2 rounded bg-slate-800 overflow-hidden">
                  <div class="h-full bg-teal-400" :style="{ width: `${channelPercent(value, idx)}%` }"></div>
                </div>
              </div>
            </div>
          </div>

          <div>
            <p class="text-sm font-medium text-slate-300 mb-2">Accel / Gyro (approx -4 to 4)</p>
            <div class="space-y-2">
              <div
                v-for="(value, idx) in [...latestChannels.accel, ...latestChannels.gyro]"
                :key="`imu_${idx}`"
                class="rounded-lg border border-slate-700 bg-slate-950/40 p-2"
              >
                <div class="flex justify-between text-xs text-slate-300 mb-1">
                  <span>{{ idx < 3 ? `accel_${['x', 'y', 'z'][idx]}` : `gyro_${['x', 'y', 'z'][idx - 3]}` }}</span>
                  <span>{{ Number(value).toFixed(4) }}</span>
                </div>
                <div class="h-2 rounded bg-slate-800 overflow-hidden">
                  <div class="h-full bg-sky-400" :style="{ width: `${channelPercent(value, idx + 5)}%` }"></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <p v-else class="text-slate-400">Waiting for sensor frames.</p>
      </BaseCard>

      <BaseCard>
        <h2 class="text-xl font-semibold text-slate-100 mb-4">Capture Controls</h2>
        <div class="space-y-3">
          <label class="block text-sm text-slate-300">
            Session ID
            <input
              v-model="sessionId"
              type="text"
              class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2 text-slate-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </label>

          <label class="block text-sm text-slate-300">
            Label
            <input
              v-model="label"
              type="text"
              placeholder="e.g. hello, rest, custom gesture"
              class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2 text-slate-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </label>

          <label class="block text-sm text-slate-300">
            Live Buffer Size
            <input
              v-model.number="maxLiveFrames"
              type="number"
              min="20"
              max="2000"
              class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2 text-slate-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </label>
        </div>

        <div class="grid grid-cols-2 gap-2 mt-5">
          <BaseBtn v-if="!isRecording" variant="primary" @click="startRecording">Start</BaseBtn>
          <BaseBtn v-else variant="amber" @click="stopRecording">Stop</BaseBtn>
          <BaseBtn variant="danger" @click="resetRecording">Reset</BaseBtn>
        </div>

        <div class="grid grid-cols-2 gap-2 mt-3">
          <BaseBtn :disabled="!canExport" variant="secondary" @click="exportRecordedCsv">Export CSV</BaseBtn>
          <BaseBtn :disabled="!canExport" variant="secondary" @click="exportRecordedJson">Export JSON</BaseBtn>
        </div>
      </BaseCard>
    </section>

    <section class="mt-6">
      <BaseCard>
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-xl font-semibold text-slate-100">Recent Frames</h2>
          <p class="text-xs text-slate-500">
            showing {{ lastFrames.length }} / {{ liveFrames.length }}
          </p>
        </div>
        <div class="overflow-auto">
          <table class="w-full min-w-[900px] text-sm">
            <thead class="text-slate-400 border-b border-slate-800">
              <tr>
                <th class="text-left py-2 pr-3">Time</th>
                <th class="text-left py-2 pr-3">Sequence</th>
                <th class="text-left py-2 pr-3">Label</th>
                <th class="text-left py-2 pr-3">Source</th>
                <th class="text-left py-2 pr-3">Values</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(frame, idx) in lastFrames"
                :key="`row_${idx}_${frame.timestamp_ms}`"
                class="border-b border-slate-900/70 text-slate-200"
              >
                <td class="py-2 pr-3 whitespace-nowrap">{{ formatTime(frame.timestamp_ms) }}</td>
                <td class="py-2 pr-3">{{ frame.sequence ?? '--' }}</td>
                <td class="py-2 pr-3">{{ label || 'unlabeled' }}</td>
                <td class="py-2 pr-3">{{ frame.source || '--' }}</td>
                <td class="py-2 pr-3 text-xs text-slate-300">
                  {{ frame.values.map((v) => Number(v).toFixed(3)).join(', ') }}
                </td>
              </tr>
              <tr v-if="!lastFrames.length">
                <td colspan="5" class="py-4 text-slate-500">No frames yet.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </BaseCard>
    </section>
  </div>
</template>
