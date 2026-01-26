import { ref } from 'vue'

/**
 * Composable to collect and save hand landmark data
 * 
 * @effect
 * - Collect hand landmarks from MediaPipe
 * - Convert to CSV format
 * - Download CSV file
 */
export function useCollectData() {

  const collectedLandmarks = ref([])
  const isCollecting = ref(false)
  const currentGestureName = ref('')

  const startCollecting = (gestureName) => {
    currentGestureName.value = gestureName
    isCollecting.value = true
  }


  const stopCollecting = () => {
    isCollecting.value = false
  }


  const addLandmark = (landmarks, handedness = 'Right') => {
    // Only collect when recording
    if (!isCollecting.value) return

    collectedLandmarks.value.push({
      gesture: currentGestureName.value,
      timestamp: Date.now(),
      handedness,
      landmarks
    })
  }

  /**
   * Convert collected data to CSV format
   * 
   */
  const convertToCSV = () => {
    let header = 'gesture,timestamp,handedness'
    for (let i = 0; i < 21; i++) {
      header += `,x${i},y${i},z${i}`
    }
    let csv = header + '\n'

    // Add each frame to CSV
    collectedLandmarks.value.forEach(frame => {
      // Basic info
      let row = `${frame.gesture},${frame.timestamp},${frame.handedness}`
      
      // Add coordinates of 21 landmarks (x, y, z)
      frame.landmarks.forEach(lm => {
        row += `,${lm.x},${lm.y},${lm.z}`
      })
      
      csv += row + '\n'
    })

    return csv
  }

  /**
   * Download CSV file
   */
  const downloadCSV = () => {
    const csv = convertToCSV()
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `landmarks_${currentGestureName.value || 'data'}_${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(url)
    
    console.log(`Downloaded ${collectedLandmarks.value.length} frames as ${a.download}`)
  }

  /**
   * Clear all collected data
   */
  const clearData = () => {
    collectedLandmarks.value = []
  }

  return {
    collectedLandmarks,
    isCollecting,
    currentGestureName,

    startCollecting,
    stopCollecting,
    addLandmark,
    downloadCSV,
    clearData,
    convertToCSV
  }
}