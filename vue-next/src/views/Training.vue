<script setup>
import { ref, watch, computed, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router' // Import useRoute
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import TrainingSettings from '../components/TrainingSettings.vue'
import { useMediaPermissions } from '../composables/useMediaPermissions.js'
import { useTrainingSettings } from '../composables/useTrainingSettings.js'
import { useHandTracking } from '../composables/useHandTracking.js'
import { useCollectData } from '../composables/useCollectData.js'
import VideoAnalyzer from '../components/VideoAnalyzer.vue'
//import { useTraining } from '../composables/useTraining.js'


const route = useRoute() // Initialize useRoute
const router = useRouter()

const isTraining = ref(false)
const showSettings = ref(false)
const videoEl = ref(null)
const canvasEl = ref(null)
const actualFps = ref(0)
const trainingMode = ref(null) // 'free' or 'advanced'

// Local loading states for buttons
const isStartingFreeTraining = ref(false)
const isStartingAdvancedTraining = ref(false)

// Refs for VideoAnalyzer data
const videoAnalyzerRef = ref(null)
const currentLightingStatus = ref({ status: '--', colorClass: 'text-slate-400' })
const currentAvgBrightness = ref(0)
const detectedGesture = ref('Waiting...')
const confidence = ref('--%')
const recordingStartCount = ref(0)
const cvFrameId = ref(0)
const hasAutoSavedCurrentRun = ref(false)

// Refs for confidence score calculation
const prevLandmarks = ref(null)
const prevHandedness = ref(null)

// Data collection
const {
  collectedLandmarks,
  isCollecting,
  currentGestureName,
  metadata,
  startCollecting,
  stopCollecting,
  addLandmark,
  downloadCSV,
  clearData
} = useCollectData()

// Check for newGestureName query parameter on component setup
if (route.query.newGestureName) {
  currentGestureName.value = route.query.newGestureName;
  isTraining.value = true; // Automatically start training if a new gesture name is provided
}

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

const { mirrorCamera, enableCamera, showLandmarks, frameLimit } = useTrainingSettings()
const { startHandTracking, stopHandTracking, onFrame } = useHandTracking(mirrorCamera, showLandmarks)


const videoClasses = computed(() => [
  'w-full',
  'h-full',
  'object-cover',
  { '-scale-x-100': mirrorCamera.value },
])


const startTraining = async () => {
  isStartingFreeTraining.value = true
  try {
    await requestPermissions()
    if (hasPermissions.value) {
      isTraining.value = true
      trainingMode.value = 'free'
    }
  } finally {
    isStartingFreeTraining.value = false
  }
}

const startCaptureSession = () => {
  router.push('/capture')
}

const startAdvancedTraining = async () => {
  isStartingAdvancedTraining.value = true
  try {
    await requestPermissions()
    if (hasPermissions.value) {
      isTraining.value = true
      trainingMode.value = 'advanced'
    }
  } finally {
    isStartingAdvancedTraining.value = false
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
  trainingMode.value = null // Reset training mode
}

const startRecording = () => {
  metadata.value.fps = 30
  metadata.value.frame_limit = frameLimit.value
  recordingStartCount.value = collectedLandmarks.value.length
  cvFrameId.value = 0
  hasAutoSavedCurrentRun.value = false
  startCollecting(currentGestureName.value)
}

const resetRecording = () => {
  stopCollecting()
  clearData()
  recordingStartCount.value = 0
  hasAutoSavedCurrentRun.value = false
}

const stopAndAutoSave = () => {
  if (!isCollecting.value || hasAutoSavedCurrentRun.value) return
  stopCollecting()
  hasAutoSavedCurrentRun.value = true
  downloadCSV()
}


watch(
  [isTraining, stream, videoEl, canvasEl, enableCamera],
  async ([training, mediaStream, video, canvas, cameraEnabled]) => {
    if (!training || !cameraEnabled) {
      stopHandTracking()
      stopFpsCounter()
      // Reset states when stopping
      prevLandmarks.value = null
      prevHandedness.value = null
      confidence.value = '--%'
      detectedGesture.value = 'Waiting...'
      return
    }

    if (!mediaStream || !video || !canvas) return

    await nextTick()

    if (video.srcObject !== mediaStream) {
      video.srcObject = mediaStream
      video.play().catch(e => console.error("Error playing video:", e));
    }

    startHandTracking(video, canvas, mediaStream)
    startFpsCounter()
    
    onFrame((results) => {
      frameCount++

      if (isCollecting.value) {
        const framesSinceStart = collectedLandmarks.value.length - recordingStartCount.value
        if (framesSinceStart >= frameLimit.value) {
          stopAndAutoSave()
          return
        }
      }
      
      if (results?.landmarks && results.landmarks.length > 0) {
        detectedGesture.value = 'Hand Detected'
        
        const landmarks = results.landmarks[0]
        const handedness = results.handedness?.[0]?.[0]

        // --- Calculate Composite Confidence Score ---
        
        // 1. Handedness Score (40%)
        const handednessScore = handedness?.score || 0
        
        // 2. Landmark Stability (30%)
        let landmarkStability = 0
        if (prevLandmarks.value) {
          const distances = landmarks.map((point, i) => {
            const prevPoint = prevLandmarks.value[i]
            return Math.sqrt(
              Math.pow(point.x - prevPoint.x, 2) +
              Math.pow(point.y - prevPoint.y, 2) +
              Math.pow(point.z - prevPoint.z, 2)
            )
          })
          const avgDistance = distances.reduce((sum, d) => sum + d, 0) / distances.length
          // Normalize: assume max avg distance of ~0.1 is unstable
          landmarkStability = Math.max(0, 1 - avgDistance * 10)
        } else {
          landmarkStability = 1 // Perfect stability on first frame
        }

        // 3. Visibility (20%) - Proxy via brightness
        const visibility = currentAvgBrightness.value / 255

        // 4. No-Flip Penalty (10%)
        let noFlipPenalty = 1
        if (prevHandedness.value && handedness?.categoryName && handedness.categoryName !== prevHandedness.value) {
          noFlipPenalty = 0 // Apply penalty if handedness flips
        }

        // Final composed score
        const finalScore = 
          0.4 * handednessScore +
          0.3 * landmarkStability +
          0.2 * visibility +
          0.1 * noFlipPenalty
          
        confidence.value = `${Math.round(finalScore * 100)}%`

        // --- End of Confidence Score ---

        // Update prev state for next frame
        prevLandmarks.value = landmarks
        prevHandedness.value = handedness?.categoryName

        // Collect landmarks if recording
        // if (isCollecting.value) {
        //    addLandmark({
        //    landmarks: landmarks,
        //    handedness: handedness?.categoryName || 'Unknown',
        //    confidence: finalScore,
        //    handedness_score: handednessScore,
        //    landmark_stability: landmarkStability,
        //    visibility: visibility,
        //    no_flip_penalty: noFlipPenalty
        //  })
        //}
        if (isCollecting.value) {
          addLandmark(results.landmarks, results.handedness, {
            frame_id: cvFrameId.value,
            timestamp_ms: Date.now()
          })
          cvFrameId.value += 1
        }

      } else {
        detectedGesture.value = 'No Hand Detected'
        confidence.value = '--%'
        prevLandmarks.value = null
        prevHandedness.value = null
        if (isCollecting.value) {
          addLandmark([], [], {
            frame_id: cvFrameId.value,
            timestamp_ms: Date.now()
          })
          cvFrameId.value += 1
        }
      }
    })
  },
  { immediate: true }
)

watch(currentAvgBrightness, (newValue) => {
  console.log('Training: Received avgBrightness:', newValue);
});

watch(currentLightingStatus, (newValue) => {
  console.log('Training: Received lightingStatus:', newValue);
});

watch(
  () => [isCollecting.value, collectedLandmarks.value.length, frameLimit.value],
  ([collecting, frameCountNow, limit]) => {
    if (!collecting) return
    if (frameCountNow - recordingStartCount.value >= limit) {
      stopAndAutoSave()
    }
  }
)
</script>

<template>
  <div class="max-w-4xl mx-auto">
    <TrainingSettings v-if="showSettings" @close="showSettings = false" />

    <div class="mb-8 text-center">
      <h1 class="text-3xl font-bold text-white mb-2">
        {{ trainingMode === 'advanced' ? 'Advanced Training Center' : 'Training Center' }}
      </h1>
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
        <BaseBtn class="mt-4" :disabled="isRequesting" @click="handlePermissionRequest">
          {{ isRequesting ? 'Retrying...' : 'Retry' }}
        </BaseBtn>
      </BaseCard>
    </div>

    <!-- Active Training -->
    <div v-else-if="isTraining && hasPermissions" class="flex flex-col items-center">
      <div v-if="trainingMode === 'free'" class="w-full aspect-video bg-black rounded-2xl border border-slate-700 relative overflow-hidden shadow-2xl">
        <div v-if="!enableCamera" class="absolute inset-0 flex items-center justify-center text-slate-500 bg-black">
          Camera is disabled
        </div>

        <video ref="videoEl" autoplay playsinline muted :class="videoClasses"></video>

        <canvas ref="canvasEl" class="absolute inset-0 w-full h-full"></canvas>
        <!-- VideoAnalyzer component for background processing -->
        <VideoAnalyzer
          v-if="videoEl"
          ref="videoAnalyzerRef"
          :video-el="videoEl"
          class="hidden"
          :mirror-camera="mirrorCamera"
          :show-landmarks="showLandmarks"
          @update:avg-brightness="currentAvgBrightness = $event"
          @update:lighting-status="currentLightingStatus = $event"
        />
        <div class="absolute top-6 left-6 right-6 flex justify-between items-end">
          <div class="bg-black/60 backdrop-blur px-4 py-2 rounded-lg border border-white/10">
            <div class="text-xs text-slate-400">FPS (Target: 30)</div>
            <div class="text-2xl font-bold" :class="actualFps > 0 ? 'text-white' : 'text-slate-500'">
              {{ actualFps || '--' }}
            </div>
          </div>
          <div class="bg-black/60 backdrop-blur px-4 py-2 rounded-lg border border-white/10">
            <div class="text-xs text-slate-400">Condition</div>
            <div class="text-2xl font-bold" :class="currentLightingStatus.colorClass">{{ currentLightingStatus.status }}</div>
          </div>
        </div>
        <div class="absolute bottom-6 left-6 right-6 flex justify-between items-end">
          <div class="bg-black/60 backdrop-blur px-4 py-2 rounded-lg border border-white/10">
            <div class="text-xs text-slate-400">Detected Gesture</div>
            <div class="text-2xl font-bold text-white">{{ detectedGesture }}</div>
          </div>
          <div class="bg-black/60 backdrop-blur px-4 py-2 rounded-lg border border-white/10">
            <div class="text-xs text-slate-400">Confidence</div>
            <div class="text-2xl font-bold text-slate-400">{{ confidence }}</div>
          </div>
        </div>
      </div>

      <div v-else-if="trainingMode === 'advanced'" class="w-full grid grid-cols-2 gap-4 aspect-video">
        <!-- Left Placeholder: 3D Model -->
        <div class="bg-slate-900 rounded-2xl border border-slate-700 relative overflow-hidden shadow-2xl flex items-center justify-center">
          <span class="text-slate-500 text-2xl font-bold">3D Model</span>
        </div>

        <!-- Right Placeholder: Camera Feed -->
        <div class="bg-black rounded-2xl border border-slate-700 relative overflow-hidden shadow-2xl">
          <div v-if="!enableCamera" class="absolute inset-0 flex items-center justify-center text-slate-500 bg-black">
            Camera is disabled
          </div>

          <video ref="videoEl" autoplay playsinline muted :class="videoClasses"></video>

          <canvas ref="canvasEl" class="absolute inset-0 w-full h-full"></canvas>
          <!-- VideoAnalyzer component for background processing -->
          <VideoAnalyzer
            v-if="videoEl"
            ref="videoAnalyzerRef"
            :video-el="videoEl"
            class="hidden"
            :mirror-camera="mirrorCamera"
            :show-landmarks="showLandmarks"
            @update:avg-brightness="currentAvgBrightness = $event"
            @update:lighting-status="currentLightingStatus = $event"
          />
          <div class="absolute top-6 left-6 right-6 flex justify-between items-end">
            <div class="bg-black/60 backdrop-blur px-4 py-2 rounded-lg border border-white/10">
              <div class="text-xs text-slate-400">FPS (Target: 30)</div>
              <div class="text-2xl font-bold" :class="actualFps > 0 ? 'text-white' : 'text-slate-500'">
                {{ actualFps || '--' }}
              </div>
            </div>
            <div class="bg-black/60 backdrop-blur px-4 py-2 rounded-lg border border-white/10">
              <div class="text-xs text-slate-400">Condition</div>
              <div class="text-2xl font-bold" :class="currentLightingStatus.colorClass">{{ currentLightingStatus.status }}</div>
            </div>
          </div>
          <div class="absolute bottom-6 left-6 right-6 flex justify-between items-end">
            <div class="bg-black/60 backdrop-blur px-4 py-2 rounded-lg border border-white/10">
              <div class="text-xs text-slate-400">Detected Gesture</div>
              <div class="text-2xl font-bold text-white">{{ detectedGesture }}</div>
            </div>
            <div class="bg-black/60 backdrop-blur px-4 py-2 rounded-lg border border-white/10">
              <div class="text-xs text-slate-400">Confidence</div>
              <div class="text-2xl font-bold text-slate-400">{{ confidence }}</div>
            </div>
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
            class="w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white focus:border-teal-500 focus:outline-none"
            :disabled="isCollecting"
          />
        </div>

        <div class="flex flex-wrap gap-3">
          <BaseBtn 
            v-if="!isCollecting"
            :disabled="!currentGestureName.trim()"
            variant="primary"
            @click="startRecording"
          >
            Start Recording
          </BaseBtn>
          <BaseBtn 
            v-else
            variant="danger"
            @click="stopCollecting"
          >
            Stop Recording  
          </BaseBtn>
          
          <BaseBtn 
            :disabled="collectedLandmarks.length === 0"
            variant="secondary"
            @click="downloadCSV"
          >
            Download CSV
          </BaseBtn>
          
          <BaseBtn 
            :disabled="collectedLandmarks.length === 0"
            variant="secondary"
            @click="clearData"
          >
            Clear Data
          </BaseBtn>
          
          <BaseBtn 
            variant="secondary"
            @click="resetRecording"
          >
            Reset
          </BaseBtn>
        </div>

        <div class="mt-4 text-sm">
          <div v-if="isCollecting" class="text-green-400 font-semibold">
            Recording "{{ currentGestureName }}"...
          </div>
          <div class="text-slate-400">
            Frames collected: <span class="text-white font-bold">{{ collectedLandmarks.length - recordingStartCount }}</span>
            <span class="text-slate-500"> / {{ frameLimit }}</span>
          </div>
        </div>
      </BaseCard>
    </div>

    <!-- Initial State -->
    <div v-else class="grid grid-cols-1 md:grid-cols-3 gap-8 mt-12">
      <BaseCard class="group hover:border-teal-400/50 transition-colors cursor-pointer card" @click="startTraining">
        <div
          class="h-48 bg-slate-800/50 rounded-lg mb-6 flex items-center justify-center text-slate-600 group-hover:text-teal-400 transition-colors">
          <span class="text-5xl">▶</span>
        </div>
        <h3 class="text-xl font-bold text-white mb-2">
          Free Practice
        </h3>
        <p class="text-slate-400 text-sm mb-6">
          Practice any gesture freely with real-time analysis and feedback.
        </p>
        <BaseBtn class="w-full" :disabled="isStartingFreeTraining || isRequesting">
          {{ isStartingFreeTraining ? 'Requesting...' : 'Start Session' }}
        </BaseBtn>
      </BaseCard>

      <BaseCard class="group hover:border-teal-400/50 transition-colors cursor-pointer card" @click="startCaptureSession">
        <div
          class="h-48 bg-slate-800/50 rounded-lg mb-6 flex items-center justify-center text-slate-600 group-hover:text-teal-400 transition-colors">
          <span class="text-5xl">●</span>
        </div>
        <h3 class="text-xl font-bold text-white mb-2">
          Capture Session
        </h3>
        <p class="text-slate-400 text-sm mb-6">
          Record a labeled gesture with sensor and CV data.
        </p>
        <BaseBtn class="w-full">
          Start Capture
        </BaseBtn>
      </BaseCard>

      <BaseCard class="group opacity-50 cursor-not-allowed card">
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

      <BaseCard class="group hover:border-teal-400/50 transition-colors cursor-pointer card" @click="startAdvancedTraining">
        <div class="h-48 bg-slate-800/50 rounded-lg mb-6 flex items-center justify-center text-slate-600 group-hover:text-teal-400">
          <span class="text-5xl">★</span>
        </div>
        <h3 class="text-xl font-bold text-white mb-2">
          Advanced Practice
        </h3>
        <p class="text-slate-400 text-sm mb-6">
          Followed by AI guidance and real-time 3D modelling.
        </p>
        <BaseBtn variant="primary" class="w-full" :disabled="isStartingAdvancedTraining || isRequesting">
          {{ isStartingAdvancedTraining ? 'Requesting...' : 'Start Advanced Session' }}
        </BaseBtn>
      </BaseCard>
    </div>
  </div>
</template>
