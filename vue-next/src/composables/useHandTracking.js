import { ref, onUnmounted } from 'vue'
// import media pipe library
import {
  HandLandmarker,
  FilesetResolver,
  DrawingUtils
} from '@mediapipe/tasks-vision'

export function useHandTracking(mirrorCameraRef) {
  // MediaPipe instance
  let landmarker = null

  // DOM
  let videoEl = null
  let canvasEl = null
  let ctx = null

  // Loop
  let rafId = null
  let running = false
  const showLandmarks = ref(true)


  // init landmarker
  const createLandmarker = async () => {
    const vision = await FilesetResolver.forVisionTasks(
      'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.0/wasm'
    )

    landmarker = await HandLandmarker.createFromOptions(vision, {
      baseOptions: {
        modelAssetPath:
          'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',
        delegate: 'GPU'
      },
      runningMode: 'VIDEO', // ensure run mode is VIDEO
      numHands: 2
    })

    console.log('[HandTracking] initialized (VIDEO mode)')
  }

  const loop = () => {
    // no chay va landmark k bat -> end
    if (!running || !landmarker) return

    if (!videoEl || videoEl.videoWidth === 0 || videoEl.videoHeight === 0) {
      rafId = requestAnimationFrame(loop)
      return
    }

    const now = performance.now()
    const results = landmarker.detectForVideo(videoEl, now)

    ctx.clearRect(0, 0, canvasEl.width, canvasEl.height)

    ctx.save()

    // MIRROR CANVAS IF VIDEO IS MIRRORED
    if (mirrorCameraRef?.value) {
      ctx.translate(canvasEl.width, 0)
      ctx.scale(-1, 1)
    }

    if (showLandmarks.value && results?.landmarks) {
      const drawer = new DrawingUtils(ctx)

      for (const landmarks of results.landmarks) {
        drawer.drawConnectors(
          landmarks,
          HandLandmarker.HAND_CONNECTIONS,
          { lineWidth: 4 }
        )
        drawer.drawLandmarks(landmarks, { lineWidth: 4 })
      }
    }

    ctx.restore()

    rafId = requestAnimationFrame(loop)
  }

  // ham chinh de goi trong training.vue

  const startHandTracking = async (video, canvas, mediaStream) => {
    stopHandTracking() // reset toan bo ps

    videoEl = video
    canvasEl = canvas
    ctx = canvasEl.getContext('2d')

    await createLandmarker()

    videoEl.srcObject = mediaStream

    await new Promise((resolve) => {
      if (videoEl.readyState >= 2) resolve()
      else videoEl.onloadedmetadata = () => resolve()
    })

    await videoEl.play()
    canvasEl.width = videoEl.videoWidth
    canvasEl.height = videoEl.videoHeight

    running = true
    loop()
  }

  //stop

  const stopHandTracking = () => {
    running = false

    if (rafId) {
      cancelAnimationFrame(rafId)
      rafId = null
    }

    if (ctx && canvasEl) {
      ctx.clearRect(0, 0, canvasEl.width, canvasEl.height)
    }

    if (landmarker) {
      landmarker.close?.()
      landmarker = null
    }
  }

  onUnmounted(stopHandTracking)

  return {
    startHandTracking,
    stopHandTracking,
    showLandmarks
  }
}
