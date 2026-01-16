import { ref, onUnmounted } from 'vue'
import {
  HandLandmarker,
  FilesetResolver,
  DrawingUtils
} from '@mediapipe/tasks-vision'

/**
 * Hand tracking composable
 * - Runs MediaPipe Hands in VIDEO mode
 * - Does NOT depend on UI settings
 * - Drawing is optional and can be toggled
 */
export function useHandTracking() {
  // MediaPipe instance (created once)
  const handLandmarker = ref(null)

  // DOM references
  const video = ref(null)
  const canvas = ref(null)
  const ctx = ref(null)

  // Runtime flags
  let animationFrameId = null
  let isRunning = false
  let isStarting = false

  // UI-controlled flag (connect to Settings)
  const showLandmarks = ref(true)

  /**
   * Initialize MediaPipe HandLandmarker ONCE
   */
  const initHandLandmarker = async () => {
    if (handLandmarker.value) return

    const vision = await FilesetResolver.forVisionTasks(
      'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.0/wasm'
    )

    handLandmarker.value = await HandLandmarker.createFromOptions(vision, {
      baseOptions: {
        modelAssetPath:
          'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',
        delegate: 'GPU'
      },
      runningMode: 'VIDEO',
      numHands: 2
    })

    console.log('[HandTracking] MediaPipe initialized')
  }

  /**
   * Main prediction loop (requestAnimationFrame)
   */
  const loop = () => {
    if (!isRunning || !handLandmarker.value) return

    // Video must be ready
    if (video.value.videoWidth === 0) {
      animationFrameId = requestAnimationFrame(loop)
      return
    }

    const now = performance.now()
    const results = handLandmarker.value.detectForVideo(video.value, now)

    // Clear canvas every frame
    ctx.value.clearRect(0, 0, canvas.value.width, canvas.value.height)

    // Draw landmarks ONLY if enabled
    if (showLandmarks.value && results.landmarks) {
      const drawer = new DrawingUtils(ctx.value)

      for (const landmarks of results.landmarks) {
        drawer.drawConnectors(
          landmarks,
          HandLandmarker.HAND_CONNECTIONS,
          { lineWidth: 4 }
        )
        drawer.drawLandmarks(landmarks, { lineWidth: 2 })
      }
    }

    animationFrameId = requestAnimationFrame(loop)
  }

  /**
   * Start hand tracking
   * - Expects an already approved MediaStream
   */
  const startHandTracking = async (videoEl, canvasEl, mediaStream) => {
    if (isRunning || isStarting) return
    isStarting = true

    video.value = videoEl
    canvas.value = canvasEl
    ctx.value = canvas.value.getContext('2d')

    await initHandLandmarker()

    // Attach stream only once
    if (video.value.srcObject !== mediaStream) {
      video.value.srcObject = mediaStream
    }

    // Wait for video metadata (dimensions)
    await new Promise((resolve) => {
      if (video.value.readyState >= 2) {
        resolve()
      } else {
        video.value.onloadedmetadata = () => resolve()
      }
    })

    await video.value.play()

    // Add a small delay to ensure video stream is fully active and MediaPipe is ready
    await new Promise(resolve => setTimeout(resolve, 100));

    // Match canvas size to video
    canvas.value.width = video.value.videoWidth
    canvas.value.height = video.value.height

    isRunning = true
    isStarting = false

    loop()
  }

  /**
   * Stop tracking loop (does NOT stop camera)
   */
  const stopHandTracking = () => {
    isRunning = false

    if (animationFrameId) {
      cancelAnimationFrame(animationFrameId)
      animationFrameId = null
    }

    if (ctx.value && canvas.value) {
      ctx.value.clearRect(0, 0, canvas.value.width, canvas.value.height)
    }
  }

  onUnmounted(stopHandTracking)

  return {
    // lifecycle
    startHandTracking,
    stopHandTracking,

    // settings
    showLandmarks
  }
}