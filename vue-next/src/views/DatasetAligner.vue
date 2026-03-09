<script setup>
import { computed, onMounted, ref, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import api from '../services/api'
import { useToast } from 'primevue/usetoast'

const router = useRouter()
const toast = useToast()

const mode = ref('single')
const isLoading = ref(false)
const selectionStatus = ref(null)
const error = ref('')

// Waveform Data
const cvData = ref(null)
const sensorData = ref(null)
const isDataLoading = ref(false)

// Alignment State
const offsetMs = ref(0) // The "Nudge"
const trimIn = ref(5) // Default 5% in
const trimOut = ref(95) // Default 95% out
const selectedCvCol = ref('')
const selectedSensorCol = ref('')

// Canvas Refs
const canvasRef = ref(null)
const containerRef = ref(null)
const playheadX = ref(0)
const isExporting = ref(false)

const isCompletePair = computed(() => Boolean(selectionStatus.value?.is_complete_pair))
const selectedCvName = computed(() => selectionStatus.value?.cv?.name || '')
const selectedSensorName = computed(() => selectionStatus.value?.sensor?.name || '')

const loadSelectionStatus = async () => {
  isLoading.value = true
  try {
    const res = await api.admin.csvLibrary.selection.get('late', mode.value)
    selectionStatus.value = res || null
    if (isCompletePair.value) {
       await fetchFullData()
    }
  } catch (e) {
    error.value = e?.response?.data?.detail || 'Failed to load dataset selection.'
  } finally {
    isLoading.value = false
  }
}

const fetchFullData = async () => {
  if (!selectedCvName.value || !selectedSensorName.value) return
  isDataLoading.value = true
  try {
    const [cv, sensor] = await Promise.all([
       api.admin.csvLibrary.getFullData(selectedCvName.value),
       api.admin.csvLibrary.getFullData(selectedSensorName.value)
    ])
    cvData.value = cv.data
    sensorData.value = sensor.data
    
    // Pick default columns to visualize
    selectedCvCol.value = cvData.value.header.find(h => h.toLowerCase().includes('wrist_y') || h.toLowerCase().includes('_y')) || cvData.value.header[1]
    selectedSensorCol.value = sensorData.value.header.find(h => h.toLowerCase().includes('f1')) || sensorData.value.header[1]
    
    drawWaveforms()
  } catch (e) {
    console.error(e)
    toast.add({ severity: 'error', summary: 'Data Load Failed', detail: 'Could not fetch full CSV data for visualization.' })
  } finally {
    isDataLoading.value = false
  }
}

// Waveform Drawing Logic
const drawWaveforms = () => {
  if (!canvasRef.value || !cvData.value || !sensorData.value) return
  
  const canvas = canvasRef.value
  const ctx = canvas.getContext('2d')
  const dpr = window.devicePixelRatio || 1
  const rect = canvas.getBoundingClientRect()
  
  canvas.width = rect.width * dpr
  canvas.height = rect.height * dpr
  ctx.scale(dpr, dpr)
  
  const width = rect.width
  const height = rect.height
  const trackHeight = height / 2

  ctx.clearRect(0, 0, width, height)

  // Draw Backgrounds
  ctx.fillStyle = '#020617'
  ctx.fillRect(0, 0, width, height)
  
  // Draw Trim Areas (Grayed out)
  ctx.fillStyle = 'rgba(255, 255, 255, 0.03)'
  ctx.fillRect(0, 0, (trimIn.value / 100) * width, height)
  ctx.fillRect((trimOut.value / 100) * width, 0, width, height)

  // Track Dividers
  ctx.strokeStyle = '#1e293b'
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.moveTo(0, trackHeight)
  ctx.lineTo(width, trackHeight)
  ctx.stroke()

  // --- Draw CV Waveform (Reference) ---
  const cvRows = cvData.value.rows
  const cvMax = Math.max(...cvRows.map(r => Math.abs(Number(r[selectedCvCol.value])))) || 1
  
  ctx.strokeStyle = '#22d3ee'
  ctx.lineWidth = 1.5
  ctx.beginPath()
  cvRows.forEach((row, i) => {
     const x = (i / cvRows.length) * width
     const val = Number(row[selectedCvCol.value])
     const y = (trackHeight / 2) - (val / cvMax) * (trackHeight / 3)
     if (i === 0) ctx.moveTo(x, y)
     else ctx.lineTo(x, y)
  })
  ctx.stroke()

  // --- Draw Sensor Waveform (Nudgeable) ---
  const sensorRows = sensorData.value.rows
  const sMax = Math.max(...sensorRows.map(r => Math.abs(Number(r[selectedSensorCol.value])))) || 1
  
  // Visual nudge factor: 1ms = X pixels. Assume 10s file = 1000px width.
  const pixelsPerMs = width / (cvRows.length * 33.3) // approx 30fps
  const nudgePx = offsetMs.value * pixelsPerMs
  
  ctx.strokeStyle = '#fbbf24'
  ctx.beginPath()
  sensorRows.forEach((row, i) => {
     const x = ((i / sensorRows.length) * width) + nudgePx
     const val = Number(row[selectedSensorCol.value])
     const y = (trackHeight * 1.5) - (val / sMax) * (trackHeight / 3)
     if (i === 0) ctx.moveTo(x, y)
     else ctx.lineTo(x, y)
  })
  ctx.stroke()

  // Trim Handles
  ctx.strokeStyle = '#4ade80'
  ctx.lineWidth = 2
  ctx.setLineDash([5, 5])
  
  // IN
  ctx.beginPath()
  ctx.moveTo((trimIn.value / 100) * width, 0)
  ctx.lineTo((trimIn.value / 100) * width, height)
  ctx.stroke()
  
  // OUT
  ctx.beginPath()
  ctx.moveTo((trimOut.value / 100) * width, 0)
  ctx.lineTo((trimOut.value / 100) * width, height)
  ctx.stroke()
  
  ctx.setLineDash([])

  // Playhead
  ctx.strokeStyle = '#f43f5e'
  ctx.lineWidth = 2
  ctx.beginPath()
  ctx.moveTo(playheadX.value, 0)
  ctx.lineTo(playheadX.value, height)
  ctx.stroke()
}

const handleMouseMove = (e) => {
  if (!containerRef.value) return
  const rect = containerRef.value.getBoundingClientRect()
  const x = e.clientX - rect.left
  playheadX.value = Math.max(0, Math.min(x, rect.width))
  drawWaveforms()
}

const exportGoldenFusion = async () => {
  if (!isCompletePair.value) return
  isExporting.value = true
  try {
    const payload = {
       cv_name: selectedCvName.value,
       sensor_name: selectedSensorName.value,
       offset_ms: offsetMs.value,
       trim_in_pct: trimIn.value,
       trim_out_pct: trimOut.value,
       mode: mode.value
    }
    const res = await api.admin.csvLibrary.fusionExport(payload)
    toast.add({ severity: 'success', summary: 'Export Successful', detail: res.message, life: 5000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Export Failed', detail: e?.response?.data?.detail || 'Unknown error' })
  } finally {
    isExporting.value = false
  }
}

const goFusionWorkspace = () => {
  router.push({ path: '/fusion', query: { tab: 'late' } })
}

const openCsvLibrary = () => {
  router.push({ path: '/csv-library', query: { pipeline: 'late', mode: mode.value } })
}

watch([offsetMs, trimIn, trimOut, selectedCvCol, selectedSensorCol, mode], () => {
  drawWaveforms()
})

onMounted(() => {
  void loadSelectionStatus()
  window.addEventListener('resize', drawWaveforms)
})

onUnmounted(() => {
  window.removeEventListener('resize', drawWaveforms)
})
</script>

<template>
  <div class="h-screen flex flex-col bg-slate-950 overflow-hidden">
    <!-- Header -->
    <header class="p-4 border-b border-slate-800 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-4">
        <BaseBtn variant="secondary" class="px-3" @click="goFusionWorkspace">&larr;</BaseBtn>
        <div>
          <h1 class="text-xl font-bold text-white leading-tight">Dataset Aligner</h1>
          <p class="text-[11px] text-slate-500 uppercase font-bold tracking-widest">Time-Series Surgeon</p>
        </div>
      </div>

      <div class="flex items-center gap-3">
         <div class="inline-flex rounded-md border border-slate-700 overflow-hidden bg-slate-900 h-9">
            <button class="px-4 text-xs font-bold uppercase transition-colors" :class="mode === 'single' ? 'bg-teal-500 text-slate-950' : 'text-slate-400 hover:text-white'" @click="mode = 'single'">Single</button>
            <button class="px-4 text-xs font-bold uppercase border-l border-slate-700 transition-colors" :class="mode === 'dual' ? 'bg-teal-500 text-slate-950' : 'text-slate-400 hover:text-white'" @click="mode = 'dual'">Dual</button>
         </div>
         <BaseBtn variant="secondary" class="h-9 text-xs" @click="openCsvLibrary">Select Datasets</BaseBtn>
         <BaseBtn variant="primary" class="h-9 text-xs" :disabled="!isCompletePair || isExporting" @click="exportGoldenFusion">
            {{ isExporting ? 'Resampling...' : 'Export Golden Fusion' }}
         </BaseBtn>
      </div>
    </header>

    <div class="flex-1 flex flex-col min-h-0">
       <!-- Waveform Area -->
       <div class="flex-1 bg-black relative cursor-crosshair group" ref="containerRef" @mousemove="handleMouseMove">
          <canvas ref="canvasRef" class="w-full h-full"></canvas>
          
          <div v-if="isDataLoading" class="absolute inset-0 flex flex-col items-center justify-center bg-black/60 backdrop-blur-sm">
             <div class="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-teal-500 mb-2"></div>
             <p class="text-xs text-slate-400 font-bold uppercase tracking-widest">Loading High-Fidelity Data...</p>
          </div>

          <div v-if="!isCompletePair && !isDataLoading" class="absolute inset-0 flex flex-col items-center justify-center">
             <p class="text-slate-500 font-bold uppercase tracking-widest text-sm mb-4">Pair incomplete. Select datasets in CSV Library.</p>
             <BaseBtn variant="primary" @click="openCsvLibrary">Open CSV Library</BaseBtn>
          </div>

          <!-- Metadata Overlays -->
          <div v-if="cvData && sensorData" class="absolute top-4 left-4 pointer-events-none space-y-2">
             <div class="bg-black/60 border border-slate-700 p-2 rounded backdrop-blur-md">
                <p class="text-[9px] text-slate-500 uppercase font-bold">Reference: {{ cvData.name }}</p>
                <p class="text-xs text-teal-400 font-bold">{{ cvData.total_rows }} frames @ master clock</p>
             </div>
             <div class="bg-black/60 border border-slate-700 p-2 rounded backdrop-blur-md">
                <p class="text-[9px] text-slate-500 uppercase font-bold">Target: {{ sensorData.name }}</p>
                <p class="text-xs text-amber-400 font-bold">{{ sensorData.total_rows }} rows (Interpolated on export)</p>
             </div>
          </div>
       </div>

       <!-- Controls Footer -->
       <footer class="bg-slate-900 border-t border-slate-800 p-4 shrink-0">
          <div class="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-8">
             <!-- Nudge Control -->
             <div class="space-y-3">
                <div class="flex justify-between items-center">
                   <label class="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Latency Nudge (ms)</label>
                   <span class="text-xs font-mono text-amber-400 bg-amber-400/10 px-2 py-0.5 rounded border border-amber-400/20">
                      {{ offsetMs > 0 ? '+' : '' }}{{ offsetMs }}ms
                   </span>
                </div>
                <input type="range" v-model.number="offsetMs" min="-500" max="500" step="10" class="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-amber-500" />
                <div class="flex justify-between text-[9px] text-slate-600 font-bold">
                   <span>-500ms</span>
                   <button @click="offsetMs = 0" class="hover:text-teal-400 transition-colors uppercase">Reset Latency</button>
                   <span>+500ms</span>
                </div>
             </div>

             <!-- Trim Control -->
             <div class="space-y-3">
                <div class="flex justify-between items-center">
                   <label class="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Trimming Window (%)</label>
                   <div class="flex gap-2">
                      <span class="text-[10px] font-mono text-emerald-400">IN: {{ trimIn }}%</span>
                      <span class="text-[10px] font-mono text-emerald-400">OUT: {{ trimOut }}%</span>
                   </div>
                </div>
                <div class="relative h-2 bg-slate-800 rounded-lg mt-4">
                   <input type="range" v-model.number="trimIn" min="0" max="40" step="1" class="absolute inset-0 w-full h-2 bg-transparent appearance-none pointer-events-none z-20 slider-handle-in" />
                   <input type="range" v-model.number="trimOut" min="60" max="100" step="1" class="absolute inset-0 w-full h-2 bg-transparent appearance-none pointer-events-none z-20 slider-handle-out" />
                   <div class="absolute inset-y-0 bg-teal-500/20 border-x border-teal-500/40" :style="{ left: trimIn + '%', right: (100 - trimOut) + '%' }"></div>
                </div>
                <div class="flex justify-between text-[9px] text-slate-600 font-bold">
                   <span>CROP START</span>
                   <span class="text-teal-400">ACTIVE DATA</span>
                   <span>CROP END</span>
                </div>
             </div>

             <!-- Visualization Channels -->
             <div class="grid grid-cols-2 gap-4">
                <div class="space-y-1">
                   <label class="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Reference Axis (CV)</label>
                   <select v-model="selectedCvCol" class="w-full bg-slate-950 border border-slate-800 text-xs text-slate-300 rounded px-2 py-1.5 focus:border-teal-500 outline-none">
                      <option v-for="h in cvData?.header" :key="h" :value="h">{{ h }}</option>
                   </select>
                </div>
                <div class="space-y-1">
                   <label class="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Alignment Channel (Glove)</label>
                   <select v-model="selectedSensorCol" class="w-full bg-slate-950 border border-slate-800 text-xs text-slate-300 rounded px-2 py-1.5 focus:border-amber-500 outline-none">
                      <option v-for="h in sensorData?.header" :key="h" :value="h">{{ h }}</option>
                   </select>
                </div>
             </div>
          </div>
       </footer>
    </div>
  </div>
</template>

<style scoped>
canvas {
  image-rendering: pixelated;
}

input[type=range]::-webkit-slider-thumb {
  -webkit-appearance: none;
  height: 16px;
  width: 16px;
  border-radius: 50%;
  background: #f59e0b;
  box-shadow: 0 0 10px rgba(245, 158, 11, 0.4);
  cursor: pointer;
  pointer-events: auto;
}

.slider-handle-in::-webkit-slider-thumb {
  background: #4ade80 !important;
}

.slider-handle-out::-webkit-slider-thumb {
  background: #4ade80 !important;
}

input[type=range] {
  outline: none;
}
</style>
