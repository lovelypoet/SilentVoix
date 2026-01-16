import { ref, onUnmounted, watch } from 'vue'
import { useTrainingSettings } from './useTrainingSettings'

export function useMediaPermissions() {
  const { 
    selectedCamera, 
    resolution, 
    resolutionOptions,
    enableCamera,
  } = useTrainingSettings()

  const hasPermissions = ref(false)
  const isRequesting = ref(false)
  const error = ref(null)
  const stream = ref(null)

  const requestPermissions = async () => {
    if (!enableCamera.value) {
      stopStream()
      return
    }

    isRequesting.value = true
    error.value = null
    
    const videoConstraints = {
      deviceId: selectedCamera.value ? { exact: selectedCamera.value } : undefined,
      ...resolutionOptions[resolution.value]
    };

    try {
      // Stop previous stream before starting a new one
      if (stream.value) {
        stream.value.getTracks().forEach(track => track.stop())
      }
      stream.value = await navigator.mediaDevices.getUserMedia({ video: videoConstraints, audio: true })
      hasPermissions.value = true
    } catch (e) {
      console.error('Error requesting media permissions:', e)
      error.value = e
      hasPermissions.value = false
      stream.value = null
    } finally {
      isRequesting.value = false
    }
  }

  const stopStream = () => {
    if (stream.value) {
      stream.value.getTracks().forEach(track => track.stop())
    }
    stream.value = null
    // Note: Don't set hasPermissions to false here, 
    // because the user has granted permissions, they just disabled the camera.
  }

  // Watch for changes in settings and re-request permissions
  watch([selectedCamera, resolution], () => {
    if (stream.value && enableCamera.value) {
      requestPermissions()
    }
  })

  watch(enableCamera, (newValue) => {
    if (newValue) {
      requestPermissions()
    } else {
      stopStream()
    }
  })

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
