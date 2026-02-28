import { computed, onMounted, onUnmounted, ref } from 'vue'
import api from '../services/api'

const DEFAULT_MAX_LIVE_FRAMES = 200
const MAX_ALLOWED_LIVE_FRAMES = 2000

function clampInt(value, min, max) {
  const n = Number.parseInt(value, 10)
  if (Number.isNaN(n)) return min
  return Math.min(Math.max(n, min), max)
}

function formatSessionId() {
  return `sensor_${Date.now()}`
}

function normalizeIncomingFrame(payload) {
  if (!payload || payload.type !== 'sensor_frame') return null
  if (!Array.isArray(payload.values) || payload.values.length !== 11) return null

  const values = payload.values.map((v) => Number(v))
  if (values.some((v) => Number.isNaN(v))) return null

  return {
    session_id: payload.session_id || null,
    source: payload.source || 'livews',
    sequence: payload.sequence ?? null,
    timestamp_ms: Number(payload.timestamp_ms) || Date.now(),
    received_at_ms: Number(payload.received_at_ms) || Date.now(),
    schema: payload.schema || 'silentvoix.sensor_frame.v1',
    schema_version: payload.schema_version || '1.0',
    channels: payload.channels || {
      flex: values.slice(0, 5),
      accel: values.slice(5, 8),
      gyro: values.slice(8, 11)
    },
    values
  }
}

function downloadText(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

export function useSensorTraining() {
  const ws = ref(null)
  const isConnected = ref(false)
  const connectionState = ref('disconnected')
  const connectionError = ref('')
  const captureStatus = ref('unknown')
  const captureError = ref('')
  const isCaptureBusy = ref(false)
  const capturePid = ref(null)
  const captureLogPath = ref('')
  const liveFrames = ref([])
  const recordedFrames = ref([])
  const isRecording = ref(false)
  const sessionId = ref(formatSessionId())
  const label = ref('')
  const maxLiveFrames = ref(DEFAULT_MAX_LIVE_FRAMES)
  const lastFrameAt = ref(null)
  const frameTimestamps = ref([])

  const latestFrame = computed(() => {
    if (!liveFrames.value.length) return null
    return liveFrames.value[liveFrames.value.length - 1]
  })

  const estimatedFps = computed(() => {
    const ts = frameTimestamps.value
    if (ts.length < 2) return 0
    const spanMs = ts[ts.length - 1] - ts[0]
    if (spanMs <= 0) return 0
    return Math.round(((ts.length - 1) * 1000) / spanMs)
  })

  const latestChannels = computed(() => {
    const frame = latestFrame.value
    if (!frame) return { flex: [], accel: [], gyro: [] }
    return frame.channels || {
      flex: frame.values.slice(0, 5),
      accel: frame.values.slice(5, 8),
      gyro: frame.values.slice(8, 11)
    }
  })

  const canExport = computed(() => recordedFrames.value.length > 0)

  const closeSocket = () => {
    if (!ws.value) return
    try {
      ws.value.close()
    } catch (_) {
      // Ignore socket close errors.
    }
    ws.value = null
  }

  const applyCaptureStatus = (payload) => {
    captureStatus.value = payload?.status || 'unknown'
    capturePid.value = payload?.pid ?? null
    captureLogPath.value = payload?.log_path || ''
  }

  const fetchCaptureStatus = async () => {
    try {
      const res = await api.captureControls.sensorCapture.status()
      applyCaptureStatus(res || {})
      captureError.value = ''
      return res
    } catch (_) {
      captureError.value = 'Unable to fetch sensor capture status.'
      captureStatus.value = 'unknown'
      capturePid.value = null
      return null
    }
  }

  const ensureCaptureRunning = async () => {
    if (isCaptureBusy.value) return false
    isCaptureBusy.value = true
    try {
      const status = await fetchCaptureStatus()
      if (status?.status === 'running') return true
      const started = await api.captureControls.sensorCapture.start('single')
      applyCaptureStatus(started || {})
      captureError.value = ''
      return true
    } catch (_) {
      captureError.value = 'Failed to auto-start sensor capture.'
      return false
    } finally {
      isCaptureBusy.value = false
    }
  }

  const stopCapture = async () => {
    if (isCaptureBusy.value) return
    isCaptureBusy.value = true
    try {
      const res = await api.captureControls.sensorCapture.stop()
      applyCaptureStatus(res || { status: 'stopped' })
      captureError.value = ''
    } catch (_) {
      captureError.value = 'Failed to stop sensor capture.'
    } finally {
      isCaptureBusy.value = false
    }
  }

  const addLiveFrame = (frame) => {
    liveFrames.value.push(frame)

    const cap = clampInt(maxLiveFrames.value, 20, MAX_ALLOWED_LIVE_FRAMES)
    if (liveFrames.value.length > cap) {
      liveFrames.value.splice(0, liveFrames.value.length - cap)
    }

    frameTimestamps.value.push(frame.timestamp_ms)
    if (frameTimestamps.value.length > 60) {
      frameTimestamps.value.splice(0, frameTimestamps.value.length - 60)
    }

    lastFrameAt.value = new Date(frame.timestamp_ms)
  }

  const onMessage = (event) => {
    let data = null
    try {
      data = JSON.parse(event.data)
    } catch (_) {
      return
    }

    if (data.type === 'error') {
      connectionError.value = data.message || 'WebSocket error'
      return
    }

    const frame = normalizeIncomingFrame(data)
    if (!frame) return

    addLiveFrame(frame)

    if (isRecording.value) {
      recordedFrames.value.push({
        ...frame,
        recording_session_id: sessionId.value,
        recording_label: label.value.trim() || 'unlabeled'
      })
    }
  }

  const connect = async () => {
    connectionError.value = ''
    if (ws.value && isConnected.value) return

    const captureOk = await ensureCaptureRunning()
    if (!captureOk) {
      connectionError.value = 'Sensor capture is not running.'
      connectionState.value = 'error'
      return
    }

    connectionState.value = 'connecting'
    const socket = api.createWebSocket('/ws/stream')
    ws.value = socket

    socket.onopen = () => {
      isConnected.value = true
      connectionState.value = 'connected'
      socket.send(JSON.stringify({ type: 'subscribe' }))
    }

    socket.onmessage = onMessage

    socket.onerror = () => {
      connectionError.value = 'Failed to connect to /ws/stream'
      connectionState.value = 'error'
    }

    socket.onclose = () => {
      isConnected.value = false
      if (connectionState.value !== 'error') {
        connectionState.value = 'disconnected'
      }
    }
  }

  const disconnect = () => {
    closeSocket()
    isConnected.value = false
    connectionState.value = 'disconnected'
  }

  const startRecording = () => {
    isRecording.value = true
  }

  const stopRecording = () => {
    isRecording.value = false
  }

  const resetRecording = () => {
    isRecording.value = false
    recordedFrames.value = []
    sessionId.value = formatSessionId()
  }

  const clearLiveFrames = () => {
    liveFrames.value = []
    frameTimestamps.value = []
    lastFrameAt.value = null
  }

  const exportRecordedJson = () => {
    if (!canExport.value) return
    const payload = {
      schema: 'silentvoix.sensor_frame.dataset.v1',
      exported_at: new Date().toISOString(),
      session_id: sessionId.value,
      label: label.value.trim() || 'unlabeled',
      count: recordedFrames.value.length,
      frames: recordedFrames.value
    }
    const fileName = `${sessionId.value || 'sensor_session'}_${Date.now()}.json`
    downloadText(JSON.stringify(payload, null, 2), fileName, 'application/json')
  }

  const exportRecordedCsv = () => {
    if (!canExport.value) return

    const header = [
      'recording_session_id',
      'recording_label',
      'source',
      'sequence',
      'timestamp_ms',
      'received_at_ms',
      'schema',
      'schema_version',
      'flex1',
      'flex2',
      'flex3',
      'flex4',
      'flex5',
      'accel_x',
      'accel_y',
      'accel_z',
      'gyro_x',
      'gyro_y',
      'gyro_z'
    ]

    const rows = recordedFrames.value.map((frame) => [
      frame.recording_session_id || '',
      frame.recording_label || '',
      frame.source || '',
      frame.sequence ?? '',
      frame.timestamp_ms ?? '',
      frame.received_at_ms ?? '',
      frame.schema || '',
      frame.schema_version || '',
      ...frame.values.map((v) => `${v}`)
    ])

    const csv = [header.join(','), ...rows.map((r) => r.join(','))].join('\n')
    const fileName = `${sessionId.value || 'sensor_session'}_${Date.now()}.csv`
    downloadText(csv, fileName, 'text/csv;charset=utf-8')
  }

  onMounted(() => {
    void ensureCaptureRunning()
    void connect()
  })

  onUnmounted(() => {
    closeSocket()
  })

  return {
    captureError,
    captureLogPath,
    capturePid,
    captureStatus,
    canExport,
    clearLiveFrames,
    connect,
    connectionError,
    connectionState,
    disconnect,
    estimatedFps,
    exportRecordedCsv,
    exportRecordedJson,
    fetchCaptureStatus,
    isConnected,
    isCaptureBusy,
    isRecording,
    label,
    lastFrameAt,
    latestChannels,
    latestFrame,
    liveFrames,
    maxLiveFrames,
    recordedFrames,
    resetRecording,
    sessionId,
    stopCapture,
    startRecording,
    stopRecording
  }
}
