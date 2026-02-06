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
  <div class="space-y-8">
    <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
      <div>
        <h1 class="text-3xl font-bold text-white">Dashboard</h1>
        <p class="text-slate-400 text-sm">A cozy start to your daily practice.</p>
      </div>
      <div class="flex items-center gap-3">
        <BaseBtn variant="secondary" @click="startNewSession">Warm Up (3 min)</BaseBtn>
        <BaseBtn variant="primary" @click="startNewSession">Start Session</BaseBtn>
      </div>
    </div>

    <!-- Friendly Hero -->
    <div
      class="welcome-banner p-8 rounded-2xl text-left overflow-hidden relative"
      @mouseover="startAnimation"
      @mouseleave="stopAnimation"
    >
      <div class="hero-bubble hero-bubble-1"></div>
      <div class="hero-bubble hero-bubble-2"></div>
      <div class="relative z-10">
        <h2 class="text-3xl md:text-4xl font-bold mb-2 welcome-text">
          Welcome back, {{ displayName }}!
        </h2>
        <p class="text-base md:text-lg welcome-text">
          Ready for a quick win? Try a short warm‑up and keep your streak alive.
        </p>
        <div class="mt-5 flex flex-wrap gap-3">
          <BaseBtn variant="primary" @click="startNewSession">Begin Practice</BaseBtn>
          <button class="text-slate-300 hover:text-white transition-colors text-sm">View last session →</button>
        </div>
      </div>
    </div>

    <!-- Focus Row -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <BaseCard class="soft-card">
        <div class="text-slate-300 text-sm mb-2">Today’s Goal</div>
        <div class="text-2xl font-bold text-white mb-2">3 gestures, 5 minutes</div>
        <div class="progress-track">
          <div class="progress-fill" style="width: 0%;"></div>
        </div>
        <div class="text-xs text-slate-400 mt-2">Let’s get your first session in.</div>
      </BaseCard>

      <BaseCard class="soft-card">
        <div class="text-slate-300 text-sm mb-2">Confidence Builder</div>
        <div class="text-2xl font-bold text-white mb-2">Quick Warm‑Up</div>
        <div class="text-slate-400 text-sm">A 3‑minute refresh to loosen your hands.</div>
        <div class="mt-4">
          <BaseBtn variant="secondary" @click="startNewSession">Start Warm‑Up</BaseBtn>
        </div>
      </BaseCard>

      <BaseCard class="soft-card">
        <div class="text-slate-300 text-sm mb-2">Streak Status</div>
        <div class="text-2xl font-bold text-white mb-2">No streak yet</div>
        <div class="text-slate-400 text-sm">Complete 1 session to begin tracking.</div>
      </BaseCard>
    </div>

    <!-- Stats Grid -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <BaseCard class="soft-card">
        <div class="text-slate-400 text-sm mb-1">Total Training Time</div>
        <div class="text-3xl font-bold text-white">--</div>
        <div class="text-emerald-400 text-sm mt-2 flex items-center gap-1">
          <span>0h</span>
          <span class="text-slate-500">this week</span>
        </div>
      </BaseCard>

      <BaseCard class="soft-card">
        <div class="text-slate-400 text-sm mb-1">Gestures Learned</div>
        <div class="text-3xl font-bold text-white">0</div>
        <div class="text-indigo-400 text-sm mt-2 flex items-center gap-1">
          <span>Level 0</span>
          <span class="text-slate-500">Novice</span>
        </div>
      </BaseCard>

      <BaseCard class="soft-card">
        <div class="text-slate-400 text-sm mb-1">Accuracy Streak</div>
        <div class="text-3xl font-bold text-white">--%</div>
        <div class="text-slate-500 text-sm mt-2">No sessions yet</div>
      </BaseCard>
    </div>

    <!-- Recent Activity -->
    <div class="flex items-center justify-between mt-6">
      <h2 class="text-xl font-bold text-white">Recent Activity</h2>
      <button class="text-sm text-slate-400 hover:text-white transition-colors">View all</button>
    </div>
    <div class="grid grid-cols-1 gap-4">
      <BaseCard class="p-8 text-center text-slate-400 soft-card">
        No recent activity yet. Your first session will appear here.
      </BaseCard>
    </div>
  </div>
</template>

<style scoped>
.welcome-banner {
  background: radial-gradient(1200px 400px at -10% -20%, rgba(99, 102, 241, 0.22), transparent 60%),
              radial-gradient(900px 350px at 110% 0%, rgba(236, 72, 153, 0.18), transparent 55%),
              linear-gradient(135deg, rgba(15, 23, 42, 0.9), rgba(30, 41, 59, 0.9));
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.welcome-text {
  background-image: linear-gradient(
    to right,
    hsl(var(--hue-start, 246), 69%, 51%), /* Default to indigo-600 hue */
    hsl(var(--hue-end, 276), 90%, 74%)    /* Default to indigo-400 hue + 30 */
  );
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  -text-fill-color: transparent;
}

.hero-bubble {
  position: absolute;
  border-radius: 9999px;
  filter: blur(10px);
  opacity: 0.45;
}

.hero-bubble-1 {
  width: 220px;
  height: 220px;
  background: rgba(59, 130, 246, 0.25);
  top: -60px;
  right: 40px;
}

.hero-bubble-2 {
  width: 180px;
  height: 180px;
  background: rgba(236, 72, 153, 0.22);
  bottom: -40px;
  left: 20px;
}

.soft-card {
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.7), rgba(15, 23, 42, 0.4));
}

.progress-track {
  height: 8px;
  border-radius: 9999px;
  background: rgba(148, 163, 184, 0.2);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 9999px;
  background: linear-gradient(90deg, rgba(99, 102, 241, 0.9), rgba(236, 72, 153, 0.9));
}

@media (prefers-reduced-motion: reduce) {
  .welcome-banner {
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.9), rgba(30, 41, 59, 0.9));
  }
}
</style>
