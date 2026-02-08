import { ref } from 'vue'

export function useCollectData() {
  const collectedLandmarks = ref([])
  const isCollecting = ref(false)
  const currentGestureName = ref('')

  const metadata = ref({
    fps: 30,
    preprocessing: []
  })

  const startCollecting = (gestureName) => {
    currentGestureName.value = gestureName
    isCollecting.value = true
  }

  const stopCollecting = () => {
    isCollecting.value = false
  }

  const addLandmark = (landmarksArray, handednessArray) => {
    if (!isCollecting.value) return
    if (!landmarksArray || landmarksArray.length === 0) {
      const features = []
      for (let i = 0; i < 126; i++) features.push(0)
      collectedLandmarks.value.push({
        gesture: currentGestureName.value,
        timestamp: Date.now(),
        L_exist: 0,
        R_exist: 0,
        features
      })
      return
    }

    let leftHand = null
    let rightHand = null

    for (let i = 0; i < landmarksArray.length && i < 2; i++) {
      const landmarks = landmarksArray[i]
      const handednessInfo = handednessArray?.[i]?.[0]
      if (!handednessInfo) continue

      const hand = handednessInfo.categoryName

      if (hand === 'Left') leftHand = landmarks
      else if (hand === 'Right') rightHand = landmarks
    }

    const features = []

    if (leftHand) {
      leftHand.forEach(lm => features.push(lm.x, lm.y, lm.z))
    } else {
      for (let i = 0; i < 63; i++) features.push(0)
    }

    if (rightHand) {
      rightHand.forEach(lm => features.push(lm.x, lm.y, lm.z))
    } else {
      for (let i = 0; i < 63; i++) features.push(0)
    }

    collectedLandmarks.value.push({
      gesture: currentGestureName.value,
      timestamp: Date.now(),
      L_exist: leftHand ? 1 : 0,
      R_exist: rightHand ? 1 : 0,
      features
    })
  }

  const convertToCSV = () => {
    let header = 'gesture,timestamp,L_exist,R_exist,L_missing,R_missing'

    for (let i = 0; i < 21; i++) {
      header += `,L_x${i},L_y${i},L_z${i}`
    }

    for (let i = 0; i < 21; i++) {
      header += `,R_x${i},R_y${i},R_z${i}`
    }

    let csv = header + '\n'

    collectedLandmarks.value.forEach(frame => {
      const L_missing = frame.L_exist ? 0 : 1
      const R_missing = frame.R_exist ? 0 : 1
      let row = `${frame.gesture},${frame.timestamp},${frame.L_exist},${frame.R_exist},${L_missing},${R_missing}`
      frame.features.forEach(v => {
        row += `,${v}`
      })
      csv += row + '\n'
    })

    return csv
  }

  const downloadMetadata = () => {
    const hasLeft = collectedLandmarks.value.some(f => f.L_exist === 1)
    const hasRight = collectedLandmarks.value.some(f => f.R_exist === 1)
    const leftMissing = collectedLandmarks.value.filter(f => f.L_exist === 0).length
    const rightMissing = collectedLandmarks.value.filter(f => f.R_exist === 0).length
    const totalFrames = collectedLandmarks.value.length

    let hands = 'none'
    if (hasLeft && hasRight) hands = 'both'
    else if (hasLeft) hands = 'left'
    else if (hasRight) hands = 'right'

    const meta = {
      label: currentGestureName.value || 'unknown',
      fps: metadata.value.fps,
      hands,
      frames: totalFrames,
      left_missing_frames: leftMissing,
      right_missing_frames: rightMissing,
      left_missing_rate: totalFrames ? leftMissing / totalFrames : 0,
      right_missing_rate: totalFrames ? rightMissing / totalFrames : 0,
      features: 128,
      preprocessing: metadata.value.preprocessing,
      created_at: new Date().toISOString()
    }

    const blob = new Blob(
      [JSON.stringify(meta, null, 2)],
      { type: 'application/json' }
    )

    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `landmarks_${currentGestureName.value || 'data'}_metadata.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const downloadCSV = () => {
    if (collectedLandmarks.value.length === 0) return

    const csv = convertToCSV()
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')

    const d = new Date()
    const timestamp =
      `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}_` +
      `${d.getHours()}-${d.getMinutes()}-${d.getSeconds()}`

    a.href = url
    a.download = `landmarks_${currentGestureName.value || 'data'}_${timestamp}.csv`
    a.click()
    URL.revokeObjectURL(url)

    downloadMetadata()
  }

  const clearData = () => {
    collectedLandmarks.value = []
  }

  return {
    collectedLandmarks,
    isCollecting,
    currentGestureName,
    metadata,
    startCollecting,
    stopCollecting,
    addLandmark,
    downloadCSV,
    downloadMetadata,
    clearData,
    convertToCSV
  }
}
