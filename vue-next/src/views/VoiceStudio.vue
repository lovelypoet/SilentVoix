<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '../services/api'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'

// State
const activeTab = ref('tts') // Default to TTS
const isLoading = ref(false)
const error = ref(null)

// --- TTS State ---
const ttsText = ref('')
const ttsStatus = ref(null)
const ttsEngine = ref('gtts')

// --- Audio Library State ---
const audioFiles = ref([])
const isDragging = ref(false)
const fileInput = ref(null)

// ===================== COMPUTED =====================
const filteredFiles = computed(() => {
  return audioFiles.value
})

// ===================== LIFECYCLE =====================
onMounted(async () => {
  await fetchAudioFiles()
})



// ===================== TTS ACTIONS =====================
const speakText = async () => {
  if (!ttsText.value) return
  
  // OS / Browser TTS
  if (ttsEngine.value === 'os') {
    if (!('speechSynthesis' in window)) {
      error.value = 'Text-to-speech is not supported in this browser.'
      return
    }
    
    // Stop any existing speech
    window.speechSynthesis.cancel()
    
    const utterance = new SpeechSynthesisUtterance(ttsText.value)
    
    // Setup event handlers
    utterance.onstart = () => {
      ttsStatus.value = 'Playing (Local)...'
    }
    
    utterance.onend = () => {
      ttsStatus.value = 'Played successfully'
      setTimeout(() => { ttsStatus.value = null }, 3000)
    }
    
    utterance.onerror = (e) => {
      console.error('TTS Error:', e)
      error.value = 'Local playback failed'
      ttsStatus.value = null
    }
    
    // Speak
    window.speechSynthesis.speak(utterance)
    return
  }

  // Google TTS (Server)
  try {
    isLoading.value = true
    ttsStatus.value = 'Generating audio...'
    // Call API (playOnLaptop = false)
    const res = await api.utils.tts.speakTest(ttsText.value, false)
    
    // Check res directly (interceptors return response.data)
    if (res.status === 'success' && res.audio_url) {
      ttsStatus.value = 'Playing...'
      const audio = new Audio(res.audio_url)
      await audio.play()
      ttsStatus.value = 'Played successfully'
    } else {
      throw new Error('No audio URL returned')
    }
    
    setTimeout(() => { ttsStatus.value = null }, 3000)
  } catch (err) {
    const msg = err.response?.data?.detail || err.message || 'Failed to play audio'
    error.value = `Error: ${msg}`
    console.error(err)
  } finally {
    isLoading.value = false
  }
}

// ===================== LIBRARY ACTIONS =====================
const fetchAudioFiles = async () => {
  try {
    isLoading.value = true
    const files = await api.audio.getAll()
    audioFiles.value = files
  } catch (err) {
    console.error('Failed to fetch audio files:', err)
    // Don't set error here to avoid blocking TTS usage if just audio files fail
  } finally {
    isLoading.value = false
  }
}

const playOnGlove = async (filename) => {
  try {
    await api.audio.playESP32(filename)
    alert(`Playing ${filename} on Glove...`)
  } catch {
    alert('Failed to play on glove')
  }
}

const playOnLaptop = async (filename) => {
    try {
        await api.audio.playLaptop(filename)
    } catch {
        alert('Failed to play on laptop')
    }
}

const deleteFile = async (filename) => {
  if (!confirm(`Delete ${filename}?`)) return
  try {
    await api.audio.delete(filename)
    await fetchAudioFiles()
  } catch {
    alert('Failed to delete file')
  }
}

const triggerUpload = () => fileInput.value.click()

const handleFileUpload = async (event) => {
  const file = event.target.files[0]
  if (!file) return
  await uploadFile(file)
}

const onDrop = async (event) => {
  isDragging.value = false
  const file = event.dataTransfer.files[0]
  if (file && file.type.startsWith('audio/')) {
    await uploadFile(file)
  }
}

const uploadFile = async (file) => {
  try {
    isLoading.value = true
    await api.audio.upload(file, 'web-user')
    await fetchAudioFiles()
  } catch {
    alert('Upload failed')
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header with Tabs -->
    <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
      <div>
        <h1 class="text-2xl font-bold text-white mb-2">Voice Studio</h1>
        <p class="text-slate-400">Manage audio, speech-to-text, and TTS capabilities.</p>
      </div>
      
      <!-- Tab Navigation -->
      <div class="flex bg-slate-800 p-1 rounded-lg">
        <button 
          v-for="tab in ['tts', 'library', 'live']" 
          :key="tab"
          class="px-4 py-2 rounded-md text-sm font-medium transition-colors"
          :class="activeTab === tab ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-white'"
          @click="activeTab = tab"
        >
          {{ tab === 'tts' ? 'Text to Speech' : tab === 'library' ? 'Audio Library' : 'Live Voice' }}
        </button>
      </div>
    </div>

    <!-- Error Alert -->
    <div v-if="error" class="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-lg flex justify-between items-center relative">
      <span>{{ error }}</span>
      <button class="text-sm hover:text-white absolute right-4" @click="error = null">&times;</button>
    </div>

    <!-- ===================== TTS TAB ===================== -->
    <div v-if="activeTab === 'tts'" class="space-y-6">
      <BaseCard title="Text to Speech Engine">
        <div class="space-y-6">
          <!-- Engine Selector -->
          <div class="flex gap-4">
            <div class="inline-flex bg-slate-900 p-1 rounded-lg border border-slate-700">
               <button 
                 class="px-4 py-2 rounded-md text-sm font-medium transition-all"
                 :class="ttsEngine === 'gtts' ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-400 hover:text-white'"
                 @click="ttsEngine = 'gtts'"
               >
                 GTTS
               </button>
               <button 
                 class="px-4 py-2 rounded-md text-sm font-medium transition-all"
                 :class="ttsEngine === 'os' ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-400 hover:text-white'"
                 @click="ttsEngine = 'os'"
               >
                 Device Default
               </button>
            </div>
            <div class="flex items-center text-xs text-slate-500">
                <i class="ph ph-info mr-1"></i>
                {{ ttsEngine === 'gtts' ? 'It\'s on lystiger' : 'It\'s on your device' }}
            </div>
          </div>

          <!-- Input Area -->
          <div class="space-y-2">
            <label class="text-sm font-medium text-slate-300">Enter text to speak</label>
            <textarea 
              v-model="ttsText"
              rows="4"
              class="w-full bg-slate-900 border border-slate-700 rounded-lg p-4 text-white placeholder-slate-600 focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 transition-all resize-none"
              placeholder="Type something here (e.g., 'Hello, how can I help you?')..."
            ></textarea>
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-4">
            <BaseBtn :disabled="!ttsText || isLoading" class="flex items-center gap-2" @click="speakText">
              <i class="ph ph-laptop text-lg"></i>
              Play
            </BaseBtn>
            
            <div v-if="ttsStatus" class="text-sm text-teal-300 animate-pulse">
              {{ ttsStatus }}
            </div>
          </div>
        </div>
      </BaseCard>
    </div>

    <!-- ===================== LIBRARY TAB ===================== -->
    <div v-if="activeTab === 'library'" class="space-y-6">
        <!-- New Upload Zone -->
      <div 
        class="border-2 border-dashed rounded-xl p-8 text-center transition-all cursor-pointer group" 
        :class="isDragging ? 'border-indigo-500 bg-indigo-500/10' : 'border-slate-700 hover:border-indigo-500/50 hover:bg-slate-800/50'" 
        @dragover.prevent="isDragging = true"
        @dragleave.prevent="isDragging = false"
        @drop.prevent="onDrop"
        @click="triggerUpload"
        class="border-2 border-dashed rounded-xl p-8 text-center transition-all cursor-pointer group"
        :class="isDragging ? 'border-teal-500 bg-teal-500/10' : 'border-slate-700 hover:border-teal-500/50 hover:bg-slate-800/50'"
      >
        <input ref="fileInput" type="file" class="hidden" accept="audio/*" @change="handleFileUpload">
        <div class="flex flex-col items-center gap-3">
          <div class="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center group-hover:bg-teal-500/20 transition-colors">
            <i class="ph ph-upload-simple text-2xl text-slate-400 group-hover:text-teal-300"></i>
          </div>
          <div>
            <h3 class="font-medium text-white mb-1">Upload Audio File</h3>
            <p class="text-sm text-slate-500">Drag & drop or click to browse (MP3, WAV)</p>
          </div>
        </div>
      </div>

      <!-- File List -->
      <div v-if="audioFiles.length === 0 && !isLoading" class="text-center py-12">
        <div class="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center mx-auto mb-4">
            <i class="ph ph-music-notes text-3xl text-slate-500"></i>
        </div>
        <h3 class="text-lg font-medium text-white mb-1">No audio files found</h3>
        <p class="text-slate-500">Upload a file to get started</p>
      </div>

      <div v-else class="grid grid-cols-1 gap-4">
        <BaseCard v-for="file in filteredFiles" :key="file.filename" class="group hover:border-teal-400/30 transition-colors">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-4">
              <div class="w-10 h-10 rounded-lg bg-teal-500/10 flex items-center justify-center text-teal-300">
                <i class="ph ph-file-audio text-xl"></i>
              </div>
              <div>
                <h3 class="font-medium text-white group-hover:text-teal-200 transition-colors">{{ file.filename }}</h3>
                <div class="text-xs text-slate-500 flex items-center gap-2">
                  <span>{{ new Date(file.upload_time).toLocaleDateString() }}</span>
                  <span>•</span>
                  <span>{{ (file.size / 1024 / 1024).toFixed(2) }} MB</span> <!-- Mock size if not real -->
                </div>
              </div>
            </div>
            
            <div class="flex items-center gap-2">
              <button @click="playOnGlove(file.filename)" class="p-2 rounded-lg hover:bg-teal-500/20 text-slate-400 hover:text-teal-300 transition-colors" title="Play on Glove">
                <i class="ph ph-speaker-high text-xl"></i>
              </button>
              <button @click="playOnLaptop(file.filename)" class="p-2 rounded-lg hover:bg-teal-500/20 text-slate-400 hover:text-teal-300 transition-colors" title="Play on Laptop">
                <i class="ph ph-laptop text-xl"></i>
              </button>
              <button class="p-2 rounded-lg hover:bg-red-500/20 text-slate-400 hover:text-red-400 transition-colors" title="Delete" @click="deleteFile(file.filename)">
                <i class="ph ph-trash text-xl"></i>
              </button>
            </div>
          </div>
        </BaseCard>
      </div>
    </div>

    <!-- ===================== LIVE VOICE TAB (Placeholder) ===================== -->
    <div v-if="activeTab === 'live'" class="text-center py-20">
      <div class="w-20 h-20 bg-slate-800 rounded-full flex items-center justify-center mx-auto mb-6">
        <i class="ph ph-microphone text-4xl text-slate-500"></i>
      </div>
      <h2 class="text-xl font-bold text-white mb-2">Live Speech Recognition</h2>
      <p class="text-slate-400 max-w-md mx-auto">
        This feature will allow you to stream audio from your microphone directly to the backend for real-time transcription.
      </p>
      <BaseBtn variant="secondary" class="mt-6" disabled>Coming Soon</BaseBtn>
    </div>

  </div>
</template>
