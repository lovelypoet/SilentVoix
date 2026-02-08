import { ref } from 'vue'

const resolutionOptions = {
  'Low (480)': { width: 640, height: 480 },
  'Medium (720)': { width: 1280, height: 720 },
  'High (1080)': { width: 1920, height: 1080 },
}

// --- Reactive State ---
const selectedCamera = ref(null)
const enableCamera = ref(true)
const resolution = ref('Medium (720)')
const mirrorCamera = ref(true)
const trainingMode = ref('Practice')
const countdown = ref(3)
const fps = ref(30)
const showLandmarks = ref(true)
const enableAISuggestions = ref(true) // New setting for AI suggestions

const cameraDevices = ref([])

export function useTrainingSettings() {

  const getCameraDevices = async () => {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices()
      cameraDevices.value = devices.filter(d => d.kind === 'videoinput')
      if (!selectedCamera.value && cameraDevices.value.length > 0) {
        selectedCamera.value = cameraDevices.value[0].deviceId
      }
    } catch (e) {
      console.error('Error enumerating media devices:', e)
    }
  }
  
  const resetSettings = () => {
    enableCamera.value = true
    resolution.value = 'Medium (480)'
    mirrorCamera.value = true
    trainingMode.value = 'Practice'
    countdown.value = 3
    showLandmarks.value = true
    // Don't reset the selected camera
  }

  return {
    selectedCamera,
    enableCamera,
    resolution,
    mirrorCamera,
    trainingMode,
    countdown,
    showLandmarks,
    fps,
    enableAISuggestions, // Add new setting
    cameraDevices,
    resolutionOptions,

    getCameraDevices,
    resetSettings,
  }
}
