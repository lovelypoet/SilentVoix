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
  <div class="min-h-screen bg-slate-950 text-slate-200 flex">
    <Toast /> <!-- Add Toast component here -->
    <!-- Sidebar (Hidden on login) -->
    <aside v-if="route.meta.layout !== 'empty'" class="w-64 border-r border-slate-800 p-6 flex flex-col fixed h-screen top-0 left-0">
      <RouterLink to="/" class="text-2xl font-bold text-teal-400 mb-8 cursor-pointer">SilentVoix</RouterLink>
      
      <nav class="flex flex-col gap-2">
        <RouterLink to="/" class="p-3 rounded hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="bg-slate-900 text-teal-300">
          Dashboard
        </RouterLink>
        <RouterLink to="/training" class="p-3 rounded hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="bg-slate-900 text-teal-300">
          Training
        </RouterLink>
        <RouterLink to="/library" class="p-3 rounded hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="bg-slate-900 text-teal-300">
          Library
        </RouterLink>
        <RouterLink to="/voice" class="p-3 rounded hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="bg-slate-900 text-teal-300">
          Voice Studio
        </RouterLink>
        <RouterLink to="/profile" class="p-3 rounded hover:bg-slate-900 hover:text-teal-300 transition-colors" active-class="bg-slate-900 text-teal-300">
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
    <main class="flex-1 overflow-auto" :class="{ 'ml-64 p-8': route.meta.layout !== 'empty' }">
      <RouterView />
    </main>
  </div>
</template>

<style>
/* Global styles if needed, can likely be empty if using Tailwind */
body {
  @apply bg-slate-950;
}
</style>
