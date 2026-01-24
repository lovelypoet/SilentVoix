<script setup>
import { ref, watch, computed, nextTick } from 'vue'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import TrainingSettings from '../components/TrainingSettings.vue'
import { useMediaPermissions } from '../composables/useMediaPermissions.js'
import { useTrainingSettings } from '../composables/useTrainingSettings.js'
import { useHandTracking } from '../composables/useHandTracking.js'
import { useCollectData } from '../composables/useCollectData.js'


const isTraining = ref(false)
const showSettings = ref(false)
const videoEl = ref(null)
const canvasEl = ref(null)
const actualFps = ref(0)

// FPS calculation
let frameCount = 0
let lastTime = performance.now()
let fpsInterval = null

const calculateFps = () => {
  frameCount++
  const currentTime = performance.now()
  const elapsed = currentTime - lastTime
  
  // Update FPS every second
  if (elapsed >= 1000) {
    actualFps.value = Math.round((frameCount * 1000) / elapsed)
    frameCount = 0
    lastTime = currentTime
  }
}

const startFpsCounter = () => {
  frameCount = 0
  lastTime = performance.now()
  actualFps.value = 0
  
  fpsInterval = setInterval(() => {
    calculateFps()
  }, 100) // Check every 100ms for smoother updates
}

const stopFpsCounter = () => {
  if (fpsInterval) {
    clearInterval(fpsInterval)
    fpsInterval = null
  }
  actualFps.value = 0
  frameCount = 0
}


const {
  hasPermissions,
  isRequesting,
  error,
  stream,
  requestPermissions,
  stopStream
} = useMediaPermissions()

const { mirrorCamera, enableCamera, showLandmarks, fps } = useTrainingSettings()
const { startHandTracking, stopHandTracking, onFrame } = useHandTracking(mirrorCamera, showLandmarks)

// Data collection
const {
  collectedLandmarks,
  isCollecting,
  currentGestureName,
  startCollecting,
  stopCollecting,
  addLandmark,
  downloadCSV,
  clearData
} = useCollectData()


const videoClasses = computed(() => [
  'w-full',
  'h-full',
  'object-cover',
  { '-scale-x-100': mirrorCamera.value },
])


const startTraining = async () => {
  await requestPermissions()
  if (hasPermissions.value) {
    isTraining.value = true
  }
}

const handlePermissionRequest = async () => {
  await requestPermissions()
  if (hasPermissions.value) {
    isTraining.value = true
  }
}

const stopTraining = () => {
  stopHandTracking()
  stopFpsCounter()
  stopStream()
  isTraining.value = false
  showSettings.value = false
}


watch(
  [isTraining, stream, videoEl, canvasEl, enableCamera],
  async ([training, mediaStream, video, canvas, cameraEnabled]) => {
    if (!training || !cameraEnabled) {
      stopHandTracking()
      stopFpsCounter()
      return
    }

    if (!mediaStream || !video || !canvas) return

    await nextTick()

    if (video.srcObject !== mediaStream) {
      video.srcObject = mediaStream
    }

    startHandTracking(video, canvas, mediaStream)
    startFpsCounter()
    
    onFrame((results) => {
      frameCount++
      
      // Collect landmarks nếu đang recording
      if (results.landmarks && results.landmarks.length > 0) {
        const landmarks = results.landmarks[0] // First hand
        const handedness = results.handedness?.[0]?.[0]?.categoryName || 'Right'
        addLandmark(landmarks, handedness)
      }
    })
  },
  { immediate: true }
)
</script>

<template>
  <div class="max-w-4xl mx-auto">
    <TrainingSettings v-if="showSettings" @close="showSettings = false" />

    <div class="mb-8 text-center">
      <h1 class="text-3xl font-bold text-white mb-2">Training Center</h1>
      <p class="text-slate-400">
        Master your sign language gestures with real-time feedback
      </p>
    </div>

    <!-- Permissions Denied -->
    <div v-if="error" class="text-center mt-12">
      <BaseCard class="max-w-md mx-auto">
        <h3 class="text-xl font-bold text-red-400 mb-2">
          Permissions Required
        </h3>
        <p class="text-slate-400 mb-4">
          Camera access is required for training. Please grant permissions in
          your browser settings.
        </p>
        <p class="text-xs text-slate-500">
          Error: {{ error.name }} - {{ error.message }}
        </p>
        <BaseBtn @click="handlePermissionRequest" class="mt-4" :disabled="isRequesting">
          {{ isRequesting ? 'Retrying...' : 'Retry' }}
        </BaseBtn>
      </BaseCard>
    </div>

    <!-- Active Training -->
    <div v-else-if="isTraining && hasPermissions" class="flex flex-col items-center">
      <div class="w-full aspect-video bg-black rounded-2xl border border-slate-700 relative overflow-hidden shadow-2xl">
        <div v-if="!enableCamera" class="absolute inset-0 flex items-center justify-center text-slate-500 bg-black">
          Camera is disabled
        </div>

        <video ref="videoEl" autoplay playsinline muted :class="videoClasses"></video>

        <canvas ref="canvasEl" class="absolute inset-0 w-full h-full"></canvas>
        <div class="absolute top-6 left-6 right-6 flex justify-between items-end">
          <div class="bg-black/60 backdrop-blur px-4 py-2 rounded-lg border border-white/10">
            <div class="text-xs text-slate-400">FPS (Target: {{ fps }})</div>
            <div class="text-2xl font-bold" :class="actualFps > 0 ? 'text-white' : 'text-slate-500'">
              {{ actualFps || '--' }}
            </div>
          </div>
          <div class="bg-black/60 backdrop-blur px-4 py-2 rounded-lg border border-white/10">
            <div class="text-xs text-slate-400">Condition</div>
            <div class="text-2xl font-bold text-slate-400">Too dark</div>
          </div>
        </div>
        <div class="absolute bottom-6 left-6 right-6 flex justify-between items-end">
          <div class="bg-black/60 backdrop-blur px-4 py-2 rounded-lg border border-white/10">
            <div class="text-xs text-slate-400">Detected Gesture</div>
            <div class="text-2xl font-bold text-white">Waiting...</div>
          </div>
          <div class="bg-black/60 backdrop-blur px-4 py-2 rounded-lg border border-white/10">
            <div class="text-xs text-slate-400">Confidence</div>
            <div class="text-2xl font-bold text-slate-400">--%</div>
          </div>
        </div>
      </div>

      <div class="flex gap-4 mt-8">
        <BaseBtn variant="danger" @click="stopTraining">
          End Session
        </BaseBtn>
        <BaseBtn variant="secondary" @click="showSettings = true">
          Settings
        </BaseBtn>
        <BaseBtn variant="primary">
          Start Training
        </BaseBtn>
      </div>

      <!-- Data Collection Panel -->
      <BaseCard class="w-full mt-8">
        <h3 class="text-lg font-bold text-white mb-4">Data Collection Session</h3>
        
        <div class="mb-4">
          <label class="block text-sm text-slate-400 mb-2">Gesture Name</label>
          <input 
            v-model="currentGestureName"
            type="text" 
            placeholder="e.g., hello, thanks, yes, no"
            class="w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white focus:border-indigo-500 focus:outline-none"
            :disabled="isCollecting"
          />
        </div>

        <div class="flex flex-wrap gap-3">
          <BaseBtn 
            v-if="!isCollecting"
            @click="startCollecting(currentGestureName)"
            :disabled="!currentGestureName.trim()"
            variant="primary"
          >
            Start Recording
          </BaseBtn>
          <BaseBtn 
            v-else
            @click="stopCollecting"
            variant="danger"
          >
            Stop Recording  
          </BaseBtn>
          
          <BaseBtn 
            @click="downloadCSV"
            :disabled="collectedLandmarks.length === 0"
            variant="secondary"
          >
            Download CSV
          </BaseBtn>
          
          <BaseBtn 
            @click="clearData"
            :disabled="collectedLandmarks.length === 0"
            variant="secondary"
          >
            Clear Data
          </BaseBtn>
        </div>

        <div class="mt-4 text-sm">
          <div v-if="isCollecting" class="text-green-400 font-semibold">
            Recording "{{ currentGestureName }}"...
          </div>
          <div class="text-slate-400">
            Frames collected: <span class="text-white font-bold">{{ collectedLandmarks.length }}</span>
          </div>
        </div>
      </BaseCard>
    </div>

    <!-- Initial State -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-8 mt-12">
      <BaseCard class="group hover:border-indigo-500/50 transition-colors cursor-pointer" @click="startTraining">
        <div
          class="h-48 bg-slate-800/50 rounded-lg mb-6 flex items-center justify-center text-slate-600 group-hover:text-indigo-500 transition-colors">
          <span class="text-5xl">▶</span>
        </div>
        <h3 class="text-xl font-bold text-white mb-2">
          Free Practice
        </h3>
        <p class="text-slate-400 text-sm mb-6">
          Practice any gesture freely with real-time analysis and feedback.
        </p>
        <BaseBtn class="w-full" :disabled="isRequesting">
          {{ isRequesting ? 'Requesting...' : 'Start Session' }}
        </BaseBtn>
      </BaseCard>

      <BaseCard class="group opacity-50 cursor-not-allowed">
        <div class="h-48 bg-slate-800/50 rounded-lg mb-6 flex items-center justify-center text-slate-600">
          <span class="text-5xl">★</span>
        </div>
        <h3 class="text-xl font-bold text-white mb-2">
          Guided Lessons
        </h3>
        <p class="text-slate-400 text-sm mb-6">
          Step-by-step curriculum to learn from basics to advanced signs.
        </p>
        <BaseBtn variant="secondary" class="w-full" disabled>
          Start Lesson 1
        </BaseBtn>
      </BaseCard>
    </div>
  </div>
</template>