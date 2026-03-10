<script setup>
import { ref, watch, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router' // Import useRoute
import { useAuthStore } from '../stores/auth'
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
const authStore = useAuthStore()
const canAccessFusionWorkspace = computed(() => ['editor', 'admin'].includes(authStore.user?.role))

const isTraining = ref(false)
const showSettings = ref(false)
const videoEl = ref(null)
const canvasEl = ref(null)
const actualFps = ref(0)
const trainingMode = ref(null) // 'free' or 'advanced'
const trainingCardsScroller = ref(null)
const isDraggingCards = ref(false)
const hasDraggedCards = ref(false)
const suppressNextCardClick = ref(false)
const dragStartX = ref(0)
const dragStartScrollLeft = ref(0)
const isAdjustingInfiniteScroll = ref(false)
const dragLastX = ref(0)
const dragLastTime = ref(0)
const dragVelocityPerFrame = ref(0)
const activeDragPointerId = ref(null)
const hasPointerCapture = ref(false)
let momentumAnimationFrameId = null
let momentumVelocityPerFrame = 0

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
  takeLogs,
  startCollecting,
  stopCollecting,
  addLandmark,
  downloadCSV,
  prepareAutoDownloadFolder,
  clearData
} = useCollectData()

// Check for newGestureName query parameter on component setup
if (route.query.newGestureName) {
  currentGestureName.value = route.query.newGestureName;
  isTraining.value = true; // Automatically start training if a new gesture name is provided
}

const syncTrainingSessionRouteState = async (active) => {
  const targetValue = active ? '1' : undefined
  if (route.query.trainingSession === targetValue) return

  const nextQuery = { ...route.query }
  if (active) {
    nextQuery.trainingSession = '1'
  } else {
    delete nextQuery.trainingSession
  }

  await router.replace({ path: route.path, query: nextQuery })
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

const trainingCards = computed(() => {
  const cards = [
    {
      id: 'free-practice',
      icon: '▶',
      title: 'Free Practice',
      description: 'Practice any gesture freely with real-time analysis and feedback.',
      buttonLabel: isStartingFreeTraining.value ? 'Requesting...' : 'Start Session',
      buttonVariant: 'primary',
      disabled: isStartingFreeTraining.value || isRequesting.value,
      locked: false,
      onClick: startTraining
    },
    {
      id: 'realtime-ai-playground',
      icon: '◉',
      title: 'Realtime AI Playground',
      description: 'Plug in exported models and test live CV inference with overlays.',
      buttonLabel: 'Open Playground',
      buttonVariant: 'primary',
      disabled: false,
      locked: false,
      onClick: startRealtimePlayground
    },
    {
      id: 'video-library',
      icon: '▣',
      title: 'Video Library',
      description: 'Upload a video, process it, and keep up to 5 results for the playground.',
      buttonLabel: 'Open Video Library',
      buttonVariant: 'primary',
      disabled: false,
      locked: false,
      onClick: startVideoLibrary
    },
    {
      id: 'advanced-practice',
      icon: '★',
      title: 'Advanced Practice',
      description: 'Followed by AI guidance and real-time 3D modelling.',
      buttonLabel: isStartingAdvancedTraining.value ? 'Requesting...' : 'Start Advanced Session',
      buttonVariant: 'primary',
      disabled: isStartingAdvancedTraining.value || isRequesting.value,
      locked: false,
      onClick: startAdvancedTraining
    }
  ]

  if (canAccessFusionWorkspace.value) {
    cards.splice(1, 0, {
      id: 'sensor-training',
      icon: '⬢',
      title: 'Sensor Training',
      description: 'Open glove-only capture and training workflows for sensor datasets.',
      buttonLabel: 'Open Sensor Training',
      buttonVariant: 'primary',
      disabled: false,
      locked: false,
      onClick: startSensorTraining
    })

    cards.splice(2, 0, {
      id: 'fusion-workspace',
      icon: '◆',
      title: 'Fusion Workspace',
      description: 'Open dedicated Early/Late Fusion modules from one page.',
      buttonLabel: 'Open Fusion',
      buttonVariant: 'primary',
      disabled: false,
      locked: false,
      onClick: startFusionWorkspace
    })
  }

  return cards
})


const startTraining = async () => {
  isStartingFreeTraining.value = true
  try {
    enableCamera.value = true
    await requestPermissions()
    if (hasPermissions.value) {
      isTraining.value = true
      trainingMode.value = 'free'
    }
  } finally {
    isStartingFreeTraining.value = false
  }
}

const startFusionWorkspace = () => {
  router.push('/fusion')
}

const startSensorTraining = () => {
  router.push('/sensor-training')
}

const startRealtimePlayground = () => {
  router.push('/realtime-ai-playground')
}

const startVideoLibrary = () => {
  router.push('/video-library')
}

const startAdvancedTraining = async () => {
  isStartingAdvancedTraining.value = true
  try {
    enableCamera.value = true
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

const resetLiveFeedback = () => {
  prevLandmarks.value = null
  prevHandedness.value = null
  confidence.value = '--%'
  detectedGesture.value = 'Waiting...'
}

const endTrainingSession = () => {
  if (isCollecting.value) {
    stopCollecting()
  }
  enableCamera.value = false
  stopHandTracking()
  stopFpsCounter()
  stopStream()
  resetLiveFeedback()
}

const returnToTrainingCards = () => {
  endTrainingSession()
  isTraining.value = false
  showSettings.value = false
  trainingMode.value = null // Reset training mode
}

const startRecording = async () => {
  try {
    await prepareAutoDownloadFolder()
  } catch (error) {
    console.warn('Folder picker skipped or unavailable, fallback to file downloads.', error)
  }
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
  resetRecording()
}

const clamp = (value, min, max) => Math.min(max, Math.max(min, value))

const stopTrainingCardsMomentum = () => {
  if (momentumAnimationFrameId) {
    cancelAnimationFrame(momentumAnimationFrameId)
    momentumAnimationFrameId = null
  }
  momentumVelocityPerFrame = 0
}

const startTrainingCardsMomentum = (initialVelocityPerFrame) => {
  const scroller = trainingCardsScroller.value
  if (!scroller) return
  if (scroller.scrollWidth <= scroller.clientWidth) return

  momentumVelocityPerFrame = clamp(initialVelocityPerFrame, -80, 80)
  if (Math.abs(momentumVelocityPerFrame) < 0.4) return

  if (momentumAnimationFrameId) return

  const step = () => {
    const el = trainingCardsScroller.value
    if (!el || isDraggingCards.value) {
      stopTrainingCardsMomentum()
      return
    }

    el.scrollLeft += momentumVelocityPerFrame
    normalizeInfiniteTrainingCardsScroll()
    momentumVelocityPerFrame *= 0.92

    if (Math.abs(momentumVelocityPerFrame) < 0.35) {
      stopTrainingCardsMomentum()
      return
    }

    momentumAnimationFrameId = requestAnimationFrame(step)
  }

  momentumAnimationFrameId = requestAnimationFrame(step)
}

const handleTrainingCardsWheel = (event) => {
  const scroller = trainingCardsScroller.value
  if (!scroller) return
  if (scroller.scrollWidth <= scroller.clientWidth) return

  stopTrainingCardsMomentum()

  const delta = clamp(event.deltaY, -120, 120)
  const immediateStep = delta * 0.85
  const velocityBoost = delta * 0.18

  const previousLeft = scroller.scrollLeft
  scroller.scrollLeft += immediateStep

  if (scroller.scrollLeft !== previousLeft) {
    normalizeInfiniteTrainingCardsScroll()
    startTrainingCardsMomentum(velocityBoost)
    event.preventDefault()
  }
}

const normalizeInfiniteTrainingCardsScroll = () => {
  const scroller = trainingCardsScroller.value
  if (!scroller) return
  if (scroller.scrollWidth <= scroller.clientWidth) return

  const segmentWidth = scroller.scrollWidth / 3
  if (!segmentWidth || !Number.isFinite(segmentWidth)) return

  const current = scroller.scrollLeft
  const lowerBound = segmentWidth * 0.5
  const upperBound = segmentWidth * 1.5

  if (current < lowerBound) {
    isAdjustingInfiniteScroll.value = true
    scroller.scrollLeft = current + segmentWidth
    requestAnimationFrame(() => {
      isAdjustingInfiniteScroll.value = false
    })
  } else if (current > upperBound) {
    isAdjustingInfiniteScroll.value = true
    scroller.scrollLeft = current - segmentWidth
    requestAnimationFrame(() => {
      isAdjustingInfiniteScroll.value = false
    })
  }
}

const resetInfiniteTrainingCardsPosition = async () => {
  const scroller = trainingCardsScroller.value
  if (!scroller) return
  if (scroller.scrollWidth <= scroller.clientWidth) return

  await nextTick()
  scroller.scrollLeft = scroller.scrollWidth / 3
}

const handleTrainingCardsScroll = () => {
  if (isAdjustingInfiniteScroll.value) return
  normalizeInfiniteTrainingCardsScroll()
}

const startTrainingCardsDrag = (event) => {
  if (event.pointerType === 'mouse' && event.button !== 0) return
  const scroller = trainingCardsScroller.value
  if (!scroller) return
  if (scroller.scrollWidth <= scroller.clientWidth) return

  stopTrainingCardsMomentum()
  isDraggingCards.value = true
  hasDraggedCards.value = false
  activeDragPointerId.value = event.pointerId
  hasPointerCapture.value = false
  dragStartX.value = event.clientX
  dragStartScrollLeft.value = scroller.scrollLeft
  dragLastX.value = event.clientX
  dragLastTime.value = performance.now()
  dragVelocityPerFrame.value = 0
}

const moveTrainingCardsDrag = (event) => {
  if (!isDraggingCards.value) return
  if (event.pointerId !== activeDragPointerId.value) return
  const scroller = trainingCardsScroller.value
  if (!scroller) return

  const deltaX = event.clientX - dragStartX.value
  if (Math.abs(deltaX) > 6) {
    hasDraggedCards.value = true
    if (!hasPointerCapture.value) {
      event.currentTarget?.setPointerCapture?.(event.pointerId)
      hasPointerCapture.value = true
    }
  }

  if (hasDraggedCards.value) {
    event.preventDefault()
    scroller.scrollLeft = dragStartScrollLeft.value - deltaX
    normalizeInfiniteTrainingCardsScroll()
  }

  const now = performance.now()
  const elapsed = now - dragLastTime.value
  if (elapsed > 0) {
    const deltaPointer = event.clientX - dragLastX.value
    // Convert pointer movement to scroll velocity (per animation frame).
    dragVelocityPerFrame.value = clamp(((-deltaPointer / elapsed) * 16), -80, 80)
    dragLastX.value = event.clientX
    dragLastTime.value = now
  }
}

const stopTrainingCardsDrag = (event) => {
  if (!isDraggingCards.value) return
  if (activeDragPointerId.value !== null && event.pointerId !== activeDragPointerId.value) return

  if (hasDraggedCards.value) {
    suppressNextCardClick.value = true
    startTrainingCardsMomentum(dragVelocityPerFrame.value)
  }
  isDraggingCards.value = false
  if (hasPointerCapture.value) {
    event.currentTarget?.releasePointerCapture?.(event.pointerId)
  }
  activeDragPointerId.value = null
  hasPointerCapture.value = false
}

const handleTrainingCardsClickCapture = (event) => {
  if (!suppressNextCardClick.value) return
  event.preventDefault()
  event.stopPropagation()
  suppressNextCardClick.value = false
}

const handleTrainingCardClick = (card) => {
  if (card.locked || card.disabled || !card.onClick) return
  card.onClick()
}

onMounted(async () => {
  await nextTick()
  resetInfiniteTrainingCardsPosition()
})

onBeforeUnmount(() => {
  stopTrainingCardsMomentum()
})


watch(
  [isTraining, stream, videoEl, canvasEl, enableCamera],
  async ([training, mediaStream, video, canvas, cameraEnabled]) => {
    if (!training || !cameraEnabled) {
      stopHandTracking()
      stopFpsCounter()
      // Reset states when stopping
      resetLiveFeedback()
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
            timestamp_ms: Date.now(),
            lighting_status: currentLightingStatus.value?.status || null
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
            timestamp_ms: Date.now(),
            lighting_status: currentLightingStatus.value?.status || null
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

watch(
  () => [isTraining.value, trainingCards.value.length],
  async ([training]) => {
    if (training) return
    await nextTick()
    resetInfiniteTrainingCardsPosition()
  }
)

watch(
  isTraining,
  (active) => {
    void syncTrainingSessionRouteState(active)
  },
  { immediate: true }
)
</script>

<template>
  <div class="max-w-4xl mx-auto">
    <TrainingSettings v-if="showSettings" @close="showSettings = false" />

    <div
      :class="[
        isTraining && hasPermissions ? 'grid grid-cols-[auto_1fr] md:grid-cols-3 items-center gap-3' : 'text-center',
        isTraining && hasPermissions && trainingMode === 'advanced' ? 'mb-3' : 'mb-8'
      ]"
    >
      <div v-if="isTraining && hasPermissions" class="flex justify-start">
        <BaseBtn
          variant="secondary"
          title="Return to training cards"
          class="px-3"
          @click="returnToTrainingCards"
        >
          &larr;
        </BaseBtn>
      </div>
      <div class="text-left md:text-center">
        <h1 class="text-2xl md:text-3xl font-bold text-white mb-2">
          {{ trainingMode === 'advanced' ? 'Advanced Training Center' : 'Training Center' }}
        </h1>
        <p class="text-slate-400">
          Master your sign language gestures with real-time feedback
        </p>
      </div>
      <div v-if="isTraining && hasPermissions" class="hidden md:block"></div>
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

      <div v-else-if="trainingMode === 'advanced'" class="training-advanced-layout w-full md:w-[min(92vw,72rem)] mx-auto grid grid-cols-1 md:grid-cols-[minmax(0,3fr)_minmax(0,5fr)] gap-4 md:gap-5">
        <!-- Left Placeholder: 3D Model -->
        <div class="training-advanced-panel training-advanced-model-panel order-2 md:order-1 bg-slate-900 rounded-2xl border border-slate-700 relative overflow-hidden shadow-2xl flex items-center justify-center">
          <span class="text-slate-500 text-2xl font-bold">3D Model</span>
        </div>

        <!-- Right Placeholder: Camera Feed -->
        <div class="training-advanced-panel training-advanced-camera-panel order-1 md:order-2 bg-black rounded-2xl border border-slate-700 relative overflow-hidden shadow-2xl">
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
          <div class="absolute top-7 left-7 right-7 flex justify-between items-end">
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
          <div class="absolute bottom-7 left-7 right-7 flex justify-between items-end">
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

      <div class="flex flex-wrap gap-4" :class="trainingMode === 'advanced' ? 'mt-5' : 'mt-8'">
        <BaseBtn variant="danger" @click="endTrainingSession">
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

        <div class="mt-4 border border-slate-800 bg-black/70 rounded-lg px-4 py-3 font-mono text-xs text-slate-200">
          <div class="text-slate-500 mb-2">Take Console</div>
          <div v-if="takeLogs.length === 0" class="text-slate-500">
            No takes recorded yet.
          </div>
          <div v-else class="space-y-1 max-h-28 overflow-y-auto">
            <div v-for="(line, idx) in takeLogs" :key="`take-log-${idx}`">
              <span class="text-emerald-400">$</span>
              <span class="ml-2">{{ line }}</span>
            </div>
          </div>
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
    <div v-else class="mt-12">
      <div
        ref="trainingCardsScroller"
        class="training-cards-scroll flex items-stretch gap-8 overflow-x-auto pb-2"
        :class="{ 'is-dragging': isDraggingCards }"
        @wheel="handleTrainingCardsWheel"
        @scroll="handleTrainingCardsScroll"
        @pointerdown="startTrainingCardsDrag"
        @pointermove="moveTrainingCardsDrag"
        @pointerup="stopTrainingCardsDrag"
        @pointercancel="stopTrainingCardsDrag"
        @pointerleave="stopTrainingCardsDrag"
        @click.capture="handleTrainingCardsClickCapture"
      >
      <template v-for="loopIndex in 3" :key="`training-loop-${loopIndex}`">
      <BaseCard
        v-for="card in trainingCards"
        :key="`${loopIndex}-${card.id}`"
        class="card w-[280px] sm:w-[320px] xl:w-[340px] h-[430px] flex-none flex flex-col transition-colors"
        :class="card.locked ? 'group opacity-50 cursor-not-allowed' : 'group hover:border-teal-400/50 cursor-pointer'"
        @click="handleTrainingCardClick(card)"
      >
        <div
          class="h-40 bg-slate-800/50 rounded-lg mb-6 flex items-center justify-center text-slate-600 transition-colors"
          :class="card.locked ? '' : 'group-hover:text-teal-400'"
        >
          <span class="text-5xl">{{ card.icon }}</span>
        </div>
        <h3 class="text-xl font-bold text-teal-300 mb-2">
          {{ card.title }}
        </h3>
        <p class="text-slate-400 text-sm flex-1">
          {{ card.description }}
        </p>
        <BaseBtn class="w-full mt-6" :variant="card.buttonVariant" :disabled="card.disabled">
          {{ card.buttonLabel }}
        </BaseBtn>
      </BaseCard>
      </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.training-cards-scroll {
  scrollbar-width: none;
  -ms-overflow-style: none;
  cursor: grab;
  user-select: none;
}

.training-cards-scroll::-webkit-scrollbar {
  display: none;
}

.training-cards-scroll.is-dragging {
  cursor: grabbing;
}

.training-advanced-layout {
  align-items: stretch;
}

.training-advanced-panel {
  min-height: 22rem;
}

@media (min-width: 768px) {
  .training-advanced-camera-panel {
    min-height: 70vh;
    max-height: 760px;
  }

  .training-advanced-model-panel {
    min-height: 64vh;
    max-height: 700px;
  }
}
</style>
