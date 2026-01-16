import { ref, onUnmounted } from 'vue'

export function useMediaPermissions() {
  const hasPermissions = ref(false)
  const isRequesting = ref(false)
  const error = ref(null)
  const stream = ref(null)

  const requestPermissions = async () => {
    isRequesting.value = true
    error.value = null
    try {
      stream.value = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
      hasPermissions.value = true
    } catch (e) {
      console.error('Error requesting media permissions:', e)
      error.value = e
      hasPermissions.value = false
    } finally {
      isRequesting.value = false
    }
  }

  const stopStream = () => {
    if (stream.value) {
      stream.value.getTracks().forEach(track => track.stop())
      stream.value = null
      hasPermissions.value = false
    }
  }

  onUnmounted(() => {
    stopStream()
  })

  return {
    hasPermissions,
    isRequesting,
    error,
    stream,
    requestPermissions,
    stopStream,
  }
}
