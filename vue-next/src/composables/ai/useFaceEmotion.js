import { ref, shallowRef, onUnmounted } from 'vue'
import { FaceLandmarker, FilesetResolver, DrawingUtils } from '@mediapipe/tasks-vision'
import * as ort from 'onnxruntime-web/wasm'
import { token } from '../../utils/tokens'
import {
  EMOTION_LABELS,
  EMOTION_META,
  FACE_INPUT_SIZE,
  distributionFromLogits,
  dominantEmotion,
  emptyDistribution,
  faceBoxFromLandmarks,
  rgbaToGrayscale,
  samplesToCsv,
  smoothDistribution
} from './emotionModel'

/*
 * Two models cooperate here:
 *
 *   MediaPipe FaceLandmarker  finds the face, gives 478 landmarks + 52
 *                             blendshapes, and runs on the GPU.
 *   FER+ (ONNX, onnxruntime-web)  classifies the cropped face into the eight
 *                             emotion classes, on the CPU via WASM.
 *
 * Landmark detection is cheap enough to run every display frame; the CNN is
 * not, so the two are gated independently. Inference is fire-and-forget with
 * an in-flight guard, which keeps a slow classification from stalling the
 * preview.
 *
 * Structure deliberately mirrors `useHandTracking.js`: a raw unmirrored canvas
 * feeds the detector, a second canvas draws the (optionally mirrored) overlay.
 */

// The FER+ weights are ~35 MB, too big to want in git. Resolution order:
//   1. VITE_EMOTION_MODEL_URL, if the deployment pins one
//   2. vue-next/public/models/emotion/ — populated by `npm run model:emotion`
//   3. the ONNX Model Zoo mirror on Hugging Face
export const LOCAL_MODEL_URL = '/models/emotion/emotion-ferplus-8.onnx'
export const REMOTE_MODEL_URL =
  'https://huggingface.co/onnxmodelzoo/emotion-ferplus-8/resolve/main/emotion-ferplus-8.onnx'

const MEDIAPIPE_WASM = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/wasm'
const FACE_LANDMARKER_TASK =
  'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task'

const DETECT_FPS = 30
const DETECT_INTERVAL = 1000 / DETECT_FPS
// How long a face may go undetected before the readout is cleared. Without it,
// a single dropped frame blanks the panel and it flickers.
const FACE_LOST_MS = 350
const HISTORY_LIMIT = 320

/*
 * Blendshapes worth surfacing next to the CNN's verdict. They are MediaPipe's
 * own geometric read of the face, so when the two disagree the operator can
 * see why — a wide smile with furrowed brows is genuinely ambiguous input.
 */
const SIGNAL_GROUPS = [
  { key: 'smile', label: 'Smile', shapes: ['mouthSmileLeft', 'mouthSmileRight'] },
  { key: 'frown', label: 'Frown', shapes: ['mouthFrownLeft', 'mouthFrownRight'] },
  { key: 'browRaise', label: 'Brow raise', shapes: ['browInnerUp', 'browOuterUpLeft', 'browOuterUpRight'] },
  { key: 'browFurrow', label: 'Brow furrow', shapes: ['browDownLeft', 'browDownRight'] },
  { key: 'jawOpen', label: 'Jaw open', shapes: ['jawOpen'] },
  { key: 'eyeWide', label: 'Eyes wide', shapes: ['eyeWideLeft', 'eyeWideRight'] }
]

/**
 * Fetch the FER+ weights, trying each candidate URL in order.
 *
 * ORT can fetch a URL itself, but doing it here lets us reject a dev server's
 * HTML fallback (which would otherwise surface as an opaque protobuf error)
 * and report which source actually served the model.
 */
const loadModelBuffer = async (configuredUrl) => {
  const candidates = configuredUrl ? [configuredUrl] : [LOCAL_MODEL_URL, REMOTE_MODEL_URL]
  const failures = []

  for (const url of candidates) {
    try {
      const response = await fetch(url)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      if ((response.headers.get('content-type') || '').includes('text/html')) {
        throw new Error('served HTML, not a model')
      }
      const buffer = await response.arrayBuffer()
      if (buffer.byteLength < 1024) throw new Error('model file is empty')
      return { buffer, url }
    } catch (error) {
      failures.push(`${url}: ${error.message}`)
    }
  }

  throw new Error(`Could not load the emotion model.\n${failures.join('\n')}`)
}

/**
 * Tag an error with the stage that produced it.
 *
 * The three failure modes need three different fixes — missing weights, a
 * WASM runtime that will not start, an unreachable MediaPipe CDN — and a
 * single "could not load the model" message sends people after the wrong one.
 */
const stageError = (stage, error) =>
  Object.assign(new Error(error.message || String(error)), { stage })

/**
 * Live face-emotion recognition over a MediaStream.
 *
 * @param {object} options
 * @param {import('vue').Ref<boolean>} [options.mirror] mirror the overlay to match a selfie view
 * @param {import('vue').Ref<boolean>} [options.showMesh] draw the 478-point face mesh
 * @param {import('vue').Ref<number>} [options.smoothing] EMA inertia, 0..0.95
 * @param {import('vue').Ref<number>} [options.inferenceFps] target classifications per second
 * @param {import('vue').Ref<number>} [options.threshold] minimum confidence to name an emotion
 */
export function useFaceEmotion(options = {}) {
  const {
    mirror = ref(true),
    showMesh = ref(true),
    smoothing = ref(0.6),
    inferenceFps = ref(12),
    threshold = ref(0.35)
  } = options

  // ---- public state ----
  const isLoading = ref(false)
  const isReady = ref(false)
  const isRunning = ref(false)
  const loadError = ref(null)
  const loadErrorStage = ref(null)
  const modelSource = ref(null)
  const faceDetected = ref(false)
  const distribution = ref(emptyDistribution())
  const dominant = ref(null)
  const inferenceMs = ref(0)
  const measuredFps = ref(0)
  const signals = ref(SIGNAL_GROUPS.map(({ key, label }) => ({ key, label, score: 0 })))
  const history = shallowRef([])
  const isRecording = ref(false)

  // ---- internals ----
  let landmarker = null
  let session = null
  let videoEl = null
  let canvasEl = null
  let ctx = null
  let drawer = null

  // Unmirrored working canvas: MediaPipe and the crop both need true pixels.
  let rawCanvas = null
  let rawCtx = null
  // 64x64 scratch canvas the browser downscales the face crop into.
  let patchCanvas = null
  let patchCtx = null

  let rafId = null
  let running = false
  let inferInFlight = false

  let lastDetectAt = 0
  let lastInferAt = 0
  let lastFaceAt = 0
  let lastCompletedAt = 0
  let latestLandmarks = null
  let latestBox = null
  let smoothed = null
  let recorded = []
  let resultCallback = null

  const emotionColor = (label) => {
    const meta = EMOTION_META[label]
    if (!meta) return token('brand-400')
    return meta.tokenName ? token(meta.tokenName) : meta.hex
  }

  // ---------------------------
  // INIT
  // ---------------------------
  const createLandmarker = async () => {
    const vision = await FilesetResolver.forVisionTasks(MEDIAPIPE_WASM)
    landmarker = await FaceLandmarker.createFromOptions(vision, {
      baseOptions: { modelAssetPath: FACE_LANDMARKER_TASK, delegate: 'GPU' },
      runningMode: 'VIDEO',
      numFaces: 1,
      outputFaceBlendshapes: true,
      outputFacialTransformationMatrixes: false
    })
  }

  const createSession = async () => {
    // Multi-threaded WASM needs cross-origin isolation, which the Vite dev
    // server does not send. Ask for threads only when the headers allow it.
    const isolated = typeof crossOriginIsolated !== 'undefined' && crossOriginIsolated
    ort.env.wasm.numThreads = isolated ? Math.min(4, navigator.hardwareConcurrency || 1) : 1

    const configured = import.meta.env?.VITE_EMOTION_MODEL_URL || ''

    let buffer
    let url
    try {
      ;({ buffer, url } = await loadModelBuffer(configured))
    } catch (error) {
      throw stageError('weights', error)
    }

    try {
      session = await ort.InferenceSession.create(buffer, {
        executionProviders: ['wasm'],
        graphOptimizationLevel: 'all'
      })
    } catch (error) {
      throw stageError('runtime', error)
    }
    modelSource.value = url
  }

  /** Load both models. Safe to call repeatedly; only the first call does work. */
  const load = async () => {
    if (isReady.value || isLoading.value) return
    isLoading.value = true
    loadError.value = null
    loadErrorStage.value = null
    try {
      await Promise.all([
        createLandmarker().catch((error) => {
          throw stageError('detector', error)
        }),
        createSession()
      ])
      isReady.value = true
    } catch (error) {
      loadError.value = error.message || String(error)
      loadErrorStage.value = error.stage || 'unknown'
      console.error(`[FaceEmotion] load failed at stage "${loadErrorStage.value}":`, error)
      throw error
    } finally {
      isLoading.value = false
    }
  }

  // ---------------------------
  // INFERENCE
  // ---------------------------
  const readSignals = (blendshapes) => {
    const scores = new Map(
      (blendshapes?.categories || []).map((c) => [c.categoryName, c.score])
    )
    signals.value = SIGNAL_GROUPS.map(({ key, label, shapes }) => {
      const values = shapes.map((name) => scores.get(name) || 0)
      // Mean across the left/right pair, so an asymmetric expression still reads.
      const score = values.reduce((a, b) => a + b, 0) / (values.length || 1)
      return { key, label, score }
    })
  }

  const classify = async (box, startedAt) => {
    inferInFlight = true
    try {
      // Crop synchronously: rawCanvas is overwritten by the next detect tick.
      patchCtx.drawImage(
        rawCanvas,
        box.x, box.y, box.size, box.size,
        0, 0, FACE_INPUT_SIZE, FACE_INPUT_SIZE
      )
      const { data } = patchCtx.getImageData(0, 0, FACE_INPUT_SIZE, FACE_INPUT_SIZE)
      const grey = rgbaToGrayscale(data)

      const feeds = {
        [session.inputNames[0]]: new ort.Tensor('float32', grey, [1, 1, FACE_INPUT_SIZE, FACE_INPUT_SIZE])
      }
      const output = await session.run(feeds)
      if (!running) return

      const raw = distributionFromLogits(output[session.outputNames[0]].data)
      smoothed = smoothDistribution(smoothed, raw, smoothing.value)
      distribution.value = smoothed
      dominant.value = dominantEmotion(smoothed, threshold.value)

      const finishedAt = performance.now()
      inferenceMs.value = Math.round(finishedAt - startedAt)
      if (lastCompletedAt) {
        const fps = 1000 / Math.max(finishedAt - lastCompletedAt, 1)
        // Light EMA: the raw number jitters too much to read off a panel.
        measuredFps.value = measuredFps.value ? measuredFps.value * 0.8 + fps * 0.2 : fps
      }
      lastCompletedAt = finishedAt

      const sample = {
        timestamp: finishedAt,
        distribution: smoothed,
        dominant: dominant.value?.label ?? null,
        confidence: dominant.value?.probability ?? 0
      }

      const next = history.value.concat(sample)
      history.value = next.length > HISTORY_LIMIT ? next.slice(-HISTORY_LIMIT) : next
      if (isRecording.value) recorded.push(sample)
      resultCallback?.(sample)
    } catch (error) {
      console.error('[FaceEmotion] inference failed:', error)
    } finally {
      inferInFlight = false
    }
  }

  // ---------------------------
  // DRAW
  // ---------------------------
  const draw = () => {
    ctx.clearRect(0, 0, canvasEl.width, canvasEl.height)
    if (!latestLandmarks) return

    const colour = dominant.value ? emotionColor(dominant.value.label) : token('brand-400', 0.9)

    ctx.save()
    if (mirror.value) {
      ctx.translate(canvasEl.width, 0)
      ctx.scale(-1, 1)
    }

    if (showMesh.value) {
      ctx.globalAlpha = 0.55
      drawer.drawConnectors(latestLandmarks, FaceLandmarker.FACE_LANDMARKS_TESSELATION, {
        color: token('brand-200', 0.18),
        lineWidth: 1
      })
      ctx.globalAlpha = 1
      for (const connectors of [
        FaceLandmarker.FACE_LANDMARKS_FACE_OVAL,
        FaceLandmarker.FACE_LANDMARKS_LEFT_EYE,
        FaceLandmarker.FACE_LANDMARKS_RIGHT_EYE,
        FaceLandmarker.FACE_LANDMARKS_LEFT_EYEBROW,
        FaceLandmarker.FACE_LANDMARKS_RIGHT_EYEBROW,
        FaceLandmarker.FACE_LANDMARKS_LIPS
      ]) {
        drawer.drawConnectors(latestLandmarks, connectors, { color: colour, lineWidth: 2 })
      }
    }

    if (latestBox) {
      ctx.strokeStyle = colour
      ctx.lineWidth = 3
      ctx.setLineDash([16, 10])
      ctx.strokeRect(latestBox.x, latestBox.y, latestBox.size, latestBox.size)
      ctx.setLineDash([])
    }
    ctx.restore()

    // The chip sits outside the mirror transform, or its text would read
    // backwards. Map the box origin into screen space by hand instead.
    if (!latestBox) return
    const originX = mirror.value
      ? canvasEl.width - (latestBox.x + latestBox.size)
      : latestBox.x
    const label = dominant.value
      ? `${EMOTION_META[dominant.value.label].emoji} ${EMOTION_META[dominant.value.label].display} ${(dominant.value.probability * 100).toFixed(0)}%`
      : 'Uncertain'

    ctx.font = '600 22px system-ui, sans-serif'
    const textWidth = ctx.measureText(label).width
    const chipHeight = 38
    const chipY = Math.max(latestBox.y - chipHeight - 10, 6)

    ctx.fillStyle = 'rgba(2, 6, 23, 0.72)'
    ctx.strokeStyle = colour
    ctx.lineWidth = 1.5
    // roundRect is Chrome 99+ / Safari 16.4+; square corners beat a crash.
    if (typeof ctx.roundRect === 'function') {
      ctx.beginPath()
      ctx.roundRect(originX, chipY, textWidth + 28, chipHeight, 10)
      ctx.fill()
      ctx.stroke()
    } else {
      ctx.fillRect(originX, chipY, textWidth + 28, chipHeight)
      ctx.strokeRect(originX, chipY, textWidth + 28, chipHeight)
    }
    ctx.fillStyle = colour
    ctx.fillText(label, originX + 14, chipY + 26)
  }

  // ---------------------------
  // LOOP
  // ---------------------------
  const loop = () => {
    if (!running) return
    if (!videoEl || videoEl.videoWidth === 0) {
      rafId = requestAnimationFrame(loop)
      return
    }

    const now = performance.now()

    if (now - lastDetectAt >= DETECT_INTERVAL) {
      lastDetectAt = now
      rawCtx.drawImage(videoEl, 0, 0)
      const result = landmarker.detectForVideo(rawCanvas, now)
      const landmarks = result?.faceLandmarks?.[0]

      if (landmarks?.length) {
        latestLandmarks = landmarks
        latestBox = faceBoxFromLandmarks(landmarks, rawCanvas.width, rawCanvas.height)
        lastFaceAt = now
        faceDetected.value = true
        readSignals(result.faceBlendshapes?.[0])
      } else if (now - lastFaceAt > FACE_LOST_MS) {
        latestLandmarks = null
        latestBox = null
        faceDetected.value = false
        // Drop the smoothing state too, so the next face starts clean rather
        // than inheriting the previous one's distribution.
        smoothed = null
        distribution.value = emptyDistribution()
        dominant.value = null
        measuredFps.value = 0
      }
    }

    const inferInterval = 1000 / Math.max(1, Number(inferenceFps.value) || 1)
    if (latestBox && !inferInFlight && now - lastInferAt >= inferInterval) {
      lastInferAt = now
      classify(latestBox, now)
    }

    draw()
    rafId = requestAnimationFrame(loop)
  }

  // ---------------------------
  // LIFECYCLE
  // ---------------------------
  /**
   * Attach to a live stream and start recognising.
   *
   * @param {HTMLVideoElement} video
   * @param {HTMLCanvasElement} canvas overlay, resized to the video
   * @param {MediaStream} stream
   */
  const start = async (video, canvas, stream) => {
    stop()
    await load()

    videoEl = video
    canvasEl = canvas
    ctx = canvasEl.getContext('2d')
    drawer = new DrawingUtils(ctx)

    videoEl.srcObject = stream
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
    rawCtx = rawCanvas.getContext('2d', { willReadFrequently: true })

    patchCanvas = document.createElement('canvas')
    patchCanvas.width = FACE_INPUT_SIZE
    patchCanvas.height = FACE_INPUT_SIZE
    patchCtx = patchCanvas.getContext('2d', { willReadFrequently: true })

    running = true
    isRunning.value = true
    lastDetectAt = 0
    lastInferAt = 0
    lastFaceAt = performance.now()
    lastCompletedAt = 0
    loop()
  }

  /** Stop the loop and release the detector. Idempotent. */
  const stop = () => {
    running = false
    isRunning.value = false
    if (rafId) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
    if (ctx && canvasEl) ctx.clearRect(0, 0, canvasEl.width, canvasEl.height)

    landmarker?.close?.()
    landmarker = null
    // The ORT session survives a stop/start cycle only if we keep it, but the
    // 35 MB of weights are not worth holding while the page sits idle.
    session?.release?.()
    session = null
    isReady.value = false

    rawCanvas = null
    rawCtx = null
    patchCanvas = null
    patchCtx = null
    latestLandmarks = null
    latestBox = null
    smoothed = null
    faceDetected.value = false
    distribution.value = emptyDistribution()
    dominant.value = null
    measuredFps.value = 0
    inferenceMs.value = 0
  }

  // ---------------------------
  // RECORDING
  // ---------------------------
  const startRecording = () => {
    recorded = []
    isRecording.value = true
  }

  const stopRecording = () => {
    isRecording.value = false
    return recorded
  }

  /** Download the recorded session as CSV. Returns the row count written. */
  const saveToCSV = (samples = recorded) => {
    if (!samples?.length) return 0
    const blob = new Blob([samplesToCsv(samples)], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `emotion_session_${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(url)
    return samples.length
  }

  const onResult = (callback) => {
    resultCallback = callback
  }

  onUnmounted(stop)

  return {
    // state
    isLoading,
    isReady,
    isRunning,
    loadError,
    loadErrorStage,
    modelSource,
    faceDetected,
    distribution,
    dominant,
    inferenceMs,
    measuredFps,
    signals,
    history,
    isRecording,
    // controls
    load,
    start,
    stop,
    onResult,
    startRecording,
    stopRecording,
    saveToCSV,
    // helpers the view reuses for its own canvas work
    emotionColor,
    labels: EMOTION_LABELS
  }
}
