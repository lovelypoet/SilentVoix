<script setup>
import { useRouter } from 'vue-router'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '../stores/auth.js' // Import useAuthStore

const router = useRouter()
const authStore = useAuthStore() // Initialize auth store

const isHovering = ref(false) // Reintroduce isHovering

const displayName = computed(() => {
  return authStore.user?.display_name || 'user'
})

const startNewSession = () => {
  router.push('/training')
}

let animationFrameId = null;
const hue = ref(246); // Starting hue for indigo-600

const animateColors = () => {
  if (!isHovering.value) { // Stop animation if not hovering
    if (animationFrameId) {
      cancelAnimationFrame(animationFrameId);
      animationFrameId = null;
    }
    return;
  }
  hue.value = (hue.value + 0.5) % 360; // Shift hue by 0.5 degrees per frame
  document.documentElement.style.setProperty('--hue-start', hue.value);
  document.documentElement.style.setProperty('--hue-end', (hue.value + 30) % 360); // Slightly different hue for the end of the gradient

  animationFrameId = requestAnimationFrame(animateColors);
};

const startAnimation = () => {
  isHovering.value = true;
  if (!animationFrameId) { // Only start if not already running
    animateColors();
  }
};

const stopAnimation = () => {
  isHovering.value = false;
  // The animateColors function will handle stopping the animation
};

onUnmounted(() => {
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId);
  }
});
</script>

<template>
  <div class="space-y-6">
    <div class="flex justify-between items-center">
      <h1 class="text-3xl font-bold text-white">Dashboard</h1>
      <BaseBtn variant="primary" @click="startNewSession">New Session</BaseBtn>
    </div>

    <!-- Welcome Banner -->
    <div
      class="welcome-banner p-8 rounded-lg text-center"
      @mouseover="startAnimation"
      @mouseleave="stopAnimation"
    >
      <h2 class="text-4xl font-bold mb-2 welcome-text">Welcome, {{ displayName }}!</h2>
      <p class="text-lg welcome-text">Start your sign language journey today.</p>
    </div>

    <!-- Stats Grid -->                                                       
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <BaseCard>
        <div class="text-slate-400 text-sm mb-1">Total Training Time</div>
        <div class="text-3xl font-bold text-white">--</div>
        <div class="text-emerald-500 text-sm mt-2 flex items-center gap-1">
          <span>0h</span>
          <span class="text-slate-500">this week</span>
        </div>
      </BaseCard>

      <BaseCard>
        <div class="text-slate-400 text-sm mb-1">Gestures Learned</div>
        <div class="text-3xl font-bold text-white">0</div>
        <div class="text-indigo-500 text-sm mt-2 flex items-center gap-1">
          <span>Level 0</span>
          <span class="text-slate-500">Novice</span>
        </div>
      </BaseCard>

      <BaseCard>
        <div class="text-slate-400 text-sm mb-1">Accuracy Streak</div>
        <div class="text-3xl font-bold text-white">--%</div>
        <div class="text-slate-500 text-sm mt-2">No sessions yet</div>
      </BaseCard>
    </div>

    <!-- Recent Activity -->
    <h2 class="text-xl font-bold text-white mt-8 mb-4">Recent Activity</h2>
    <div class="grid grid-cols-1 gap-4">
       <!-- Empty state -->
      <BaseCard class="p-8 text-center text-slate-500">
         No recent activity to show.
      </BaseCard>

  </div>
  </div>
</template>

<style scoped>
.welcome-text {
  background-image: linear-gradient(
    to right,
    hsl(var(--hue-start, 246), 69%, 51%), /* Default to indigo-600 hue */
    hsl(var(--hue-end, 276), 90%, 74%)    /* Default to indigo-400 hue + 30 */
  );
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  text-fill-color: transparent;
}
</style>
