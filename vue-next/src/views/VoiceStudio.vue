<script setup>
import { ref, onMounted } from 'vue'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import api from '../services/api'

const audioFiles = ref([])
const isLoading = ref(false)
const fileInput = ref(null) // Ref for the hidden file input

const triggerFileInput = () => {
  fileInput.value.click()
}

const handleFileChange = (event) => {
  const file = event.target.files[0]
  if (file) {
    console.log('Selected file:', file.name, file);
    // Here you would typically handle the file upload, e.g., call an API
  }
}

const fetchAudio = async () => {
  isLoading.value = true
  try {
    // Mock data for now if API fails (since backend might not be up)
    // audioFiles.value = await api.audio.getAll()
    // For prototype demonstration:
    const res = await api.audio.getAll().catch(() => [])
    audioFiles.value = Array.isArray(res) ? res : []
  } catch (e) {
    console.error(e)
  } finally {
    isLoading.value = false
  }
}

const playOnGlove = async (filename) => {
  try {
    await api.audio.playESP32(filename)
  } catch (e) {
    alert('Failed to play on glove (Mock: Playing beep...)')
  }
}

onMounted(() => {
  fetchAudio()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex justify-between items-center">
      <div>
        <h1 class="text-3xl font-bold text-white">Voice Studio</h1>
        <p class="text-slate-400">Manage and test audio feedback files</p>
      </div>
      <BaseBtn variant="primary" @click="triggerFileInput">Upload Audio</BaseBtn>
      <input type="file" ref="fileInput" accept="audio/*" style="display: none;" @change="handleFileChange">
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <BaseCard v-for="file in audioFiles" :key="file.filename" class="flex flex-col justify-between">
        <div class="flex items-start justify-between mb-4">
          <div class="p-3 rounded-lg bg-indigo-500/20 text-indigo-400">
            <!-- Icon -->
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 256 256"><path fill="currentColor" d="M128 24a104 104 0 1 0 104 104A104.11 104.11 0 0 0 128 24m0 192a88 88 0 1 1 88-88a88.1 88.1 0 0 1-88 88m48-88a48 48 0 0 1-48 48a48 48 0 0 1-48-48a48 48 0 0 1 48-48a48 48 0 0 1 48 48"/></svg>
          </div>
          <button class="text-slate-500 hover:text-red-500 transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 256 256"><path fill="currentColor" d="M216 48h-40v-8a24 24 0 0 0-24-24h-48a24 24 0 0 0-24 24v8H40a8 8 0 0 0 0 16h8v144a16 16 0 0 0 16 16h128a16 16 0 0 0 16-16V64h8a8 8 0 0 0 0-16M96 40a8 8 0 0 1 8-8h48a8 8 0 0 1 8 8v8H96Zm96 168H64V64h128Zm-80-104v64a8 8 0 0 1-16 0v-64a8 8 0 0 1 16 0m48 0v64a8 8 0 0 1-16 0v-64a8 8 0 0 1 16 0"/></svg>
          </button>
        </div>
        
        <div>
          <h3 class="text-white font-medium truncate" :title="file.filename">{{ file.filename }}</h3>
          <p class="text-xs text-slate-500 mt-1">Uploaded by {{ file.uploader }}</p>
        </div>

        <div class="mt-6 flex gap-2">
          <BaseBtn class="flex-1 text-sm py-2" @click="playOnGlove(file.filename)">Play on Glove</BaseBtn>
          <BaseBtn variant="secondary" class="flex-1 text-sm py-2">Preview</BaseBtn>
        </div>
      </BaseCard>
      
      <!-- Upload Placeholder -->
      <BaseCard class="border-dashed border-2 border-slate-700 bg-transparent hover:bg-slate-900/50 hover:border-indigo-500/50 transition flex flex-col items-center justify-center cursor-pointer min-h-[200px] group">
          <div class="text-slate-600 group-hover:text-indigo-500 mb-2">
            <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 256 256"><path fill="currentColor" d="M216 152a8 8 0 0 1-8 8H48a8 8 0 0 1 0-16h160a8 8 0 0 1 8 8m-80-8a8 8 0 0 0 8-8V88h28.69L134.34 49.37a8 8 0 0 0-12.68 0L83.31 88H112v48a8 8 0 0 0 8 8"/></svg>
          </div>
          <span class="text-slate-400 font-medium">Drop audio files here</span>
      </BaseCard>
      <BaseCard v-if="audioFiles.length === 0" class="col-span-full p-8 text-center text-slate-500">
        No audio files found.
      </BaseCard>
    </div>
  </div>
</template>
