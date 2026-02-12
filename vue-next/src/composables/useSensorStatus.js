import { ref, onMounted, onUnmounted } from 'vue'
import api from '../services/api'

export const useSensorStatus = () => {
  const serialStatus = ref({
    single_connected: false,
    left_connected: false,
    right_connected: false,
    available_ports: []
  })
  const sensorCaptureStatus = ref({ status: 'stopped', mode: 'single' })
  let serialPoll = null

  const fetchSerialStatus = async () => {
    try {
      const res = await api.utils.serialStatus()
      if (res?.data) {
        serialStatus.value = res.data
      }
    } catch (e) {
      // Keep last known status
    }
  }

  const fetchCaptureStatus = async () => {
    try {
      const res = await api.utils.sensorCapture.status()
      if (res) {
        sensorCaptureStatus.value = res
      }
    } catch (e) {
      // Keep last known status
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
    fetchSerialStatus()
    fetchCaptureStatus()
    serialPoll = setInterval(() => {
      fetchSerialStatus()
      fetchCaptureStatus()
    }, 3000)
  })

  onUnmounted(() => {
    if (serialPoll) clearInterval(serialPoll)
  })

  return {
    serialStatus,
    sensorCaptureStatus,
    fetchSerialStatus,
    fetchCaptureStatus,
    startSensorCapture,
    stopSensorCapture
  }
}
