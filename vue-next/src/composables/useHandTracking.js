import { onUnmounted } from 'vue'
import {
  HandLandmarker,
  FilesetResolver,
  DrawingUtils
} from '@mediapipe/tasks-vision'

export function useHandTracking(mirrorCameraRef, showLandmarksRef) {
  // MediaPipe
  let landmarker = null

  // DOM
  let videoEl = null
  let canvasEl = null
  let ctx = null

  // RAW (unmirrored) canvas for MediaPipe
  let rawCanvas = null
  let rawCtx = null

  // Loop
  let rafId = null
  let running = false
  let frameCallback = null

  // ---------------------------
  // INIT MEDIAPIPE
  // ---------------------------
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
      runningMode: 'VIDEO',
      numHands: 2
    })

    console.log('[HandTracking] initialized (VIDEO mode)')
  }

  // ---------------------------
  // MAIN LOOP
  // ---------------------------
  const loop = () => {
    if (!running || !landmarker) return

    if (!videoEl || videoEl.videoWidth === 0 || videoEl.videoHeight === 0) {
      rafId = requestAnimationFrame(loop)
      return
    }

    const now = performance.now()

    // ---- FEED RAW FRAME TO MEDIAPIPE (NO MIRROR) ----
    rawCtx.setTransform(1, 0, 0, 1, 0, 0)
    rawCtx.drawImage(videoEl, 0, 0)

    const results = landmarker.detectForVideo(rawCanvas, now)

    // CALLBACK
    if (frameCallback && results) {
      frameCallback(results)
    }

    // ---- DRAW UI CANVAS (MIRRORED IF NEEDED) ----
    ctx.clearRect(0, 0, canvasEl.width, canvasEl.height)
    ctx.save()

    if (mirrorCameraRef?.value) {
      ctx.translate(canvasEl.width, 0)
      ctx.scale(-1, 1)
    }

    if (showLandmarksRef.value && results?.landmarks) {
      const drawer = new DrawingUtils(ctx)

      for (const landmarks of results.landmarks) {
        drawer.drawConnectors(
          landmarks,
          HandLandmarker.HAND_CONNECTIONS,
          {
            color: 'green',
            lineWidth: 6
          }
        )
        drawer.drawLandmarks(
          landmarks,
          {
            color: '#fff700',
            radius: 6,
            lineWidth: 2
          }
        )
      }
    }

    ctx.restore()
    rafId = requestAnimationFrame(loop)
  }

  // ---------------------------
  // START
  // ---------------------------
  const startHandTracking = async (video, canvas, mediaStream) => {
    stopHandTracking()

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

    // UI canvas
    canvasEl.width = videoEl.videoWidth
    canvasEl.height = videoEl.videoHeight

    // RAW canvas (UNMIRRORED)
    rawCanvas = document.createElement('canvas')
    rawCtx = rawCanvas.getContext('2d')
    rawCanvas.width = videoEl.videoWidth
    rawCanvas.height = videoEl.videoHeight

    running = true
    loop()
  }

  // ---------------------------
  // STOP
  // ---------------------------
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

    rawCanvas = null
    rawCtx = null
  }

  const onFrame = (callback) => {
    frameCallback = callback
  }

  onUnmounted(stopHandTracking)

  return {
    startHandTracking,
    stopHandTracking,
    onFrame
  }
}
