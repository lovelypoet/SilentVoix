import { ref, shallowRef, onUnmounted } from 'vue'
import * as ort from 'onnxruntime-web/wasm'
import { HandLandmarker, FilesetResolver, DrawingUtils } from '@mediapipe/tasks-vision'
import {
  ASL_LABELS,
  FRAME_FEATURES,
  buildFrameFeatures,
  createFrameWindow,
  softmax,
  topK
} from './aslModel'

/*
 * Camera -> MediaPipe HandLandmarker (2 hands) -> sliding window of 126-float
 * frames -> ASL CNN+BiLSTM (ONNX, onnxruntime-web) -> top-k signs, all in this
 * tab. Structurally mirrors useGestureRecognizerCamera.js / useFaceEmotion.js:
 * a raw unmirrored canvas feeds the detector, and the component CSS-mirrors
 * the <video> and the overlay <canvas> together.
 *
 * The weights are gitignored like FER+. Resolution order:
 *   1. VITE_ASL_MODEL_URL, if the deployment pins one
 *   2. vue-next/public/models/asl/, written by scripts/export_asl_model.py
 */
export const LOCAL_MODEL_URL = '/models/asl/asl-improved.onnx'

const MEDIAPIPE_WASM = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/wasm'
const HAND_LANDMARKER_TASK =
  'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task'

// The model was trained on video clips, so frames should arrive at a
// video-like rate. 15 Hz keeps two-hand detection and inference cheap.
export const DETECT_FPS = 15
const DETECT_INTERVAL = 1000 / DETECT_FPS
const INFER_EVERY_N_FRAMES = 3
const HOLD_LAST_FRAME_MS = 250

export function useAslRecognizer() {
  let landmarker = null
  let session = null
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
  let framesSinceInfer = 0
  let inferring = false
  let predictionCallback = null

  const settings = { windowFrames: 30, minHandFrames: 8 }
  const frameWindow = createFrameWindow(settings.windowFrames)

  const isLoading = ref(false)
  const isReady = ref(false)
  const isActive = ref(false)
  const error = ref('')
  const handsVisible = ref(0)
  const bufferFill = ref(0)
  const predictions = shallowRef([])
  const inferenceMs = ref(0)

  const loadSession = async () => {
    const isolated = typeof crossOriginIsolated !== 'undefined' && crossOriginIsolated
    ort.env.wasm.numThreads = isolated ? Math.min(4, navigator.hardwareConcurrency || 1) : 1

    const url = import.meta.env?.VITE_ASL_MODEL_URL || LOCAL_MODEL_URL
    const response = await fetch(url)
    // Vite answers a missing public file with index.html, which would
    // otherwise surface as an opaque protobuf parse error.
    if (!response.ok || (response.headers.get('content-type') || '').includes('text/html')) {
      throw new Error(
        `ASL model not found at ${url}. Run \`npm run model:asl\` to export it into public/models/asl/.`
      )
    }
    const buffer = await response.arrayBuffer()
    session = await ort.InferenceSession.create(buffer, {
      executionProviders: ['wasm'],
      graphOptimizationLevel: 'all'
    })
  }

  const loadLandmarker = async () => {
    const vision = await FilesetResolver.forVisionTasks(MEDIAPIPE_WASM)
    landmarker = await HandLandmarker.createFromOptions(vision, {
      baseOptions: { modelAssetPath: HAND_LANDMARKER_TASK, delegate: 'GPU' },
      runningMode: 'VIDEO',
      numHands: 2
    })
  }

  const load = async () => {
    if (isReady.value) return
    await Promise.all([loadLandmarker(), loadSession()])
    isReady.value = true
  }

  const infer = async () => {
    if (!session || inferring) return
    if (frameWindow.recentHandFrames(frameWindow.length) < settings.minHandFrames) {
      if (predictions.value.length) predictions.value = []
      return
    }
    inferring = true
    try {
      const t0 = performance.now()
      const frames = frameWindow.length
      const input = new ort.Tensor('float32', frameWindow.flatten(), [1, frames, FRAME_FEATURES])
      const output = await session.run({ [session.inputNames[0]]: input })
      const logits = output[session.outputNames[0]].data
      inferenceMs.value = Math.round(performance.now() - t0)
      const ranked = topK(softmax(logits), 5, ASL_LABELS)
      predictions.value = ranked
      predictionCallback?.(ranked)
    } catch (e) {
      console.warn('[ASL] inference error (loop continues):', e)
    } finally {
      inferring = false
    }
  }

  const loop = () => {
    if (!running) return
    if (!videoEl || videoEl.videoWidth === 0) {
      rafId = requestAnimationFrame(loop)
      return
    }

    const now = performance.now()
    let currentResult = null
    try {
      if (now - lastDetectTime >= DETECT_INTERVAL) {
        rawCtx.drawImage(videoEl, 0, 0)
        const result = landmarker.detectForVideo(rawCanvas, now)
        lastDetectTime = now

        const { features, handCount } = buildFrameFeatures(result?.landmarks, result?.handedness)
        frameWindow.push(features, handCount)
        handsVisible.value = handCount
        bufferFill.value = frameWindow.length

        if (handCount > 0) {
          currentResult = result
          lastValidResult = result
          lastValidTime = now
        } else if (frameWindow.recentHandFrames(settings.minHandFrames) === 0) {
          // Hands have been gone for a while: drop the stale window so the
          // next sign starts clean instead of blending with the last one.
          frameWindow.clear()
          if (predictions.value.length) predictions.value = []
        }

        if (++framesSinceInfer >= INFER_EVERY_N_FRAMES) {
          framesSinceInfer = 0
          infer()
        }
      }

      ctx.clearRect(0, 0, canvasEl.width, canvasEl.height)
      const display = currentResult || (now - lastValidTime <= HOLD_LAST_FRAME_MS ? lastValidResult : null)
      if (display?.landmarks?.length) {
        const drawer = new DrawingUtils(ctx)
        for (const points of display.landmarks) {
          drawer.drawConnectors(points, HandLandmarker.HAND_CONNECTIONS, { color: '#22d3ee', lineWidth: 3 })
          drawer.drawLandmarks(points, { color: '#ffffff', radius: 3, lineWidth: 1 })
        }
      }
    } catch (e) {
      console.warn('[ASL] frame processing error (loop continues):', e)
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
      await load()

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

      frameWindow.clear()
      running = true
      lastDetectTime = 0
      isActive.value = true
      loop()
    } catch (e) {
      error.value = e?.message || 'Failed to start the ASL recognizer.'
      stop()
    } finally {
      isLoading.value = false
    }
  }

  const stop = () => {
    running = false
    if (rafId) cancelAnimationFrame(rafId)
    rafId = null
    mediaStream?.getTracks().forEach((t) => t.stop())
    mediaStream = null
    if (ctx && canvasEl) ctx.clearRect(0, 0, canvasEl.width, canvasEl.height)
    lastValidResult = null
    frameWindow.clear()
    handsVisible.value = 0
    bufferFill.value = 0
    predictions.value = []
    isActive.value = false
  }

  const configure = ({ windowFrames, minHandFrames } = {}) => {
    if (windowFrames) {
      settings.windowFrames = windowFrames
      frameWindow.resize(windowFrames)
    }
    if (minHandFrames) settings.minHandFrames = minHandFrames
  }

  const onPrediction = (callback) => {
    predictionCallback = callback
  }

  onUnmounted(() => {
    stop()
    landmarker?.close?.()
    landmarker = null
    session?.release?.()
    session = null
  })

  return {
    start,
    stop,
    configure,
    onPrediction,
    isLoading,
    isReady,
    isActive,
    error,
    handsVisible,
    bufferFill,
    predictions,
    inferenceMs
  }
}
