/**
 * Draws bounding boxes and labels on a canvas.
 */
export function drawBoundingBox(ctx, bbox, options = {}) {
  const {
    landmarkColor = '#22d3ee',
    pointColor = '#ffffff',
    mirror = true,
    width = 640,
    height = 480,
    label = '',
    confidence = 0
  } = options

  if (!ctx || !bbox) return

  const [x1, y1, x2, y2] = bbox.map(v => Number(v))
  const boxWidth = Math.max(1, x2 - x1)
  const boxHeight = Math.max(1, y2 - y1)
  const drawX = mirror ? width - x2 : x1

  ctx.strokeStyle = landmarkColor
  ctx.lineWidth = 2
  ctx.strokeRect(drawX, y1, boxWidth, boxHeight)

  if (label) {
    const overlayText = `${label} ${(Number(confidence) * 100).toFixed(1)}%`
    ctx.fillStyle = 'rgba(2,6,23,0.8)'
    ctx.fillRect(drawX, Math.max(0, y1 - 24), 220, 20)
    ctx.fillStyle = pointColor
    ctx.font = '12px monospace'
    ctx.fillText(overlayText, drawX + 6, Math.max(12, y1 - 10))
  }
}

/**
 * Special version for results from local MediaPipe (array of hands).
 */
export function drawHandBoundingBoxes(ctx, hands, options = {}) {
  const {
    landmarkColor = '#22d3ee',
    pointColor = '#ffffff',
    mirror = true,
    width = 640,
    height = 480,
    label = '',
    confidence = 0
  } = options

  if (!ctx || !hands || !hands.length) return

  hands.forEach((hand) => {
    const xs = hand.map((p) => {
      const x = Number(p.x) * width
      return mirror ? width - x : x
    })
    const ys = hand.map((p) => Number(p.y) * height)
    const minX = Math.max(0, Math.min(...xs))
    const minY = Math.max(0, Math.min(...ys))
    const maxX = Math.min(width, Math.max(...xs))
    const maxY = Math.min(height, Math.max(...ys))

    const bbox = [
      mirror ? width - maxX : minX,
      minY,
      mirror ? width - minX : maxX,
      maxY
    ]
    
    drawBoundingBox(ctx, bbox, { 
      landmarkColor, 
      pointColor, 
      mirror, 
      width, 
      height, 
      label, 
      confidence 
    })
  })
}
