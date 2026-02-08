import { ref, onUnmounted } from 'vue'
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
  
  // ---------------------------
  // TIME-GATED CAPTURE @ 30 FPS
  // ---------------------------
  const TARGET_FPS = 30
  const FRAME_INTERVAL = 1000 / TARGET_FPS // ~33.33ms
  let lastCaptureTime = 0
  let capturedFrames = [] // Store captured landmark data
  let isRecording = ref(false)
  
  // HOLD-LAST-FRAME (live display)
  let lastValidResult = null
  
  // Callback for external consumers
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
    console.log('[HandTracking] initialized (VIDEO mode, 30 FPS capture)')
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
    
    // TIME-GATED CAPTURE: Only detect at 30 FPS
    const timeSinceLastCapture = now - lastCaptureTime
    let currentResult = lastValidResult // Hold last frame by default
    
    if (timeSinceLastCapture >= FRAME_INTERVAL) {
      // ---- FEED RAW FRAME TO MEDIAPIPE (NO MIRROR) ----
      rawCtx.setTransform(1, 0, 0, 1, 0, 0)
      rawCtx.drawImage(videoEl, 0, 0)
      
      const results = landmarker.detectForVideo(rawCanvas, now)
      
      if (results && results.landmarks && results.landmarks.length > 0) {
        currentResult = results
        lastValidResult = results // Update hold-last-frame
        lastCaptureTime = now
        
        // CAPTURE DATA if recording
        if (isRecording.value) {
          capturedFrames.push({
            timestamp: now,
            landmarks: JSON.parse(JSON.stringify(results.landmarks)), // Deep copy
            handedness: results.handedness ? JSON.parse(JSON.stringify(results.handedness)) : null,
            worldLandmarks: results.worldLandmarks ? JSON.parse(JSON.stringify(results.worldLandmarks)) : null
          })
        }
        
        // CALLBACK with fresh data
        if (frameCallback) {
          frameCallback(results)
        }
      }
    }
    
    // ---- DRAW UI CANVAS (MIRRORED IF NEEDED) ----
    // Always draw at display refresh rate, using held frame
    ctx.clearRect(0, 0, canvasEl.width, canvasEl.height)
    ctx.save()
    
    if (mirrorCameraRef?.value) {
      ctx.translate(canvasEl.width, 0)
      ctx.scale(-1, 1)
    }
    
    if (showLandmarksRef.value && currentResult?.landmarks) {
      const drawer = new DrawingUtils(ctx)
      for (const landmarks of currentResult.landmarks) {
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
  // RECORDING CONTROLS
  // ---------------------------
  const startRecording = () => {
    capturedFrames = []
    lastCaptureTime = performance.now()
    isRecording.value = true
    console.log('[HandTracking] Recording started @ 30 FPS')
  }

  const stopRecording = () => {
    isRecording.value = false
    console.log(`[HandTracking] Recording stopped. Captured ${capturedFrames.length} frames`)
    return capturedFrames
  }

  // ---------------------------
  // SAVE CSV
  // ---------------------------
  const saveToCSV = (frames = capturedFrames) => {
    if (!frames || frames.length === 0) {
      console.warn('[HandTracking] No frames to save')
      return
    }

    // CSV Header
    let csv = 'timestamp,hand_index,handedness,landmark_index,x,y,z\n'
    
    frames.forEach(frame => {
      const { timestamp, landmarks, handedness } = frame
      
      landmarks.forEach((handLandmarks, handIdx) => {
        const handLabel = handedness?.[handIdx]?.[0]?.categoryName || 'Unknown'
        
        handLandmarks.forEach((landmark, lmIdx) => {
          csv += `${timestamp},${handIdx},${handLabel},${lmIdx},${landmark.x},${landmark.y},${landmark.z}\n`
        })
      })
    })

    // Download CSV
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `hand_tracking_${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(url)
    
    console.log('[HandTracking] CSV saved')
  }

  // ---------------------------
  // OFFLINE INTERPOLATION / RESAMPLE
  // ---------------------------
  const interpolateFrames = (frames, targetFps = 60) => {
    if (!frames || frames.length < 2) return frames

    const targetInterval = 1000 / targetFps
    const interpolated = []
    
    for (let i = 0; i < frames.length - 1; i++) {
      const curr = frames[i]
      const next = frames[i + 1]
      const timeDiff = next.timestamp - curr.timestamp
      const steps = Math.ceil(timeDiff / targetInterval)
      
      for (let step = 0; step < steps; step++) {
        const t = step / steps // interpolation factor [0, 1)
        const interpTime = curr.timestamp + (timeDiff * t)
        
        // Linear interpolation of landmarks
        const interpLandmarks = curr.landmarks.map((handLandmarks, handIdx) => {
          if (!next.landmarks[handIdx]) return handLandmarks
          
          return handLandmarks.map((lm, lmIdx) => {
            const nextLm = next.landmarks[handIdx][lmIdx]
            return {
              x: lm.x + (nextLm.x - lm.x) * t,
              y: lm.y + (nextLm.y - lm.y) * t,
              z: lm.z + (nextLm.z - lm.z) * t,
              visibility: lm.visibility
            }
          })
        })
        
        interpolated.push({
          timestamp: interpTime,
          landmarks: interpLandmarks,
          handedness: curr.handedness,
          interpolated: step > 0 // Mark interpolated frames
        })
      }
    }
    
    // Add last frame
    interpolated.push(frames[frames.length - 1])
    
    console.log(`[HandTracking] Interpolated ${frames.length} → ${interpolated.length} frames (${targetFps} FPS)`)
    return interpolated
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
    lastCaptureTime = performance.now()
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
    lastValidResult = null
    capturedFrames = []
  }

  const onFrame = (callback) => {
    frameCallback = callback
  }

  onUnmounted(stopHandTracking)

  return {
    startHandTracking,
    stopHandTracking,
    onFrame,
    // NEW: Recording & Export
    startRecording,
    stopRecording,
    saveToCSV,
    interpolateFrames,
    isRecording,
    getCapturedFrames: () => capturedFrames
  }
}