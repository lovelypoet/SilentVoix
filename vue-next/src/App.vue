<script setup>
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import Toast from 'primevue/toast'; // Import Toast component
import BaseBtn from './components/base/BaseBtn.vue' // Import BaseBtn
import { useAuthStore } from './stores/auth' // Import useAuthStore

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const handleLogout = async () => {
  await authStore.logout()
  router.push('/login')
}
</script>

<template>
  <div class="min-h-screen bg-slate-950 text-slate-200 flex app-bg">
    <Toast /> <!-- Add Toast component here -->
    <!-- Sidebar (Hidden on login) -->
    <aside v-if="route.meta.layout !== 'empty'" class="w-64 border-r border-slate-800 p-6 flex flex-col fixed h-screen top-0 left-0">
      <RouterLink to="/" class="text-2xl font-bold text-teal-400 mb-8 cursor-pointer">SilentVoix</RouterLink>
      
      <nav class="flex flex-col gap-2">
        <RouterLink to="/" class="nav-link p-3 rounded font-semibold hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="nav-active text-teal-300">
          Dashboard
        </RouterLink>
        <RouterLink to="/training" class="nav-link p-3 rounded font-semibold hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="nav-active text-teal-300">
          Training
        </RouterLink>
        <RouterLink to="/library" class="nav-link p-3 rounded font-semibold hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="nav-active text-teal-300">
          Library
        </RouterLink>
        <RouterLink to="/voice" class="nav-link p-3 rounded font-semibold hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="nav-active text-teal-300">
          Voice Studio
        </RouterLink>
        <RouterLink to="/profile" class="nav-link p-3 rounded font-semibold hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="nav-active text-teal-300">
          Profile
        </RouterLink>
      </nav>

      <div class="mt-auto"> <!-- This div will push the logout button to the bottom -->
        <BaseBtn variant="danger" class="w-full justify-center" @click="handleLogout">
          Logout
        </BaseBtn>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="flex-1 overflow-auto" :class="{ 'p-8': route.meta.layout !== 'empty' }">
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
