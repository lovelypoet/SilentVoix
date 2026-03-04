<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import Toast from 'primevue/toast'; // Import Toast component
import { useAuthStore } from './stores/auth' // Import useAuthStore

const route = useRoute()
const authStore = useAuthStore()
const isMobileNavOpen = ref(false)
const canAccessExtendedPages = computed(() => ['editor', 'admin'].includes(authStore.user?.role))
const canAccessAdminPages = computed(() => authStore.user?.role === 'admin')
const isFullscreenLayout = computed(() => {
  if (route.meta.layout === 'empty' || route.meta.layout === 'fullscreen') return true
  return route.name === 'training' && route.query.trainingSession === '1'
})

watch(
  () => route.fullPath,
  () => {
    isMobileNavOpen.value = false
  }
)
</script>

<template>
  <div class="min-h-screen bg-slate-950 text-slate-200 flex app-bg">
    <Toast /> <!-- Add Toast component here -->
    <!-- Sidebar (Hidden on login) -->
    <aside v-if="!isFullscreenLayout" class="hidden lg:flex w-52 p-5 flex-col sticky top-0 h-screen shrink-0">
      <RouterLink to="/" class="text-2xl font-bold text-teal-400 mb-8 cursor-pointer">SilentVoix</RouterLink>
      
      <nav class="flex flex-col gap-2">
        <RouterLink to="/" class="nav-link p-3 rounded font-semibold hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="nav-active text-teal-300">
          Dashboard
        </RouterLink>
        <RouterLink to="/training" class="nav-link p-3 rounded font-semibold hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="nav-active text-teal-300">
          Training
        </RouterLink>
        <RouterLink to="/library" class="nav-link p-3 rounded font-semibold hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="nav-active text-teal-300">
          Gesture Library
        </RouterLink>
        <RouterLink v-if="canAccessExtendedPages" to="/model-library" class="nav-link p-3 rounded font-semibold hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="nav-active text-teal-300">
          Model Library
        </RouterLink>
        <RouterLink v-if="canAccessAdminPages" to="/csv-library" class="nav-link p-3 rounded font-semibold hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="nav-active text-teal-300">
          CSV Library
        </RouterLink>
        <RouterLink to="/voice" class="nav-link p-3 rounded font-semibold hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="nav-active text-teal-300">
          Voice Studio
        </RouterLink>
        <RouterLink to="/profile" class="nav-link p-3 rounded font-semibold hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="nav-active text-teal-300">
          Profile
        </RouterLink>
        <RouterLink to="/about" class="nav-link p-3 rounded font-semibold hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="nav-active text-teal-300">
          About
        </RouterLink>
      </nav>

      <div class="mt-auto"></div>
    </aside>

    <div
      v-if="!isFullscreenLayout && isMobileNavOpen"
      class="fixed inset-0 z-40 bg-black/60 lg:hidden"
      @click="isMobileNavOpen = false"
    ></div>

    <aside
      v-if="!isFullscreenLayout"
      class="fixed inset-y-0 left-0 z-50 w-72 border-r border-slate-800 bg-slate-950 p-6 flex flex-col transform transition-transform duration-200 lg:hidden"
      :class="isMobileNavOpen ? 'translate-x-0' : '-translate-x-full'"
    >
      <div class="flex items-center justify-between mb-8">
        <RouterLink to="/" class="text-2xl font-bold text-teal-400 cursor-pointer">SilentVoix</RouterLink>
        <button class="p-2 rounded border border-slate-700 text-slate-300" @click="isMobileNavOpen = false">
          ✕
        </button>
      </div>

      <nav class="flex flex-col gap-2">
        <RouterLink to="/" class="nav-link p-3 rounded font-semibold hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="nav-active text-teal-300">
          Dashboard
        </RouterLink>
        <RouterLink to="/training" class="nav-link p-3 rounded font-semibold hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="nav-active text-teal-300">
          Training
        </RouterLink>
        <RouterLink to="/library" class="nav-link p-3 rounded font-semibold hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="nav-active text-teal-300">
          Gesture Library
        </RouterLink>
        <RouterLink v-if="canAccessExtendedPages" to="/model-library" class="nav-link p-3 rounded font-semibold hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="nav-active text-teal-300">
          Model Library
        </RouterLink>
        <RouterLink v-if="canAccessAdminPages" to="/csv-library" class="nav-link p-3 rounded font-semibold hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="nav-active text-teal-300">
          CSV Library
        </RouterLink>
        <RouterLink to="/voice" class="nav-link p-3 rounded font-semibold hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="nav-active text-teal-300">
          Voice Studio
        </RouterLink>
        <RouterLink to="/profile" class="nav-link p-3 rounded font-semibold hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="nav-active text-teal-300">
          Profile
        </RouterLink>
        <RouterLink to="/about" class="nav-link p-3 rounded font-semibold hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="nav-active text-teal-300">
          About
        </RouterLink>
      </nav>

      <div class="mt-auto"></div>
    </aside>

    <!-- Main Content -->
    <main
      class="flex-1 overflow-auto"
      :class="{
        'p-4 sm:p-6 lg:py-8 lg:pr-8 lg:pl-0 lg:border-l lg:border-slate-800': !isFullscreenLayout
      }"
    >
      <div
        v-if="!isFullscreenLayout"
        class="mb-4 flex items-center gap-3 lg:hidden"
      >
        <button class="p-2 rounded border border-slate-700 text-slate-200" @click="isMobileNavOpen = true">
          ☰
        </button>
        <div class="text-sm text-slate-400">Menu</div>
      </div>
      <RouterView />
    </main>
  </div>
</template>

<style>
/* Global styles if needed, can likely be empty if using Tailwind */
body {
  @apply bg-slate-950;
}

.nav-link {
  position: relative;
  z-index: 0;
}

.nav-active {
  color: #5eead4;
  animation: nav-bounce 420ms ease;
}

.nav-active::before {
  content: '';
  position: absolute;
  inset: 2px;
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(20, 184, 166, 0.18), rgba(15, 23, 42, 0.25));
  border: 1px solid rgba(45, 212, 191, 0.25);
  z-index: -1;
}

@keyframes nav-bounce {
  0% { transform: translateY(0); }
  35% { transform: translateY(-4px); }
  100% { transform: translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
  .nav-active {
    animation: none;
  }
}
</style>
