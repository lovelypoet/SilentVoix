import { ref } from 'vue'

export function useCollectData() {
  const collectedLandmarks = ref([])
  const isCollecting = ref(false)
  const currentGestureName = ref('')
  const takes = ref([])
  const takeLogs = ref([])
  const takeCounter = ref(0)
  const currentTakeId = ref(null)
  const autoGestureFolderIndex = ref(1)
  const autoDownloadRootHandle = ref(null)

  const metadata = ref({
    fps: 30,
    frame_limit: 100,
    preprocessing: []
  })

  const startCollecting = (gestureName) => {
    currentGestureName.value = gestureName
    isCollecting.value = true
    takeCounter.value += 1
    currentTakeId.value = takeCounter.value
    takeLogs.value.push(`take#${currentTakeId.value} started (${gestureName || 'unknown'})`)
  }

  const stopCollecting = () => {
    if (!isCollecting.value) return
    isCollecting.value = false
    finalizeTake()
  }

  const addLandmark = (landmarksArray, handednessArray, frameMeta = {}) => {
    if (!isCollecting.value) return
    const timestamp_ms = frameMeta.timestamp_ms ?? Date.now()
    const frame_id = frameMeta.frame_id ?? collectedLandmarks.value.length
    const take_id = frameMeta.take_id ?? currentTakeId.value
    const primary_hand = handednessArray?.[0]?.[0]?.categoryName || null
    if (!landmarksArray || landmarksArray.length === 0) {
      const features = []
      for (let i = 0; i < 126; i++) features.push(0)
      collectedLandmarks.value.push({
        gesture: currentGestureName.value,
        frame_id,
        timestamp_ms,
        take_id,
        primary_hand,
        take_quality: null,
        quality_score: null,
        bad_reasons: '',
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
      frame_id,
      timestamp_ms,
      take_id,
      primary_hand,
      take_quality: null,
      quality_score: null,
      bad_reasons: '',
      L_exist: leftHand ? 1 : 0,
      R_exist: rightHand ? 1 : 0,
      features
    })
  }

  const computeFlipCount = (frames) => {
    let flips = 0
    let last = null
    frames.forEach(frame => {
      if (!frame.primary_hand) return
      if (last && frame.primary_hand !== last) flips += 1
      last = frame.primary_hand
    })
    return flips
  }

  const finalizeTake = () => {
    if (currentTakeId.value === null) return
    const takeFrames = collectedLandmarks.value.filter(f => f.take_id === currentTakeId.value)
    const totalFrames = takeFrames.length
    const handFrames = takeFrames.filter(f => f.L_exist === 1 || f.R_exist === 1).length
    const frameLimit = metadata.value.frame_limit || 0
    const framePct = frameLimit ? totalFrames / frameLimit : 1
    const handPresencePct = totalFrames ? handFrames / totalFrames : 0
    const flipCount = computeFlipCount(takeFrames)

    const reasons = []
    let score = 100

    if (framePct < 0.7) {
      reasons.push('insufficient frames')
      score -= 25
    }

    if (handPresencePct < 0.9) {
      reasons.push('hand missing too often')
      score -= 25
    }

    if (flipCount > 1) {
      reasons.push('handedness flip detected')
      score -= Math.min(20, 5 + (flipCount - 1) * 5)
    }

    score = Math.max(0, Math.min(100, Math.round(score)))
    let quality = 'Good'
    if (score < 60) quality = 'Bad'
    else if (score < 80) quality = 'Borderline'

    const bad_reasons = reasons.join('; ')
    takeFrames.forEach(frame => {
      frame.take_quality = quality
      frame.quality_score = score
      frame.bad_reasons = bad_reasons
    })

    const t_start_ms = totalFrames ? takeFrames[0].timestamp_ms : null
    const t_end_ms = totalFrames ? takeFrames[totalFrames - 1].timestamp_ms : null

    takes.value.push({
      take_id: currentTakeId.value,
      label: currentGestureName.value || 'unknown',
      frames: totalFrames,
      frame_limit: frameLimit,
      frame_pct: framePct,
      hand_presence_pct: handPresencePct,
      flip_count: flipCount,
      quality_score: score,
      quality,
      bad_reasons,
      t_start_ms,
      t_end_ms
    })

    takeLogs.value.push(
      `take#${currentTakeId.value} ${quality.toLowerCase()} (${score})` +
      (bad_reasons ? ` - ${bad_reasons}` : '')
    )

    currentTakeId.value = null
  }

  const convertToCSV = () => {
    let header = 'frame_id,timestamp_ms,gesture,primary_hand,L_exist,R_exist,L_missing,R_missing'

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
      let row = `${frame.frame_id},${frame.timestamp_ms},${frame.gesture},` +
        `${frame.primary_hand ?? ''},` +
        `${frame.L_exist},${frame.R_exist},${L_missing},${R_missing}`
      frame.features.forEach(v => {
        row += `,${v}`
      })
      csv += row + '\n'
    })

    return csv
  }

  const buildExportId = () => {
    const d = new Date()
    const timestamp =
      `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}_` +
      `${d.getHours()}-${d.getMinutes()}-${d.getSeconds()}`
    const suffix = Math.random().toString(36).slice(2, 6)
    return `${timestamp}_${suffix}`
  }

  const nextGestureFolderName = () => {
    const folderName = `gesture_${String(autoGestureFolderIndex.value).padStart(3, '0')}`
    autoGestureFolderIndex.value = autoGestureFolderIndex.value >= 10 ? 1 : autoGestureFolderIndex.value + 1
    return folderName
  }

  const sanitizeFileName = (value) => (value || 'data').replace(/[\\/:*?"<>|]+/g, '_')

  const buildMetadata = (exportId = null) => {
    const hasLeft = collectedLandmarks.value.some(f => f.L_exist === 1)
    const hasRight = collectedLandmarks.value.some(f => f.R_exist === 1)
    const leftMissing = collectedLandmarks.value.filter(f => f.L_exist === 0).length
    const rightMissing = collectedLandmarks.value.filter(f => f.R_exist === 0).length
    const totalFrames = collectedLandmarks.value.length
    const t_start_ms = totalFrames ? collectedLandmarks.value[0].timestamp_ms : null
    const t_end_ms = totalFrames ? collectedLandmarks.value[totalFrames - 1].timestamp_ms : null

    let hands = 'none'
    if (hasLeft && hasRight) hands = 'both'
    else if (hasLeft) hands = 'left'
    else if (hasRight) hands = 'right'

    return {
      label: currentGestureName.value || 'unknown',
      fps: metadata.value.fps,
      frame_limit: metadata.value.frame_limit,
      hands,
      frames: totalFrames,
      t_start_ms,
      t_end_ms,
      duration_ms: (t_start_ms !== null && t_end_ms !== null) ? (t_end_ms - t_start_ms) : 0,
      left_missing_frames: leftMissing,
      right_missing_frames: rightMissing,
      left_missing_rate: totalFrames ? leftMissing / totalFrames : 0,
      right_missing_rate: totalFrames ? rightMissing / totalFrames : 0,
      features: 126,
      preprocessing: metadata.value.preprocessing,
      export_id: exportId,
      created_at: new Date().toISOString()
    }
  }

  const buildTakeMetadata = (exportId = null) => ({
    export_id: exportId,
    label: currentGestureName.value || 'unknown',
    fps: metadata.value.fps,
    frame_limit: metadata.value.frame_limit,
    created_at: new Date().toISOString(),
    takes: takes.value
  })

  const downloadMetadata = (exportId = null) => {
    const meta = buildMetadata(exportId)

    const blob = new Blob(
      [JSON.stringify(meta, null, 2)],
      { type: 'application/json' }
    )

    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `landmarks_${currentGestureName.value || 'data'}_${exportId || 'metadata'}_metadata.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const writeTextFile = async (dirHandle, fileName, content) => {
    const fileHandle = await dirHandle.getFileHandle(fileName, { create: true })
    const writable = await fileHandle.createWritable()
    await writable.write(content)
    await writable.close()
  }

  const supportsFolderWrite = () =>
    typeof window !== 'undefined' && typeof window.showDirectoryPicker === 'function'

  const prepareAutoDownloadFolder = async () => {
    if (!supportsFolderWrite()) return false
    if (autoDownloadRootHandle.value) return true
    autoDownloadRootHandle.value = await window.showDirectoryPicker({ mode: 'readwrite' })
    return true
  }

  const saveThreeFilesToFolder = async (folderData) => {
    if (!supportsFolderWrite()) return false

    if (!autoDownloadRootHandle.value) return false

    const folderName = nextGestureFolderName()
    const folderHandle = await autoDownloadRootHandle.value.getDirectoryHandle(folderName, { create: true })

    await writeTextFile(
      folderHandle,
      `landmarks_${folderData.gestureName}_${folderData.exportId}.csv`,
      folderData.csvContent
    )
    await writeTextFile(
      folderHandle,
      `landmarks_${folderData.gestureName}_${folderData.exportId}_metadata.json`,
      JSON.stringify(folderData.metaPayload, null, 2)
    )
    await writeTextFile(
      folderHandle,
      `takes_${folderData.gestureName}_${folderData.exportId}.json`,
      JSON.stringify(folderData.takePayload, null, 2)
    )

    takeLogs.value.push(`auto-saved to folder ${folderName}`)
    return true
  }

  const downloadCSV = async () => {
    if (collectedLandmarks.value.length === 0) return
    const exportId = buildExportId()
    const gestureName = sanitizeFileName(currentGestureName.value || 'data')
    const csvContent = convertToCSV()
    const metaPayload = buildMetadata(exportId)
    const takePayload = buildTakeMetadata(exportId)

    try {
      const wroteFolder = await saveThreeFilesToFolder({
        exportId,
        gestureName,
        csvContent,
        metaPayload,
        takePayload
      })
      if (wroteFolder) return
    } catch (error) {
      console.error('Auto folder download failed, fallback to file downloads:', error)
    }

    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `landmarks_${gestureName}_${exportId}.csv`
    a.click()
    URL.revokeObjectURL(url)

    const metaBlob = new Blob([JSON.stringify(metaPayload, null, 2)], { type: 'application/json' })
    const metaUrl = URL.createObjectURL(metaBlob)
    const metaA = document.createElement('a')
    metaA.href = metaUrl
    metaA.download = `landmarks_${gestureName}_${exportId}_metadata.json`
    metaA.click()
    URL.revokeObjectURL(metaUrl)

    const takeBlob = new Blob([JSON.stringify(takePayload, null, 2)], { type: 'application/json' })
    const takeUrl = URL.createObjectURL(takeBlob)
    const takeA = document.createElement('a')
    takeA.href = takeUrl
    takeA.download = `takes_${gestureName}_${exportId}.json`
    takeA.click()
    URL.revokeObjectURL(takeUrl)
  }

  const downloadTakeMetadata = (exportId = null) => {
    if (!takes.value.length) return
    const payload = buildTakeMetadata(exportId)
    const blob = new Blob(
      [JSON.stringify(payload, null, 2)],
      { type: 'application/json' }
    )

    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')

    a.href = url
    a.download = `takes_${currentGestureName.value || 'data'}_${exportId || 'metadata'}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const clearData = () => {
    collectedLandmarks.value = []
    takes.value = []
    takeLogs.value = []
    takeCounter.value = 0
    currentTakeId.value = null
  }

  return {
    collectedLandmarks,
    isCollecting,
    currentGestureName,
    metadata,
    takes,
    takeLogs,
    startCollecting,
    stopCollecting,
    addLandmark,
    downloadCSV,
    downloadMetadata,
    downloadTakeMetadata,
    prepareAutoDownloadFolder,
    clearData,
    convertToCSV
  }
}
