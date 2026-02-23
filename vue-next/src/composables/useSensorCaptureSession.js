import { onMounted, onUnmounted, ref } from 'vue'
import api from '../services/api'

export function useSensorCaptureSession() {
  const sensorCaptureStatus = ref({ status: 'stopped', mode: 'single' })
  const captureError = ref('')
  let capturePoll = null

  const fetchCaptureStatus = async () => {
    try {
      const res = await api.utils.sensorCapture.status()
      if (res) {
        sensorCaptureStatus.value = res
      }
      captureError.value = ''
    } catch (_) {
      captureError.value = 'Unable to reach sensor capture status endpoint.'
    }
  }

  const startSensorCapture = async (mode) => {
    await api.utils.sensorCapture.start(mode)
    await fetchCaptureStatus()
  }

  const stopSensorCapture = async () => {
    await api.utils.sensorCapture.stop()
    await fetchCaptureStatus()
  }

  onMounted(() => {
    fetchCaptureStatus()
    capturePoll = setInterval(() => {
      fetchCaptureStatus()
    }, 3000)
  })

  onUnmounted(() => {
    if (capturePoll) clearInterval(capturePoll)
  })

  return {
    captureError,
    fetchCaptureStatus,
    sensorCaptureStatus,
    startSensorCapture,
    stopSensorCapture
  }
}
