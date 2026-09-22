import { ref, onUnmounted } from 'vue'
import { GestureRecognizer, FilesetResolver, DrawingUtils } from '@mediapipe/tasks-vision'

/*
 * Camera + MediaPipe Gesture Recognizer loop for the temporary gesture -> TTS
 * test feature (MediaPipeGestureTest.vue). Structurally mirrors
 * useHandTracking.js (raw canvas feeds the detector, gated detection rate,
 * hold-last-frame for smooth display) but is kept as its own module rather
 * than folded into useHandTracking: that composable is HandLandmarker-only
 * and feeds the real V-Hand capture/training pipeline, and this is a
 * throwaway test path with a different model and no recording/export.
 *
 * Model: Google's official Gesture Recognizer .task bundle, referenced
 * directly by its Google Cloud Storage URL - the same pattern already used
 * for HandLandmarker (useHandTracking.js) and FaceLandmarker
 * (useFaceEmotion.js) in this codebase. MediaPipe fetches and caches it
 * itself; there is no local vendoring step for .task files anywhere in this
 * project (unlike the FER+ .onnx weights, which are large enough to want a
 * local copy - see scripts/fetch-emotion-model.js). The registry-uploaded
 * V-Hand models never touch this: `.task` is not one of the accepted
 * upload formats (AI/model_library only takes .tflite/.keras/.h5/.pth/.pt).
 */
const MEDIAPIPE_WASM = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/wasm'
export const GESTURE_RECOGNIZER_TASK_URL =
  'https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task'

const DETECT_FPS = 15
const DETECT_INTERVAL = 1000 / DETECT_FPS
const HOLD_LAST_FRAME_MS = 250

export function useGestureRecognizerCamera() {
  let recognizer = null
  let videoEl = null
  let canvasEl = null
  let ctx = null
  let rawCanvas = null
  let rawCtx = null
  let mediaStream = null
  let rafId = null
  let running = false
  let lastDetectTime = 0
  let lastValidResult = null
  let lastValidTime = 0
  let frameCallback = null

  const isActive = ref(false)
  const isLoading = ref(false)
  const error = ref('')

  const createRecognizer = async () => {
    const vision = await FilesetResolver.forVisionTasks(MEDIAPIPE_WASM)
    recognizer = await GestureRecognizer.createFromOptions(vision, {
      baseOptions: {
        modelAssetPath: GESTURE_RECOGNIZER_TASK_URL,
        delegate: 'GPU'
      },
      runningMode: 'VIDEO',
      numHands: 1
    })
  }

  const loop = () => {
    if (!running || !recognizer) return

    if (!videoEl || videoEl.videoWidth === 0 || videoEl.videoHeight === 0) {
      rafId = requestAnimationFrame(loop)
      return
    }

    const now = performance.now()
    let currentResult = null

    if (now - lastDetectTime >= DETECT_INTERVAL) {
      rawCtx.drawImage(videoEl, 0, 0)
      const result = recognizer.recognizeForVideo(rawCanvas, now)
      lastDetectTime = now

      if (result?.landmarks?.length) {
        currentResult = result
        lastValidResult = result
        lastValidTime = now
      }

      frameCallback?.(currentResult)
    }

    // Draw the overlay every animation frame (not just detection ticks) so
    // it doesn't visibly stutter at DETECT_FPS. Both the <video> and this
    // <canvas> are CSS-mirrored together by the component, so landmarks are
    // drawn in raw (unmirrored) space and still line up on screen.
    ctx.clearRect(0, 0, canvasEl.width, canvasEl.height)
    const displayResult = currentResult
      || (now - lastValidTime <= HOLD_LAST_FRAME_MS ? lastValidResult : null)

    if (displayResult?.landmarks?.length) {
      const drawer = new DrawingUtils(ctx)
      for (const landmarks of displayResult.landmarks) {
        drawer.drawConnectors(landmarks, GestureRecognizer.HAND_CONNECTIONS, {
          color: '#facc15',
          lineWidth: 3
        })
        drawer.drawLandmarks(landmarks, { color: '#ffffff', radius: 3, lineWidth: 1 })
      }
    }

    rafId = requestAnimationFrame(loop)
  }

  const start = async (video, canvas) => {
    error.value = ''
    isLoading.value = true
    try {
      videoEl = video
      canvasEl = canvas
      ctx = canvasEl.getContext('2d')

      if (!recognizer) await createRecognizer()

      mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false
      })
      videoEl.srcObject = mediaStream
      await new Promise((resolve) => {
        if (videoEl.readyState >= 2) resolve()
        else videoEl.onloadedmetadata = () => resolve()
      })
      await videoEl.play()

      canvasEl.width = videoEl.videoWidth
      canvasEl.height = videoEl.videoHeight
      rawCanvas = document.createElement('canvas')
      rawCanvas.width = videoEl.videoWidth
      rawCanvas.height = videoEl.videoHeight
      rawCtx = rawCanvas.getContext('2d')

      running = true
      lastDetectTime = 0
      isActive.value = true
      loop()
    } catch (e) {
      error.value = e?.message || 'Failed to start camera.'
      stop()
    } finally {
      isLoading.value = false
    }
  }

  const stop = () => {
    running = false
    if (rafId) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
    if (mediaStream) {
      mediaStream.getTracks().forEach((t) => t.stop())
      mediaStream = null
    }
    if (ctx && canvasEl) ctx.clearRect(0, 0, canvasEl.width, canvasEl.height)
    lastValidResult = null
    isActive.value = false
  }

  const onFrame = (callback) => {
    frameCallback = callback
  }

  onUnmounted(() => {
    stop()
    recognizer?.close?.()
    recognizer = null
  })

  return { start, stop, onFrame, isActive, isLoading, error }
}
