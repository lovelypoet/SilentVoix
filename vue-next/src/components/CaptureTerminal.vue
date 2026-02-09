<script setup>
import BaseCard from './base/BaseCard.vue'
import BaseBtn from './base/BaseBtn.vue'
import { ref, defineExpose } from 'vue'

defineProps({
  isStreaming: { type: Boolean, default: false },
  terminalLines: { type: Array, default: () => [] },
  terminalError: { type: String, default: '' },
  autoScroll: { type: Boolean, default: true }
})

const emit = defineEmits(['toggle-stream', 'update:autoScroll'])
const terminalEl = ref(null)

const onToggle = () => {
  emit('toggle-stream')
}

defineExpose({ terminalEl })
</script>

<template>
  <BaseCard class="bg-slate-950/70 border border-slate-800">
    <div class="flex items-center justify-between mb-3">
      <div>
        <div class="text-sm font-semibold text-slate-200">Collector Logs</div>
        <div class="text-xs text-slate-500">
          <slot name="subtitle">Collector output</slot>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <span
          class="text-xs font-semibold"
          :class="isStreaming ? 'text-green-400' : 'text-slate-500'"
        >
          {{ isStreaming ? 'Live' : 'Idle' }}
        </span>
        <BaseBtn
          variant="secondary"
          class="px-3 py-1 text-xs"
          @click="onToggle"
        >
          {{ isStreaming ? 'Stop' : 'Connect' }}
        </BaseBtn>
      </div>
    </div>

    <div
      ref="terminalEl"
      class="terminal-body h-44 overflow-y-auto rounded-lg border border-slate-800 bg-black/70 px-4 py-3 font-mono text-xs text-slate-200"
    >
      <div v-if="terminalError" class="text-red-400">{{ terminalError }}</div>
      <div v-else-if="terminalLines.length === 0" class="text-slate-500">
        No log output yet.
      </div>
      <div v-else class="space-y-1">
        <div v-for="(line, idx) in terminalLines" :key="`term-${idx}`">
          <span class="text-emerald-400">$</span>
          <span class="ml-2">{{ line }}</span>
        </div>
      </div>
    </div>

    <div class="mt-3 flex items-center justify-between text-xs text-slate-500">
      <label class="flex items-center gap-2 cursor-pointer">
        <input
          :checked="autoScroll"
          type="checkbox"
          class="accent-teal-400"
          @change="emit('update:autoScroll', $event.target.checked)"
        />
        Auto-scroll
      </label>
      <span>Last 200 lines</span>
    </div>
  </BaseCard>
</template>

<style scoped>
.terminal-body {
  scrollbar-width: thin;
}
</style>
