<script setup>
import { onMounted } from 'vue'
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
  showLandmarks,
  enableAISuggestions, // Import new setting
  cameraDevices,
  resolutionOptions,
  getCameraDevices,
  resetSettings,
} = useTrainingSettings()

onMounted(() => {
  getCameraDevices()
})
</script>

<template>
  <div class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50" @click.self="emit('close')">
    <div class="bg-slate-800/80 border border-slate-700 rounded-2xl shadow-2xl max-w-md w-full p-8 m-4">
      <div class="flex justify-between items-center mb-6">
        <h2 class="text-2xl font-bold text-white">Settings </h2>
        <button class="text-slate-500 hover:text-white transition-colors" @click="emit('close')">&times;</button>
      </div>

      <div class="space-y-6 text-sm">
        <!-- Camera -->
        <div class="space-y-3">
          <h3 class="text-lg font-semibold text-slate-300">Camera</h3>
          <div class="grid grid-cols-2 gap-4 items-center">
            <label for="camera-device" class="text-slate-400">Camera Device</label>
            <select id="camera-device" v-model="selectedCamera" class="bg-slate-700 border border-slate-600 rounded-md px-3 py-2 text-white w-full">
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
            <select id="resolution" v-model="resolution" class="bg-slate-700 border border-slate-600 rounded-md px-3 py-2 text-white w-full">
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
            <select id="training-mode" v-model="trainingMode" class="bg-slate-700 border border-slate-600 rounded-md px-3 py-2 text-white w-full">
              <option>Practice</option>
              <option disabled>Guided</option>
            </select>
          </div>
          <div class="grid grid-cols-2 gap-4 items-center">
            <label for="countdown" class="text-slate-400">Countdown</label>
            <select id="countdown" v-model="countdown" class="bg-slate-700 border border-slate-600 rounded-md px-3 py-2 text-white w-full">
              <option :value="0">Off</option>
              <option :value="3">3s</option>
              <option :value="5">5s</option>
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
  background-color: #4f46e5;
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
