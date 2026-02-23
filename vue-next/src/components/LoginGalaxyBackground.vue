<script setup>
import { onMounted, onBeforeUnmount, ref } from 'vue'
import * as THREE from 'three'

const containerRef = ref(null)

let renderer
let scene
let camera
let animationId
let time = 0

const mouse = { x: 0, y: 0 }
const target = { x: 0, y: 0 }

let farStars
let nebula
let galaxy
let closeStars

let farStarsGeometry
let nebulaGeometry
let galaxyGeometry
let closeStarsGeometry

let farStarsMaterial
let nebulaMaterial
let galaxyMaterial
let closeStarsMaterial

let onMouseMove
let onResize

const createParticleTexture = () => {
  const canvas = document.createElement('canvas')
  canvas.width = 64
  canvas.height = 64
  const ctx = canvas.getContext('2d')

  const gradient = ctx.createRadialGradient(32, 32, 0, 32, 32, 32)
  gradient.addColorStop(0, 'rgba(255, 255, 255, 1)')
  gradient.addColorStop(0.12, 'rgba(196, 255, 251, 0.95)')
  gradient.addColorStop(0.35, 'rgba(45, 212, 191, 0.55)')
  gradient.addColorStop(0.7, 'rgba(20, 184, 166, 0.2)')
  gradient.addColorStop(1, 'rgba(255, 255, 255, 0)')

  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, 64, 64)

  return new THREE.CanvasTexture(canvas)
}

const buildFarStars = (texture) => {
  farStarsGeometry = new THREE.BufferGeometry()
  const count = 9000
  const positions = new Float32Array(count * 3)
  const sizes = new Float32Array(count)
  const colors = new Float32Array(count * 3)

  for (let i = 0; i < count; i++) {
    const i3 = i * 3
    const theta = Math.random() * Math.PI * 2
    const phi = Math.acos(2 * Math.random() - 1)
    const radius = 38 + Math.random() * 62

    positions[i3] = radius * Math.sin(phi) * Math.cos(theta)
    positions[i3 + 1] = radius * Math.sin(phi) * Math.sin(theta)
    positions[i3 + 2] = radius * Math.cos(phi)

    sizes[i] = Math.random() * 0.75 + 0.2

    const colorType = Math.random()
    if (colorType < 0.65) {
      colors[i3] = 0.92
      colors[i3 + 1] = 1
      colors[i3 + 2] = 0.98
    } else if (colorType < 0.85) {
      colors[i3] = 0.65
      colors[i3 + 1] = 0.95
      colors[i3 + 2] = 1
    } else {
      colors[i3] = 0.45
      colors[i3 + 1] = 0.9
      colors[i3 + 2] = 0.85
    }
  }

  farStarsGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  farStarsGeometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1))
  farStarsGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))

  farStarsMaterial = new THREE.PointsMaterial({
    size: 0.000001,
    sizeAttenuation: true,
    transparent: true,
    opacity: 0.82,
    map: texture,
    vertexColors: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  })

  farStars = new THREE.Points(farStarsGeometry, farStarsMaterial)
  scene.add(farStars)
}

const buildNebula = (texture) => {
  nebulaGeometry = new THREE.BufferGeometry()
  const count = 2200
  const positions = new Float32Array(count * 3)
  const colors = new Float32Array(count * 3)
  const sizes = new Float32Array(count)

  for (let i = 0; i < count; i++) {
    const i3 = i * 3

    positions[i3] = (Math.random() - 0.5) * 32
    positions[i3 + 1] = (Math.random() - 0.5) * 32
    positions[i3 + 2] = (Math.random() - 0.5) * 32
    sizes[i] = Math.random() * 3.7 + 1.4

    const color = new THREE.Color()
    if (Math.random() < 0.5) {
      color.setHSL(0.47, 0.75, 0.34)
    } else {
      color.setHSL(0.53, 0.85, 0.4)
    }
    colors[i3] = color.r
    colors[i3 + 1] = color.g
    colors[i3 + 2] = color.b
  }

  nebulaGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  nebulaGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))
  nebulaGeometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1))

  nebulaMaterial = new THREE.PointsMaterial({
    size: 0.14,
    sizeAttenuation: true,
    transparent: true,
    opacity: 0.22,
    map: texture,
    vertexColors: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  })

  nebula = new THREE.Points(nebulaGeometry, nebulaMaterial)
  scene.add(nebula)
}

const buildGalaxy = (texture) => {
  galaxyGeometry = new THREE.BufferGeometry()
  const count = 20000
  const positions = new Float32Array(count * 3)
  const colors = new Float32Array(count * 3)
  const sizes = new Float32Array(count)

  const coreColor = new THREE.Color(0xe9fffb)
  const armColor1 = new THREE.Color(0x38bdf8)
  const armColor2 = new THREE.Color(0x14b8a6)
  const armColor3 = new THREE.Color(0x2dd4bf)
  const outerColor = new THREE.Color(0x0f766e)

  for (let i = 0; i < count; i++) {
    const i3 = i * 3
    const radius = Math.random() * Math.random() * 6.2
    const spinAngle = radius * 2.55
    const branchAngle = ((i % 4) / 4) * Math.PI * 2

    const randomRadius = Math.pow(Math.random(), 2) * 0.42
    const randomAngle = Math.random() * Math.PI * 2
    const randomX = Math.cos(randomAngle) * randomRadius
    const randomZ = Math.sin(randomAngle) * randomRadius
    const randomY = (Math.random() - 0.5) * 0.22 * Math.pow(Math.random(), 3)

    positions[i3] = Math.cos(branchAngle + spinAngle) * radius + randomX
    positions[i3 + 1] = randomY
    positions[i3 + 2] = Math.sin(branchAngle + spinAngle) * radius + randomZ

    const normalizedRadius = radius / 6.2
    const mixedColor = new THREE.Color()
    if (normalizedRadius < 0.2) {
      mixedColor.lerpColors(coreColor, armColor1, normalizedRadius * 5)
    } else if (normalizedRadius < 0.5) {
      mixedColor.lerpColors(armColor1, armColor2, (normalizedRadius - 0.2) * 3.33)
    } else if (normalizedRadius < 0.75) {
      mixedColor.lerpColors(armColor2, armColor3, (normalizedRadius - 0.5) * 4)
    } else {
      mixedColor.lerpColors(armColor3, outerColor, (normalizedRadius - 0.75) * 4)
    }

    colors[i3] = mixedColor.r
    colors[i3 + 1] = mixedColor.g
    colors[i3 + 2] = mixedColor.b
    sizes[i] = Math.random() * 1.5 + 0.5
  }

  galaxyGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  galaxyGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))
  galaxyGeometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1))

  galaxyMaterial = new THREE.PointsMaterial({
    size: 0.03,
    sizeAttenuation: true,
    vertexColors: true,
    transparent: true,
    opacity: 0.95,
    blending: THREE.AdditiveBlending,
    map: texture,
    depthWrite: false
  })

  galaxy = new THREE.Points(galaxyGeometry, galaxyMaterial)
  scene.add(galaxy)
}

const buildCloseStars = (texture) => {
  closeStarsGeometry = new THREE.BufferGeometry()
  const count = 180
  const positions = new Float32Array(count * 3)
  const sizes = new Float32Array(count)
  const colors = new Float32Array(count * 3)

  for (let i = 0; i < count; i++) {
    const i3 = i * 3
    positions[i3] = (Math.random() - 0.5) * 16
    positions[i3 + 1] = (Math.random() - 0.5) * 16
    positions[i3 + 2] = (Math.random() - 0.5) * 10 - 2
    sizes[i] = Math.random() * 1.5 + 0.5
    colors[i3] = 0.95
    colors[i3 + 1] = 1
    colors[i3 + 2] = 0.98
  }

  closeStarsGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  closeStarsGeometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1))
  closeStarsGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))

  closeStarsMaterial = new THREE.PointsMaterial({
    size: 0.04,
    sizeAttenuation: true,
    transparent: true,
    opacity: 0.9,
    map: texture,
    vertexColors: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  })

  closeStars = new THREE.Points(closeStarsGeometry, closeStarsMaterial)
  scene.add(closeStars)
}

const animate = () => {
  animationId = requestAnimationFrame(animate)
  time += 0.0005

  target.x += (mouse.x - target.x) * 0.03
  target.y += (mouse.y - target.y) * 0.03

  farStars.rotation.y = time * 0.012 + target.x * 0.02
  farStars.rotation.x = time * 0.006 + target.y * 0.02

  nebula.rotation.y = time * 0.022 + target.x * 0.04
  nebula.rotation.x = time * 0.016 + target.y * 0.04

  galaxy.rotation.y = time * 0.3 + target.x * 0.3
  galaxy.rotation.x = target.y * 0.2

  closeStars.rotation.y = time * 0.05 + target.x * 0.1
  closeStars.rotation.x = time * 0.03 + target.y * 0.1

  const farSizes = farStarsGeometry.attributes.size.array
  for (let i = 0; i < farSizes.length; i++) {
    farSizes[i] += Math.sin(time * 10 + i * 0.5) * 0.002
  }
  farStarsGeometry.attributes.size.needsUpdate = true

  const galaxyPositions = galaxyGeometry.attributes.position.array
  const galaxySizes = galaxyGeometry.attributes.size.array
  for (let i = 0; i < galaxySizes.length; i++) {
    const i3 = i * 3
    const x = galaxyPositions[i3]
    const z = galaxyPositions[i3 + 2]
    const distance = Math.sqrt(x * x + z * z)
    galaxyPositions[i3 + 1] += Math.sin(time * 3 + distance * 2 + i * 0.01) * 0.0003
    galaxySizes[i] += Math.sin(time * 5 + i * 0.1) * 0.0016
  }
  galaxyGeometry.attributes.position.needsUpdate = true
  galaxyGeometry.attributes.size.needsUpdate = true

  const closeSizes = closeStarsGeometry.attributes.size.array
  for (let i = 0; i < closeSizes.length; i++) {
    closeSizes[i] += Math.sin(time * 8 + i * 0.3) * 0.002
  }
  closeStarsGeometry.attributes.size.needsUpdate = true

  renderer.render(scene, camera)
}

onMounted(() => {
  const container = containerRef.value
  if (!container) return

  scene = new THREE.Scene()
  scene.fog = new THREE.FogExp2(0x020617, 0.02)

  camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000)
  camera.position.z = 3

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setSize(window.innerWidth, window.innerHeight)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  container.appendChild(renderer.domElement)

  const particleTexture = createParticleTexture()
  buildFarStars(particleTexture)
  buildNebula(particleTexture)
  buildGalaxy(particleTexture)
  buildCloseStars(particleTexture)

  onMouseMove = (event) => {
    mouse.x = (event.clientX / window.innerWidth) * 2 - 1
    mouse.y = -(event.clientY / window.innerHeight) * 2 + 1
  }

  onResize = () => {
    if (!camera || !renderer) return
    camera.aspect = window.innerWidth / window.innerHeight
    camera.updateProjectionMatrix()
    renderer.setSize(window.innerWidth, window.innerHeight)
  }

  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('resize', onResize)

  animate()
})

onBeforeUnmount(() => {
  cancelAnimationFrame(animationId)
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('resize', onResize)

  if (farStarsGeometry) farStarsGeometry.dispose()
  if (nebulaGeometry) nebulaGeometry.dispose()
  if (galaxyGeometry) galaxyGeometry.dispose()
  if (closeStarsGeometry) closeStarsGeometry.dispose()

  if (farStarsMaterial) farStarsMaterial.dispose()
  if (nebulaMaterial) nebulaMaterial.dispose()
  if (galaxyMaterial) galaxyMaterial.dispose()
  if (closeStarsMaterial) closeStarsMaterial.dispose()

  if (renderer) {
    renderer.dispose()
    if (renderer.domElement && renderer.domElement.parentNode) {
      renderer.domElement.parentNode.removeChild(renderer.domElement)
    }
  }
})
</script>

<template>
  <div ref="containerRef" class="login-galaxy-bg"></div>
</template>

<style scoped>
.login-galaxy-bg {
  position: fixed;
  inset: 0;
  width: 100%;
  height: 100vh;
  pointer-events: none;
  z-index: 0;
  background:
    radial-gradient(ellipse at center, #07131f 0%, #020617 60%, #000000 100%);
}
</style>
