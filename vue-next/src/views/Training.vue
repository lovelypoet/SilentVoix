<script setup>
import { ref, watch, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router' // Import useRoute
import {
  PhPlay,
  PhHexagon,
  PhShuffle,
  PhStar,
  PhBroadcast,
  PhCaretLeft,
  PhCaretRight,
  PhArrowRight,
  PhLock,
  PhStop,
  PhGearSix,
  PhRecord,
  PhDownloadSimple,
  PhTrash,
  PhArrowCounterClockwise,
  PhTerminalWindow
} from '@phosphor-icons/vue'
import { useAuthStore } from '../stores/auth'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import BasePageHeader from '../components/base/BasePageHeader.vue'
import TrainingSettings from '../components/TrainingSettings.vue'
import { useMediaPermissions } from '../composables/useMediaPermissions.js'
import { useTrainingSettings } from '../composables/useTrainingSettings.js'
import { useHandTracking } from '../composables/useHandTracking.js'
import { useCollectData } from '../composables/useCollectData.js'
import VideoAnalyzer from '../components/VideoAnalyzer.vue'
import TrainingHud from '../components/training/TrainingHud.vue'
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
      tags: ['Camera', 'Live feedback'],
      accent: 'brand-400',
      icon: PhPlay,
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
      tags: ['Your models', 'CV inference'],
      accent: 'success-400',
      icon: PhBroadcast,
      title: 'Realtime AI Playground',
      description: 'Plug in exported models and test live CV inference with overlays.',
      buttonLabel: 'Open Playground',
      buttonVariant: 'primary',
      disabled: false,
      locked: false,
      onClick: startRealtimePlayground
    },
    {
      id: 'advanced-practice',
      tags: ['3D guide', 'AI coach'],
      accent: 'warning-400',
      icon: PhStar,
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
      tags: ['Glove', 'IMU + flex'],
      accent: 'brand-alt-400',
      icon: PhHexagon,
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
      tags: ['Camera + glove', 'Early / late'],
      accent: 'brand-pink-400',
      icon: PhShuffle,
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

/*
 * Arrow-button / keyboard stepping for the card carousel - an explicit
 * alternative to drag and wheel. Tweens scrollLeft by *deltas* each frame
 * (rather than towards an absolute target) so the infinite-loop
 * normalisation can re-seat scrollLeft mid-animation without derailing it.
 */
let stepAnimationFrameId = null
const stepTrainingCards = (direction) => {
  const scroller = trainingCardsScroller.value
  if (!scroller || scroller.scrollWidth <= scroller.clientWidth) return
  stopTrainingCardsMomentum()
  if (stepAnimationFrameId) cancelAnimationFrame(stepAnimationFrameId)

  const firstCard = scroller.querySelector('.card')
  const gap = Number.parseFloat(getComputedStyle(scroller).columnGap) || 0
  const distance = ((firstCard?.offsetWidth || 320) + gap) * direction
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (reduceMotion) {
    scroller.scrollLeft += distance
    normalizeInfiniteTrainingCardsScroll()
    return
  }

  const duration = 520
  const start = performance.now()
  let travelled = 0
  const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3)
  const tick = (now) => {
    const progress = Math.min(1, (now - start) / duration)
    const target = distance * easeOutCubic(progress)
    scroller.scrollLeft += target - travelled
    travelled = target
    normalizeInfiniteTrainingCardsScroll()
    stepAnimationFrameId = progress < 1 ? requestAnimationFrame(tick) : null
  }
  stepAnimationFrameId = requestAnimationFrame(tick)
}

const handleTrainingCardsKeydown = (event) => {
  if (event.target !== event.currentTarget) return
  if (event.key === 'ArrowRight') {
    event.preventDefault()
    stepTrainingCards(1)
  } else if (event.key === 'ArrowLeft') {
    event.preventDefault()
    stepTrainingCards(-1)
  }
}

const framesCollected = computed(() => Math.max(0, collectedLandmarks.value.length - recordingStartCount.value))
const frameProgress = computed(() => (frameLimit.value ? Math.min(1, framesCollected.value / frameLimit.value) : 0))

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
  if (stepAnimationFrameId) cancelAnimationFrame(stepAnimationFrameId)
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

    <BasePageHeader
      :class="isTraining && hasPermissions && trainingMode === 'advanced' ? 'mb-3' : 'mb-8'"
      :title="trainingMode === 'advanced' ? 'Advanced Training Center' : 'Training Center'"
      description="Master your sign language gestures with real-time feedback"
      :centered="!(isTraining && hasPermissions)"
      :back-label="isTraining && hasPermissions ? 'Return to training cards' : ''"
      @back="returnToTrainingCards"
    />

    <!-- Permissions Denied -->
    <div v-if="error" class="text-center mt-12">
      <BaseCard class="max-w-md mx-auto">
        <h3 class="text-xl font-bold text-danger-400 mb-2">
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
      <div v-if="trainingMode === 'free'" class="feed-frame viewport-frame w-full aspect-video bg-black rounded-2xl relative overflow-hidden">
        <span class="viewport-frame-corner-tr"></span>
        <span class="viewport-frame-corner-bl"></span>
        <div v-if="!enableCamera" class="absolute inset-0 flex flex-col items-center justify-center gap-3 text-slate-500 bg-black">
          <span class="scan-ring"></span>
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
        <TrainingHud
          :fps="actualFps"
          :lighting="currentLightingStatus"
          :gesture="detectedGesture"
          :confidence="confidence"
          :recording="isCollecting"
        />
      </div>

      <div v-else-if="trainingMode === 'advanced'" class="training-advanced-layout w-full md:w-[min(92vw,72rem)] mx-auto grid grid-cols-1 md:grid-cols-[minmax(0,3fr)_minmax(0,5fr)] gap-4 md:gap-5">
        <!-- Left Placeholder: 3D Model -->
        <div class="training-advanced-panel training-advanced-model-panel feed-frame grid-texture order-2 md:order-1 rounded-2xl relative overflow-hidden flex flex-col items-center justify-center gap-4 text-center">
          <span class="scan-ring text-brand-400"><PhStar size="26" weight="duotone" aria-hidden="true" /></span>
          <span>
            <span class="block text-lg font-semibold text-slate-200">3D guide model</span>
            <span class="block text-sm text-slate-500">Reference pose renders here</span>
          </span>
        </div>

        <!-- Right Placeholder: Camera Feed -->
        <div class="training-advanced-panel training-advanced-camera-panel feed-frame order-1 md:order-2 bg-black rounded-2xl relative overflow-hidden">
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
          <TrainingHud
            :fps="actualFps"
            :lighting="currentLightingStatus"
            :gesture="detectedGesture"
            :confidence="confidence"
            :recording="isCollecting"
          />
        </div>
      </div>

      <div class="session-bar flex flex-wrap items-center justify-center gap-3" :class="trainingMode === 'advanced' ? 'mt-5' : 'mt-6'">
        <BaseBtn variant="danger" @click="endTrainingSession">
          <PhStop size="16" weight="fill" aria-hidden="true" />
          End Session
        </BaseBtn>
        <BaseBtn variant="secondary" @click="showSettings = true">
          <PhGearSix size="16" weight="bold" aria-hidden="true" />
          Settings
        </BaseBtn>
      </div>

      <!-- Data Collection Panel -->
      <BaseCard class="w-full mt-8">
        <div class="flex flex-wrap items-center justify-between gap-3 mb-5">
          <h2 class="card-title">Data Collection Session</h2>
          <span class="status-badge" :class="isCollecting ? 'status-badge-critical' : 'status-badge-neutral'">
            {{ isCollecting ? 'Recording' : 'Idle' }}
          </span>
        </div>

        <div class="grid gap-5 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
          <div>
            <label for="training-gesture-name" class="field-label">Gesture name</label>
            <input
              id="training-gesture-name"
              v-model="currentGestureName"
              type="text"
              placeholder="e.g., hello, thanks, yes, no"
              class="field-control"
              :disabled="isCollecting"
            />
          </div>
          <BaseBtn
            v-if="!isCollecting"
            :disabled="!currentGestureName.trim()"
            variant="primary"
            class="h-10"
            @click="startRecording"
          >
            <PhRecord size="16" weight="fill" aria-hidden="true" />
            Start Recording
          </BaseBtn>
          <BaseBtn
            v-else
            variant="danger"
            class="h-10"
            @click="stopCollecting"
          >
            <PhStop size="16" weight="fill" aria-hidden="true" />
            Stop Recording
          </BaseBtn>
        </div>

        <div class="mt-5">
          <div class="flex items-baseline justify-between text-sm">
            <span class="text-slate-400">
              <template v-if="isCollecting">Recording <span class="text-slate-100">"{{ currentGestureName }}"</span></template>
              <template v-else>Frames collected</template>
            </span>
            <span class="tabular-nums text-slate-400">
              <span class="font-semibold text-slate-100">{{ framesCollected }}</span> / {{ frameLimit }}
            </span>
          </div>
          <div class="take-progress mt-2" role="progressbar" :aria-valuenow="framesCollected" aria-valuemin="0" :aria-valuemax="frameLimit" aria-label="Frames collected for this take">
            <div class="take-progress-fill" :class="{ 'is-live': isCollecting }" :style="{ transform: `scaleX(${frameProgress})` }"></div>
          </div>
        </div>

        <div class="mt-5 flex flex-wrap gap-2">
          <BaseBtn
            :disabled="collectedLandmarks.length === 0"
            variant="secondary"
            @click="downloadCSV"
          >
            <PhDownloadSimple size="16" weight="bold" aria-hidden="true" />
            Download CSV
          </BaseBtn>
          <BaseBtn
            :disabled="collectedLandmarks.length === 0"
            variant="secondary"
            @click="clearData"
          >
            <PhTrash size="16" weight="bold" aria-hidden="true" />
            Clear Data
          </BaseBtn>
          <BaseBtn
            variant="secondary"
            @click="resetRecording"
          >
            <PhArrowCounterClockwise size="16" weight="bold" aria-hidden="true" />
            Reset
          </BaseBtn>
        </div>

        <div class="take-console mt-5 rounded-xl px-4 py-3 font-mono text-xs text-slate-200">
          <div class="mb-2 flex items-center gap-2 text-slate-500">
            <PhTerminalWindow size="14" weight="bold" aria-hidden="true" />
            Take console
          </div>
          <div v-if="takeLogs.length === 0" class="text-slate-500">
            No takes recorded yet.
          </div>
          <TransitionGroup v-else tag="div" name="take-log" class="space-y-1 max-h-28 overflow-y-auto">
            <div v-for="(line, idx) in takeLogs" :key="`take-log-${idx}`">
              <span class="text-success-400">$</span>
              <span class="ml-2">{{ line }}</span>
            </div>
          </TransitionGroup>
        </div>
      </BaseCard>
    </div>

    <!-- Initial State -->
    <div v-else class="mt-10">
      <div class="relative">
        <div
          ref="trainingCardsScroller"
          class="training-cards-scroll flex items-stretch gap-6 overflow-x-auto py-4"
          :class="{ 'is-dragging': isDraggingCards }"
          tabindex="0"
          role="region"
          aria-label="Training modes. Use left and right arrow keys to browse."
          @wheel="handleTrainingCardsWheel"
          @scroll="handleTrainingCardsScroll"
          @keydown="handleTrainingCardsKeydown"
          @pointerdown="startTrainingCardsDrag"
          @pointermove="moveTrainingCardsDrag"
          @pointerup="stopTrainingCardsDrag"
          @pointercancel="stopTrainingCardsDrag"
          @pointerleave="stopTrainingCardsDrag"
          @click.capture="handleTrainingCardsClickCapture"
        >
          <template v-for="loopIndex in 3" :key="`training-loop-${loopIndex}`">
            <BaseCard
              v-for="(card, cardIndex) in trainingCards"
              :key="`${loopIndex}-${card.id}`"
              class="card mode-card w-[280px] sm:w-[320px] xl:w-[340px] min-h-[440px] flex-none flex flex-col"
              :class="card.locked ? 'is-locked cursor-not-allowed' : 'cursor-pointer'"
              :style="{ '--card-accent': `var(--${card.accent})` }"
              @click="handleTrainingCardClick(card)"
            >
              <div class="mode-art mb-6">
                <span class="mode-index" aria-hidden="true">{{ String(cardIndex + 1).padStart(2, '0') }}</span>
                <span class="mode-ring" aria-hidden="true"></span>
                <span class="mode-icon grid place-items-center">
                  <component :is="card.icon" :size="40" weight="duotone" aria-hidden="true" />
                </span>
                <span v-if="card.locked" class="mode-lock grid place-items-center" aria-label="Locked">
                  <PhLock size="14" weight="bold" />
                </span>
              </div>
              <h3 class="text-lg font-semibold text-slate-50 mb-2">
                {{ card.title }}
              </h3>
              <p class="text-slate-400 text-sm">
                {{ card.description }}
              </p>
              <ul v-if="card.tags?.length" class="mt-4 mb-6 flex flex-wrap gap-1.5" aria-label="Highlights">
                <li v-for="tag in card.tags" :key="tag" class="mode-tag">{{ tag }}</li>
              </ul>
              <BaseBtn class="mode-cta w-full" :variant="card.buttonVariant" :disabled="card.disabled">
                {{ card.buttonLabel }}
                <PhArrowRight size="16" weight="bold" class="mode-cta-arrow" aria-hidden="true" />
              </BaseBtn>
            </BaseCard>
          </template>
        </div>
      </div>

      <div class="mt-6 flex items-center justify-center gap-4">
        <button
          type="button"
          class="focus-ring icon-btn carousel-btn grid h-11 w-11 place-items-center rounded-full text-slate-300 hover:text-slate-50"
          aria-label="Previous training mode"
          @click="stepTrainingCards(-1)"
        >
          <PhCaretLeft size="18" weight="bold" aria-hidden="true" />
        </button>
        <p class="text-xs text-slate-500">Drag, scroll or use the arrows</p>
        <button
          type="button"
          class="focus-ring icon-btn carousel-btn grid h-11 w-11 place-items-center rounded-full text-slate-300 hover:text-slate-50"
          aria-label="Next training mode"
          @click="stepTrainingCards(1)"
        >
          <PhCaretRight size="18" weight="bold" aria-hidden="true" />
        </button>
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
  -webkit-mask-image: linear-gradient(to right, transparent, black 24px, black calc(100% - 48px), transparent);
  mask-image: linear-gradient(to right, transparent, black 24px, black calc(100% - 48px), transparent);
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

/* ---- Mode cards ------------------------------------------------------- */
.mode-card {
  transition:
    transform 420ms var(--ease-spring),
    box-shadow var(--dur) var(--ease-out),
    border-color var(--dur) var(--ease-out);
}

.mode-card:not(.is-locked):hover {
  transform: translateY(-6px);
  border-color: rgb(var(--card-accent) / 0.45);
  box-shadow: 0 30px 60px -30px rgb(var(--card-accent) / 0.55);
}

.mode-card.is-locked {
  opacity: 0.5;
  filter: grayscale(0.6);
}

.mode-art {
  position: relative;
  height: 10.5rem;
  display: grid;
  place-items: center;
  overflow: hidden;
  border-radius: 0.875rem;
  background:
    radial-gradient(120% 90% at 20% 0%, rgb(var(--card-accent) / 0.28), transparent 60%),
    radial-gradient(80% 80% at 100% 100%, rgb(var(--brand-alt-500) / 0.16), transparent 60%),
    rgb(var(--surface) / 0.8);
  box-shadow: inset 0 0 0 1px rgb(var(--card-accent) / 0.16);
}

/* Faint grid inside the art tile. */
.mode-art::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgb(var(--card-accent) / 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgb(var(--card-accent) / 0.08) 1px, transparent 1px);
  background-size: 22px 22px;
  mask-image: radial-gradient(circle at center, black 20%, transparent 75%);
  -webkit-mask-image: radial-gradient(circle at center, black 20%, transparent 75%);
}

.mode-index {
  position: absolute;
  top: 0.75rem;
  left: 0.9rem;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: rgb(var(--card-accent) / 0.8);
}

.mode-ring {
  position: absolute;
  width: 6.5rem;
  height: 6.5rem;
  border-radius: 9999px;
  border: 1px dashed rgb(var(--card-accent) / 0.45);
  animation: mode-ring-spin 18s linear infinite;
}

.mode-icon {
  position: relative;
  width: 4.25rem;
  height: 4.25rem;
  border-radius: 1.25rem;
  color: rgb(var(--card-accent));
  background: rgb(var(--card-accent) / 0.12);
  box-shadow: inset 0 0 0 1px rgb(var(--card-accent) / 0.3), 0 0 32px -6px rgb(var(--card-accent) / 0.6);
  transition: transform 520ms var(--ease-spring);
}

.mode-card:not(.is-locked):hover .mode-icon {
  transform: translateY(-4px) rotate(-6deg) scale(1.08);
}

.mode-card:not(.is-locked):hover .mode-ring {
  animation-duration: 5s;
}

.mode-lock {
  position: absolute;
  top: 0.65rem;
  right: 0.65rem;
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 9999px;
  background: rgb(var(--surface-raised));
  color: rgb(var(--slate-400));
}

.mode-tag {
  padding: 0.2rem 0.6rem;
  border-radius: 9999px;
  font-size: 0.6875rem;
  font-weight: 500;
  color: rgb(var(--slate-300));
  background: rgb(var(--card-accent) / 0.08);
  border: 1px solid rgb(var(--card-accent) / 0.2);
}

.mode-cta {
  margin-top: auto;
}

.mode-cta-arrow {
  transition: transform var(--dur) var(--ease-spring);
}

.mode-card:hover .mode-cta-arrow {
  transform: translateX(4px);
}

@keyframes mode-ring-spin {
  to { transform: rotate(360deg); }
}

.carousel-btn {
  background: rgb(var(--surface) / 0.7);
}

.training-cards-scroll:focus-visible {
  outline: 2px solid rgb(var(--brand-400));
  outline-offset: 4px;
  border-radius: 1rem;
}

/* ---- Live session ----------------------------------------------------- */
.feed-frame {
  border: 1px solid rgb(var(--border-default));
  box-shadow: 0 30px 70px -30px rgb(var(--brand-500) / 0.35), 0 0 0 1px rgb(var(--brand-400) / 0.06);
}

.take-progress {
  height: 0.5rem;
  border-radius: 9999px;
  background: rgb(var(--surface-raised));
  overflow: hidden;
}

.take-progress-fill {
  height: 100%;
  border-radius: inherit;
  transform-origin: left;
  background: linear-gradient(90deg, rgb(var(--brand-500)), rgb(var(--brand-alt-500)));
  transition: transform 240ms var(--ease-out);
}

.take-progress-fill.is-live {
  background: linear-gradient(90deg, rgb(var(--danger-500)), rgb(var(--brand-pink-400)));
  box-shadow: 0 0 12px rgb(var(--danger-400) / 0.6);
}

.take-console {
  border: 1px solid rgb(var(--border-subtle));
  background: rgb(2 6 23 / 0.7);
}

[data-theme='light'] .take-console {
  background: rgb(var(--surface));
}

.take-log-enter-active {
  transition: opacity 260ms var(--ease-out), transform 260ms var(--ease-out);
}

.take-log-enter-from {
  opacity: 0;
  transform: translateX(-8px);
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
