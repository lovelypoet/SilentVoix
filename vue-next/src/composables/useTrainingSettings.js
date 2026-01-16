import { ref } from 'vue'

const resolutionOptions = {
  'Low': { width: 640, height: 480 },
  'Medium': { width: 1280, height: 720 },
  'High': { width: 1920, height: 1080 },
}

// --- Reactive State ---
const selectedCamera = ref(null)
const enableCamera = ref(true)
const resolution = ref('Medium')
const mirrorCamera = ref(true)
const trainingMode = ref('Practice')
const countdown = ref(3)
const showLandmarks = ref(true)

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
    resolution.value = 'Medium'
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
    
    cameraDevices,
    resolutionOptions,

    getCameraDevices,
    resetSettings,
  }
}
