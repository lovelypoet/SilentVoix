import { ref } from 'vue'

/**
 * Composable to collect and save hand landmark data
 * 
 * @effect
 * - Collect hand landmarks from MediaPipe (supports 1 or 2 hands)
 * - Convert to CSV format with 21*3*2 = 126 features (Left hand first, then Right)
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

  /**
   * Add landmark data for one or two hands
   * @param {Array} landmarksArray - Array of landmark arrays from MediaPipe results.landmarks
   * @param {Array} handednessArray - Array of handedness objects from MediaPipe results.handedness
   */
  const addLandmark = (landmarksArray, handednessArray) => {
    if (!isCollecting.value) return
    if (!landmarksArray || landmarksArray.length === 0) return

    // Prepare slots for Left and Right hands
    let leftHand = null
    let rightHand = null
    
    for (let i = 0; i < landmarksArray.length && i < 2; i++) {
      const landmarks = landmarksArray[i]
      const handedness = handednessArray?.[i]?.[0]?.categoryName || 'Unknown'
      
      // Assign to correct slot based on handedness label
      if (handedness === 'Left') {
        leftHand = landmarks
      } else if (handedness === 'Right') {
        rightHand = landmarks
      }
    }

    // Create feature array [21*3*2] = 126 features
    // Format: [Left_hand_21_landmarks, Right_hand_21_landmarks]
    // Each landmark has x, y, z
    const features = []
    
    // Add Left hand data (or zeros if not detected)
    if (leftHand) {
      leftHand.forEach(lm => {
        features.push(lm.x, lm.y, lm.z)
      })
    } else {
      // Fill with zeros (21 landmarks * 3 coords = 63 values)
      for (let j = 0; j < 63; j++) {
        features.push(0)
      }
    }
    
    // Add Right hand data (or zeros if not detected)
    if (rightHand) {
      rightHand.forEach(lm => {
        features.push(lm.x, lm.y, lm.z)
      })
    } else {
      // Fill with zeros (21 landmarks * 3 coords = 63 values)
      for (let j = 0; j < 63; j++) {
        features.push(0)
      }
    }

    collectedLandmarks.value.push({
      gesture: currentGestureName.value,
      timestamp: Date.now(),
      L_exist: leftHand ? 1 : 0,
      R_exist: rightHand ? 1 : 0,
      features  // Array of 126 values
    })
  }

  /**
   * Convert collected data to CSV format
   */
  const convertToCSV = () => {
    let header = 'gesture,timestamp,L_exist,R_exist'
    
    // Add headers for Left hand (21 landmarks * 3 coords)
    for (let i = 0; i < 21; i++) {
      header += `,L_x${i},L_y${i},L_z${i}`
    }
    
    // Add headers for Right hand (21 landmarks * 3 coords)
    for (let i = 0; i < 21; i++) {
      header += `,R_x${i},R_y${i},R_z${i}`
    }
    
    let csv = header + '\n'

    // Add each frame to CSV
    collectedLandmarks.value.forEach(frame => {
      let row = `${frame.gesture},${frame.timestamp},${frame.L_exist},${frame.R_exist}`
      
      // Add all 126 feature values
      frame.features.forEach(value => {
        row += `,${value}`
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
    const d = new Date()
    const timestamp = `${d.getFullYear()}-${d.getMonth()+1}-${d.getDate()}_${d.getHours()}-${d.getMinutes()}-${d.getSeconds()}`
    a.download = `landmarks_${currentGestureName.value || 'data'}_${timestamp}.csv`
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