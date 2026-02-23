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

export function usePortSession() {
  const serialStatus = ref({ ...DEFAULT_STATUS })
  const isLoading = ref(false)
  const error = ref('')
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
    }, 5000)
  }

  const stopPolling = () => {
    if (!poll) return
    clearInterval(poll)
    poll = null
  }

  onMounted(() => {
    fetchSerialStatus()
    startPolling()
  })

  onUnmounted(() => {
    stopPolling()
  })

  return {
    autoRefresh,
    error,
    fetchSerialStatus,
    isLoading,
    lastCheckedAt,
    serialStatus
  }
}
