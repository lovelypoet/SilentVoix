import { ref } from 'vue'

/**
 * Composable to collect and save hand landmark data
 * 
 * @effect
 * - Collect hand landmarks from MediaPipe
 * - Convert to CSV format with 21*3*2 = 126 features 
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

  
  const addLandmark = (landmarksArray, handednessArray) => {
    if (!isCollecting.value) return
    if (!landmarksArray || landmarksArray.length === 0) return

    let leftHand = null
    let rightHand = null
    
    for (let i = 0; i < landmarksArray.length && i < 2; i++) {
      const landmarks = landmarksArray[i]
      const handedness = handednessArray?.[i]?.[0]?.categoryName || 'Unknown'
      
      // Assign to correct slot
      if (handedness === 'Left') {
        leftHand = landmarks
      } else if (handedness === 'Right') {
        rightHand = landmarks
      }
    }

    const features = []
    
    // Add Left hand data
    if (leftHand) {
      leftHand.forEach(lm => {
        features.push(lm.x, lm.y, lm.z)
      })
    } else {
      // Fill with zeros 
      for (let j = 0; j < 63; j++) {
        features.push(0)
      }
    }
    
    // Add Right hand data 
    if (rightHand) {
      rightHand.forEach(lm => {
        features.push(lm.x, lm.y, lm.z)
      })
    } else {
      // Fill with zeros 
      for (let j = 0; j < 63; j++) {
        features.push(0)
      }
    }

    collectedLandmarks.value.push({
      gesture: currentGestureName.value,
      timestamp: Date.now(),
      L_exist: leftHand ? 1 : 0,
      R_exist: rightHand ? 1 : 0,
      features  
    })
  }

  /**
   * Convert collected data to CSV format
   */
  const convertToCSV = () => {
    let header = 'gesture,timestamp,L_exist,R_exist'
    
    for (let i = 0; i < 21; i++) {
      header += `,L_x${i},L_y${i},L_z${i}`
    }
    
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