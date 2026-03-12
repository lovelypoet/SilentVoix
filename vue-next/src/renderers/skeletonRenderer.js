/**
 * Draws the hand skeleton on a canvas.
 */
export function drawSkeleton(ctx, landmarks, options = {}) {
  const {
    landmarkColor = '#22d3ee',
    pointColor = '#ffffff',
    lineWidth = 3,
    pointRadius = 4,
    mirror = true,
    width = 640,
    height = 480
  } = options

  if (!ctx || !landmarks) return

  // Standard hand skeleton connections
  const connections = [
    [0, 1], [1, 2], [2, 3], [3, 4], // thumb
    [0, 5], [5, 6], [6, 7], [7, 8], // index
    [5, 9], [9, 10], [10, 11], [11, 12], // middle
    [9, 13], [13, 14], [14, 15], [15, 16], // ring
    [13, 17], [17, 18], [18, 19], [19, 20], // pinky
    [0, 17] // palm base
  ]

  ctx.strokeStyle = landmarkColor
  ctx.fillStyle = pointColor
  ctx.lineWidth = lineWidth

  landmarks.forEach((pt) => {
    // Backend landmarks are [x, y], frontend might be {x, y}
    const xVal = Array.isArray(pt) ? pt[0] : pt.x
    const yVal = Array.isArray(pt) ? pt[1] : pt.y
    
    const x = Number(xVal) * width
    const y = Number(yVal) * height
    const actualX = mirror ? width - x : x

    ctx.beginPath()
    ctx.arc(actualX, y, pointRadius, 0, 2 * Math.PI)
    ctx.fill()
  })

  ctx.beginPath()
  connections.forEach(([i, j]) => {
    const p1 = landmarks[i]
    const p2 = landmarks[j]
    if (!p1 || !p2) return

    const x1Val = Array.isArray(p1) ? p1[0] : p1.x
    const y1Val = Array.isArray(p1) ? p1[1] : p1.y
    const x2Val = Array.isArray(p2) ? p2[0] : p2.x
    const y2Val = Array.isArray(p2) ? p2[1] : p2.y

    const x1 = Number(x1Val) * width
    const y1 = Number(y1Val) * height
    const x2 = Number(x2Val) * width
    const y2 = Number(y2Val) * height

    const ax1 = mirror ? width - x1 : x1
    const ax2 = mirror ? width - x2 : x2

    ctx.moveTo(ax1, y1)
    ctx.lineTo(ax2, y2)
  })
  ctx.stroke()
}
