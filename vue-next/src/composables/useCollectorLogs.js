import { ref, watch, onUnmounted } from 'vue'
import api from '../services/api'

export const useCollectorLogs = (captureMode, sensorCaptureStatus) => {
  const terminalLines = ref([])
  const terminalError = ref('')
  const isStreaming = ref(false)
  const autoScroll = ref(true)
  const POLL_INTERVAL_MS = 4000
  let terminalPoll = null

  const fetchLogs = async () => {
    try {
      terminalError.value = ''
      const activeMode =
        sensorCaptureStatus.value?.status === 'running'
          ? sensorCaptureStatus.value?.mode || captureMode.value
          : captureMode.value
      const res = await api.utils.collectorLogs(activeMode, 200)
      if (res?.lines) {
        terminalLines.value = res.lines.map(line => line.replace(/\r?\n$/, ''))
      }
    } catch (error) {
      const status = error?.response?.status
      if (status === 404) {
        terminalError.value = 'No collector logs found yet. Start a capture to generate logs.'
      } else if (status === 429) {
        terminalError.value = 'Collector logs polling is rate-limited. Waiting before retry.'
      } else {
        terminalError.value = 'Unable to fetch collector logs from backend.'
      }
    }
  }

  const startStream = async () => {
    if (terminalPoll) return
    isStreaming.value = true
    await fetchLogs()
    terminalPoll = setInterval(fetchLogs, POLL_INTERVAL_MS)
  }

  const stopStream = () => {
    if (terminalPoll) clearInterval(terminalPoll)
    terminalPoll = null
    isStreaming.value = false
  }

  const toggleStream = () => {
    if (isStreaming.value) {
      stopStream()
    } else {
      startStream()
    }
  }

  watch(
    () => sensorCaptureStatus.value?.status,
    (status) => {
      if (status === 'running') {
        startStream()
      } else if (status === 'stopped') {
        stopStream()
      }
    }
  )

  onUnmounted(() => {
    if (terminalPoll) clearInterval(terminalPoll)
  })

  return {
    terminalLines,
    terminalError,
    isStreaming,
    autoScroll,
    fetchLogs,
    startStream,
    stopStream,
    toggleStream
  }
}
