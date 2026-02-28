import { onMounted, onUnmounted, ref } from 'vue'
import api from '../services/api'

const DEFAULT_STATUS = {
  single_port: '',
  left_port: '',
  right_port: '',
  available_ports: [],
  single_connected: false,
  left_connected: false,
  right_connected: false
}
const POLL_INTERVAL_MS = 2000

export function usePortSession() {
  const serialStatus = ref({ ...DEFAULT_STATUS })
  const isLoading = ref(false)
  const isUpdatingConfig = ref(false)
  const error = ref('')
  const message = ref('')
  const autoRefresh = ref(true)
  const lastCheckedAt = ref(null)
  const consecutiveFailures = ref(0)
  let poll = null

  const fetchSerialStatus = async () => {
    isLoading.value = true
    try {
      const res = await api.utils.serialStatus()
      serialStatus.value = res?.data ? res.data : { ...DEFAULT_STATUS }
      error.value = ''
      message.value = ''
      consecutiveFailures.value = 0
      lastCheckedAt.value = new Date()
    } catch (e) {
      error.value = 'Unable to reach backend serial-status endpoint.'
      consecutiveFailures.value += 1
      if (consecutiveFailures.value >= 3) {
        autoRefresh.value = false
      }
    } finally {
      isLoading.value = false
    }
  }

  const startPolling = () => {
    if (poll) clearInterval(poll)
    poll = setInterval(() => {
      if (!autoRefresh.value) return
      fetchSerialStatus()
    }, POLL_INTERVAL_MS)
  }

  const stopPolling = () => {
    if (!poll) return
    clearInterval(poll)
    poll = null
  }

  const applyAutoDetectedPorts = async () => {
    isUpdatingConfig.value = true
    try {
      const res = await api.utils.serialConfig.auto()
      if (res?.data) {
        serialStatus.value = res.data
      }
      message.value = 'Serial port config updated from detected ports.'
      error.value = ''
      autoRefresh.value = true
      consecutiveFailures.value = 0
      lastCheckedAt.value = new Date()
    } catch (_) {
      error.value = 'Auto-detect failed. No ports detected or backend unavailable.'
      message.value = ''
    } finally {
      isUpdatingConfig.value = false
    }
  }

  const applySinglePort = async (singlePort) => {
    if (!singlePort) {
      error.value = 'Select a port first.'
      return
    }
    isUpdatingConfig.value = true
    try {
      const payload = {
        single_port: singlePort,
        left_port: singlePort,
        right_port: singlePort,
      }
      const res = await api.utils.serialConfig.update(payload)
      if (res?.data) {
        serialStatus.value = res.data
      }
      message.value = `Configured ports updated to ${singlePort}.`
      error.value = ''
      autoRefresh.value = true
      consecutiveFailures.value = 0
      lastCheckedAt.value = new Date()
    } catch (_) {
      error.value = 'Failed to update serial port config.'
      message.value = ''
    } finally {
      isUpdatingConfig.value = false
    }
  }

  onMounted(() => {
    fetchSerialStatus()
    startPolling()
  })

  onUnmounted(() => {
    stopPolling()
  })

  return {
    applyAutoDetectedPorts,
    applySinglePort,
    autoRefresh,
    error,
    fetchSerialStatus,
    isLoading,
    isUpdatingConfig,
    lastCheckedAt,
    message,
    serialStatus
  }
}
