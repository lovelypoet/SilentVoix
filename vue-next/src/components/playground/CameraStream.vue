<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { useHandTracking } from '@/composables/useHandTracking.js'
import { usePlaygroundStore } from '@/stores/playgroundStore'
import { drawHandBoundingBoxes } from '@/renderers/bboxRenderer'

const props = defineProps({
  mirror: { type: Boolean, default: true },
  showLandmarks: { type: Boolean, default: true },
  styleSettings: {
    type: Object,
    default: () => ({
      landmarkColor: '#22d3ee',
      pointColor: '#ffffff',
      lineWidth: 3,
      pointRadius: 4
    })
  }
})

const emit = defineEmits(['results'])

const store = usePlaygroundStore()
const videoEl = ref(null)
const landmarkCanvasEl = ref(null)
const bboxCanvasEl = ref(null)
const mediaStream = ref(null)

const { startHandTracking, stopHandTracking, onFrame } = useHandTracking(
  computed(() => props.mirror),
  computed(() => props.showLandmarks),
  computed(() => props.styleSettings)
)

const videoClasses = computed(() => [
  'absolute inset-0 h-full w-full object-cover',
  { '-scale-x-100': props.mirror }
])

const start = async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false
    })
    mediaStream.value = stream
    await startHandTracking(videoEl.value, landmarkCanvasEl.value, stream)
    
    onFrame((results) => {
      const canvas = bboxCanvasEl.value
      if (canvas && videoEl.value) {
        const ctx = canvas.getContext('2d')
        canvas.width = videoEl.value.videoWidth || 640
        canvas.height = videoEl.value.videoHeight || 480
        ctx.clearRect(0, 0, canvas.width, canvas.height)
        
        if (results?.landmarks?.length) {
          drawHandBoundingBoxes(ctx, results.landmarks, {
            landmarkColor: props.styleSettings.landmarkColor,
            pointColor: props.styleSettings.pointColor,
            mirror: props.mirror,
            width: canvas.width,
            height: canvas.height,
            label: store.prediction?.label,
            confidence: store.prediction?.confidence
          })
        }
      }
      emit('results', results)
    })
    store.isLive = true
  } catch (e) {
    store.liveStatus = e.message || 'Failed to start camera.'
    stop()
  }
}

const stop = () => {
  stopHandTracking()
  if (mediaStream.value) {
    mediaStream.value.getTracks().forEach(t => t.stop())
    mediaStream.value = null
  }
  store.isLive = false
}

defineExpose({ start, stop })

onUnmounted(stop)
</script>

<template>
  <div class="relative aspect-video w-full overflow-hidden rounded-xl border border-slate-700 bg-black">
    <video 
      v-show="store.modelModality !== 'sensor' || store.isFusionMode" 
      ref="videoEl" 
      autoplay 
      playsinline 
      muted 
      :class="videoClasses"
    ></video>
    <canvas 
      v-show="store.modelModality !== 'sensor' || store.isFusionMode" 
      ref="landmarkCanvasEl" 
      class="absolute inset-0 h-full w-full"
    ></canvas>
    <canvas 
      v-show="store.modelModality !== 'sensor' || store.isFusionMode" 
      ref="bboxCanvasEl" 
      class="absolute inset-0 h-full w-full"
    ></canvas>
    
    <slot name="overlay"></slot>
  </div>
</template>
