import { ref, computed, watch, onUnmounted } from 'vue'
import api from '../services/api'

const buildPath = (values) => {
  if (!values.length) return ''
  const width = 100
  const height = 24
  const max = Math.max(...values)
  const min = Math.min(...values)
  const range = Math.max(1, max - min)
  return values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * width
      const y = height - ((v - min) / range) * (height - 4) - 2
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(2)} ${y.toFixed(2)}`
    })
    .join(' ')
}

export const useSyncStream = (captureMode, isSessionActive) => {
  const sensorSeries = ref([])
  const cvSeries = ref([])
  const sensorSpikeThreshold = ref(null)
  const sensorSpikeIndex = ref(-1)
  const sensorSpikeActive = ref(false)
  const cvSpikeThreshold = ref(null)
  const cvSpikeIndex = ref(-1)
  const cvSpikeActive = ref(false)
  const syncWsConnected = ref(false)
  const syncWs = ref(null)
  let syncTick = null

  const sparkPath = computed(() => buildPath(sensorSeries.value))
  const cvPath = computed(() => buildPath(cvSeries.value))

  const sparkPeak = computed(() => {
    if (!sensorSeries.value.length) return { x: 0, y: 0 }
    const width = 100
    const height = 24
    const values = sensorSeries.value
    const max = Math.max(...values)
    const min = Math.min(...values)
    const range = Math.max(1, max - min)
    const peakIndex = values.indexOf(max)
    const x = (peakIndex / (values.length - 1)) * width
    const y = height - ((max - min) / range) * (height - 4) - 2
    return { x, y }
  })

  const cvPeak = computed(() => {
    if (!cvSeries.value.length) return { x: 0, y: 0 }
    const width = 100
    const height = 24
    const values = cvSeries.value
    const max = Math.max(...values)
    const min = Math.min(...values)
    const range = Math.max(1, max - min)
    const peakIndex = values.indexOf(max)
    const x = (peakIndex / (values.length - 1)) * width
    const y = height - ((max - min) / range) * (height - 4) - 2
    return { x, y }
  })

  const sparkThreshold = computed(() => {
    if (sensorSpikeThreshold.value === null || !sensorSeries.value.length) return null
    const height = 24
    const values = sensorSeries.value
    const max = Math.max(...values)
    const min = Math.min(...values)
    const range = Math.max(1, max - min)
    const y = height - ((sensorSpikeThreshold.value - min) / range) * (height - 4) - 2
    return Math.max(2, Math.min(height - 2, y))
  })

  const cvThreshold = computed(() => {
    if (cvSpikeThreshold.value === null || !cvSeries.value.length) return null
    const height = 24
    const values = cvSeries.value
    const max = Math.max(...values)
    const min = Math.min(...values)
    const range = Math.max(1, max - min)
    const y = height - ((cvSpikeThreshold.value - min) / range) * (height - 4) - 2
    return Math.max(2, Math.min(height - 2, y))
  })

  const sparkSpike = computed(() => {
    if (sensorSpikeIndex.value < 0 || !sensorSeries.value.length) return null
    const width = 100
    const height = 24
    const values = sensorSeries.value
    const max = Math.max(...values)
    const min = Math.min(...values)
    const range = Math.max(1, max - min)
    const x = (sensorSpikeIndex.value / (values.length - 1)) * width
    const y = height - ((values[sensorSpikeIndex.value] - min) / range) * (height - 4) - 2
    return { x, y }
  })

  const cvSpike = computed(() => {
    if (cvSpikeIndex.value < 0 || !cvSeries.value.length) return null
    const width = 100
    const height = 24
    const values = cvSeries.value
    const max = Math.max(...values)
    const min = Math.min(...values)
    const range = Math.max(1, max - min)
    const x = (cvSpikeIndex.value / (values.length - 1)) * width
    const y = height - ((values[cvSpikeIndex.value] - min) / range) * (height - 4) - 2
    return { x, y }
  })

  const openSyncStream = () => {
    if (syncWs.value) return
    const ws = api.createWebSocket('/ws/sync')
    syncWs.value = ws

    ws.onopen = () => {
      syncWsConnected.value = true
      ws.send(JSON.stringify({ type: 'configure', mode: captureMode.value }))
      syncTick = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'tick' }))
        }
      }, 1000)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type !== 'sync_series') return
        if (data.sensor) {
          sensorSeries.value = data.sensor.series || []
          sensorSpikeThreshold.value = data.sensor.threshold ?? null
          sensorSpikeIndex.value = data.sensor.spike_index ?? -1
          sensorSpikeActive.value = Boolean(data.sensor.spike_active)
        }
        if (data.cv) {
          cvSeries.value = data.cv.series || []
          cvSpikeThreshold.value = data.cv.threshold ?? null
          cvSpikeIndex.value = data.cv.spike_index ?? -1
          cvSpikeActive.value = Boolean(data.cv.spike_active)
        }
      } catch (e) {
        // Ignore malformed payloads
      }
    }

    ws.onclose = () => {
      syncWsConnected.value = false
      syncWs.value = null
      if (syncTick) clearInterval(syncTick)
      syncTick = null
    }
  }

  const closeSyncStream = () => {
    if (syncWs.value) syncWs.value.close()
  }

  const prevCvPoint = ref(null)
  const prevCvTime = ref(0)
  const lastCvSend = ref(0)

  const ingestCvPoint = (point, timestampMs = Date.now()) => {
    if (!point) return
    if (prevCvPoint.value) {
      const dx = point.x - prevCvPoint.value.x
      const dy = point.y - prevCvPoint.value.y
      const dz = point.z - prevCvPoint.value.z
      const dt = Math.max(1, timestampMs - prevCvTime.value)
      const velocity = Math.sqrt(dx * dx + dy * dy + dz * dz) / dt
      if (syncWs.value && syncWs.value.readyState === WebSocket.OPEN) {
        if (timestampMs - lastCvSend.value >= 100) {
          syncWs.value.send(JSON.stringify({ type: 'cv_sample', timestamp_ms: timestampMs, velocity }))
          lastCvSend.value = timestampMs
        }
      }
    }
    prevCvPoint.value = point
    prevCvTime.value = timestampMs
  }

  const resetCvState = () => {
    prevCvPoint.value = null
    prevCvTime.value = 0
    lastCvSend.value = 0
  }

  watch(
    () => captureMode.value,
    (mode) => {
      if (syncWs.value && syncWs.value.readyState === WebSocket.OPEN) {
        syncWs.value.send(JSON.stringify({ type: 'configure', mode }))
      }
    }
  )

  watch(
    () => isSessionActive.value,
    (active) => {
      if (active) {
        openSyncStream()
      } else {
        closeSyncStream()
      }
    }
  )

  onUnmounted(() => {
    if (syncTick) clearInterval(syncTick)
    if (syncWs.value) syncWs.value.close()
  })

  return {
    sensorSeries,
    cvSeries,
    sensorSpikeThreshold,
    sensorSpikeIndex,
    sensorSpikeActive,
    cvSpikeThreshold,
    cvSpikeIndex,
    cvSpikeActive,
    syncWsConnected,
    sparkPath,
    cvPath,
    sparkPeak,
    cvPeak,
    sparkThreshold,
    cvThreshold,
    sparkSpike,
    cvSpike,
    ingestCvPoint,
    resetCvState
  }
}
