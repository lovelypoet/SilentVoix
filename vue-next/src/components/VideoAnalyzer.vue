<script setup>
import { ref, watchEffect, computed, defineEmits, watch } from 'vue';
import { useHandTracking } from '../composables/useHandTracking.js';

const props = defineProps({
  videoEl: {
    type: Object,
    required: true,
  },
  // New props based on Training.vue's usage of useHandTracking
  mirrorCamera: {
    type: Boolean,
    default: false
  },
  showLandmarks: {
    type: Boolean,
    default: false
  }
});

const canvasRef = ref(null);
const avgBrightness = ref(0);
let processingInterval = null;

// Instantiate the composable for hand tracking with correct arguments
// Assuming useHandTracking expects refs for these boolean values
const { startHandTracking, stopHandTracking, onFrame } = useHandTracking(
  ref(props.mirrorCamera),
  ref(props.showLandmarks)
);

// Local ref to store hand tracking results, updated via onFrame callback
const hands = ref([]);

// Register callback to update local hands ref when new frames are processed
onFrame((results) => {
  if (results.landmarks && results.landmarks.length > 0) {
    hands.value = results.landmarks;
  } else {
    hands.value = [];
  }
});

const processFrame = () => {
  const video = props.videoEl;
  const canvas = canvasRef.value;

  console.log('VideoAnalyzer: processFrame called');

  if (!video) {
    console.log('VideoAnalyzer: processFrame returning early - video is null');
    return;
  }
  if (!canvas) {
    console.log('VideoAnalyzer: processFrame returning early - canvas is null');
    return;
  }
  if (video.paused) {
    console.log('VideoAnalyzer: processFrame returning early - video is paused');
    return;
  }
  if (video.ended) {
    console.log('VideoAnalyzer: processFrame returning early - video is ended');
    return;
  }

  const ctx = canvas.getContext('2d');
  if (!ctx) {
    console.error("VideoAnalyzer: Could not get 2D context for canvas.");
    return;
  }

  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const data = imageData.data;

  let totalLuminance = 0;
  const numPixels = canvas.width * canvas.height;

  for (let i = 0; i < data.length; i += 4) {
    const r = data[i];
    const g = data[i + 1];
    const b = data[i + 2];

    const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
    totalLuminance += luminance;
  }

  avgBrightness.value = totalLuminance / numPixels;
  console.log('VideoAnalyzer: avgBrightness updated to', avgBrightness.value);
};

const lightingStatus = computed(() => {
  const brightness = avgBrightness.value;
  if (brightness < 60) {
    return { status: 'Too Dark', colorClass: 'text-yellow-500' };
  } else if (brightness > 140) {
    return { status: 'Too Bright', colorClass: 'text-red-500' };
  } else {
    return { status: 'Good', colorClass: 'text-green-500' };
  }
});

// Define emits
const emit = defineEmits(['update:avgBrightness', 'update:lightingStatus']);

// Watch avgBrightness and emit an event when it changes
watch(avgBrightness, (newValue) => {
  emit('update:avgBrightness', newValue);
}, { immediate: true }); // Emit initial value

// Watch lightingStatus and emit an event when it changes
watch(lightingStatus, (newValue) => {
  emit('update:lightingStatus', newValue);
}, { immediate: true }); // Emit initial value

watchEffect((onCleanup) => {
  if (props.videoEl && canvasRef.value) {
    // Start hand tracking with correct function name
    startHandTracking(props.videoEl, canvasRef.value, null); // Pass videoEl, the local canvas, and null for mediaStream
    processingInterval = setInterval(processFrame, 150);
  }

  onCleanup(() => {
    // Stop hand tracking with correct function name
    if (stopHandTracking) {
      stopHandTracking();
    }
    if (processingInterval) {
      clearInterval(processingInterval);
      processingInterval = null;
    }
  });
});

// Expose hands only, as avgBrightness and lightingStatus are now emitted
defineExpose({
  hands
});
</script>

<template>
  <div class="video-analyzer-container hidden">
    <!-- Hidden canvas for frame processing. The UI for analysis results is now handled by the parent. -->
    <canvas ref="canvasRef" width="160" height="120"></canvas>
  </div>
</template>

<style scoped>
.video-analyzer-container {
  display: none;
}
</style>