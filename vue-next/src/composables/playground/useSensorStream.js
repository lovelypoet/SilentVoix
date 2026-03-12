import { ref, computed, onUnmounted } from 'vue'
import api from '@/services/api'

export function useSensorStream() {
  const sensorSnapshot = ref({
    values: [],
    realSensor: false,
    updatedAt: null
  })
  const sensorStreamWs = ref(null)
  const isConnected = ref(false)
  const isDesired = ref(false)

  const updatedAtText = computed(() => {
    const ts = sensorSnapshot.value?.updatedAt
    if (!ts) return '--'
    const d = new Date(ts)
    return Number.isNaN(d.getTime()) ? '--' : d.toLocaleTimeString()
  })

  const start = () => {
    if (sensorStreamWs.value) return
    isDesired.value = true
    const ws = api.createWebSocket('/ws/stream')
    sensorStreamWs.value = ws
    isConnected.value = false

    ws.onopen = () => {
      isConnected.value = true
      try {
        ws.send(JSON.stringify({ type: 'subscribe' }))
      } catch (e) {
        console.error('Failed to send subscribe message:', e)
      }
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg?.type === 'sensor_frame' && Array.isArray(msg.values)) {
          sensorSnapshot.value = {
            values: msg.values,
            realSensor: true,
            updatedAt: Date.now()
          }
        }
      } catch (e) {
        // ignore malformed frames
      }
    }

    ws.onerror = () => {
      isConnected.value = false
      try {
        ws.close()
      } catch (e) {
        // ignore
      }
    }

    ws.onclose = () => {
      isConnected.value = false
      if (sensorSnapshot.value?.realSensor) {
        sensorSnapshot.value = {
          ...sensorSnapshot.value,
          realSensor: false
        }
      }
      if (isDesired.value) {
        sensorStreamWs.value = null
        setTimeout(() => {
          if (isDesired.value && !sensorStreamWs.value) {
            start()
          }
        }, 1000)
      }
    }
  }

  const stop = () => {
    isDesired.value = false
    if (sensorStreamWs.value) {
      try {
        sensorStreamWs.value.close()
      } catch (e) {
        // ignore
      }
    }
    sensorStreamWs.value = null
    isConnected.value = false
  }

  onUnmounted(() => {
    stop()
  })

  return {
    sensorSnapshot,
    isConnected,
    isDesired,
    updatedAtText,
    start,
    stop
  }
}
