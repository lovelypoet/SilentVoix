<script setup>
import { onMounted, onBeforeUnmount, ref, nextTick } from 'vue'
import { useTrainingSettings } from '../composables/useTrainingSettings'
import BaseBtn from './base/BaseBtn.vue'

const emit = defineEmits(['close'])

const {
  selectedCamera,
  enableCamera,
  resolution,
  mirrorCamera,
  trainingMode,
  countdown,
  frameLimit,
  showLandmarks,
  enableAISuggestions, // Import new setting
  cameraDevices,
  resolutionOptions,
  getCameraDevices,
  resetSettings,
} = useTrainingSettings()

// This component's own mount/unmount lifetime IS its open/close state - the
// parent renders it with v-if rather than toggling a prop - so the modal
// mechanics (focus trap, Escape, initial focus, focus restore) hang off
// onMounted/onBeforeUnmount instead of a watched prop, mirroring the
// pattern in App.vue's mobile nav drawer and BaseModal.
const panelRef = ref(null)
let previouslyFocused = null

const focusableInPanel = () => {
  if (!panelRef.value) return []
  return Array.from(
    panelRef.value.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')
  )
}

const onKeydown = (event) => {
  if (event.key === 'Escape') {
    event.stopPropagation()
    emit('close')
    return
  }
  if (event.key !== 'Tab') return

  const focusable = focusableInPanel()
  if (focusable.length === 0) return
  const first = focusable[0]
  const last = focusable[focusable.length - 1]

  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

onMounted(async () => {
  getCameraDevices()
  previouslyFocused = document.activeElement
  document.addEventListener('keydown', onKeydown)
  document.body.style.overflow = 'hidden'
  await nextTick()
  focusableInPanel()[0]?.focus()
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
  previouslyFocused?.focus?.()
})
</script>

<template>
  <div class="fixed inset-0 bg-black/80 flex items-center justify-center z-50" @click.self="emit('close')">
    <div ref="panelRef" role="dialog" aria-modal="true" aria-labelledby="training-settings-title" class="bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl max-w-md w-full p-8 m-4">
      <div class="flex justify-between items-center mb-6">
        <h2 id="training-settings-title" class="text-2xl font-bold text-slate-100">Settings</h2>
        <button type="button" class="focus-ring text-slate-500 hover:text-slate-100 transition-colors" aria-label="Close settings" @click="emit('close')">&times;</button>
      </div>

      <div class="space-y-6 text-sm">
        <!-- Camera -->
        <div class="space-y-3">
          <h3 class="text-lg font-semibold text-slate-300">Camera</h3>
          <div class="grid grid-cols-2 gap-4 items-center">
            <label for="camera-device" class="text-slate-400">Camera Device</label>
            <select id="camera-device" v-model="selectedCamera" class="bg-slate-700 border border-slate-600 rounded-md px-3 py-2 text-slate-100 w-full">
              <option v-for="device in cameraDevices" :key="device.deviceId" :value="device.deviceId">
                {{ device.label || `Camera ${cameraDevices.indexOf(device) + 1}` }}
              </option>
            </select>
          </div>
          <div class="grid grid-cols-2 gap-4 items-center">
            <label for="enable-camera" class="text-slate-400">Enable Camera</label>
            <input id="enable-camera" v-model="enableCamera" type="checkbox" class="toggle-switch">
          </div>
        </div>

        <!-- Video -->
        <div class="space-y-3">
          <h3 class="text-lg font-semibold text-slate-300">Video</h3>
          <div class="grid grid-cols-2 gap-4 items-center">
            <label for="resolution" class="text-slate-400">Resolution</label>
            <select id="resolution" v-model="resolution" class="bg-slate-700 border border-slate-600 rounded-md px-3 py-2 text-slate-100 w-full">
              <option v-for="(res, name) in resolutionOptions" :key="name" :value="name">{{ name }}</option>
            </select>
          </div>
          <div class="grid grid-cols-2 gap-4 items-center">
            <label for="mirror-camera" class="text-slate-400">Mirror Camera</label>
            <input id="mirror-camera" v-model="mirrorCamera" type="checkbox" class="toggle-switch">
          </div>
        </div>

        <!-- Training -->
        <div class="space-y-3">
          <h3 class="text-lg font-semibold text-slate-300">Training</h3>
          <div class="grid grid-cols-2 gap-4 items-center">
            <label for="training-mode" class="text-slate-400">Mode</label>
            <select id="training-mode" v-model="trainingMode" class="bg-slate-700 border border-slate-600 rounded-md px-3 py-2 text-slate-100 w-full">
              <option>Practice</option>
              <option disabled>Guided</option>
            </select>
          </div>
          <div class="grid grid-cols-2 gap-4 items-center">
            <label for="countdown" class="text-slate-400">Countdown</label>
            <select id="countdown" v-model="countdown" class="bg-slate-700 border border-slate-600 rounded-md px-3 py-2 text-slate-100 w-full">
              <option :value="0">Off</option>
              <option :value="3">3s</option>
              <option :value="5">5s</option>
            </select>
          </div>
          <div class="grid grid-cols-2 gap-4 items-center">
            <label for="frame-limit" class="text-slate-400">Frame Limit</label>
            <select id="frame-limit" v-model="frameLimit" class="bg-slate-700 border border-slate-600 rounded-md px-3 py-2 text-slate-100 w-full">
              <option :value="100">100</option>
              <option :value="150">150</option>
              <option :value="200">200</option>
            </select>
          </div>
        </div>

        <!-- Visualization -->
        <div class="space-y-3">
          <h3 class="text-lg font-semibold text-slate-300">Visualization</h3>
          <div class="grid grid-cols-2 gap-4 items-center">
            <label for="show-landmarks" class="text-slate-400">Show Landmarks</label>
            <input id="show-landmarks" v-model="showLandmarks" type="checkbox" class="toggle-switch">
          </div>
        </div>

        <!-- AI Suggestions -->
        <div class="space-y-3">
          <h3 class="text-lg font-semibold text-slate-300">AI Suggestions</h3>
          <div class="grid grid-cols-2 gap-4 items-center">
            <label for="enable-ai-suggestions" class="text-slate-400">Enable AI Suggestions</label>
            <input id="enable-ai-suggestions" v-model="enableAISuggestions" type="checkbox" class="toggle-switch">
          </div>
        </div>
      </div>
      
      <div class="mt-8 border-t border-slate-700 pt-6 flex justify-end">
        <BaseBtn variant="secondary" @click="resetSettings">Reset Settings</BaseBtn>
      </div>
    </div>
  </div>
</template>

<style>
.toggle-switch {
  /* A simple toggle switch style */
  appearance: none;
  width: 3.5rem;
  height: 1.75rem;
  border-radius: 9999px;
  background-color: #4a5568;
  position: relative;
  transition: background-color 0.2s ease-in-out;
}
.toggle-switch:checked {
  background-color: rgb(var(--brand-600));
}
.toggle-switch::before {
  content: '';
  position: absolute;
  left: 0.25rem;
  top: 0.25rem;
  width: 1.25rem;
  height: 1.25rem;
  border-radius: 9999px;
  background-color: white;
  transition: transform 0.2s ease-in-out;
}
.toggle-switch:checked::before {
  transform: translateX(1.75rem);
}
</style>
