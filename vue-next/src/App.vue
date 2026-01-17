<script setup>
import { RouterLink, RouterView, useRoute } from 'vue-router'
const route = useRoute()
</script>

<template>
  <div class="min-h-screen bg-slate-950 text-slate-200 flex">
    <!-- Sidebar (Hidden on login) -->
    <aside v-if="route.meta.layout !== 'empty'" class="w-64 border-r border-slate-800 p-6 flex flex-col">
      <div class="text-2xl font-bold text-indigo-500 mb-8">SilentVoix</div>
      
      <nav class="flex flex-col gap-2">
        <RouterLink to="/" class="p-3 rounded hover:bg-slate-900 hover:text-indigo-400 transition-colors" active-class="bg-slate-900 text-indigo-400">
          Dashboard
        </RouterLink>
        <RouterLink to="/library" class="p-3 rounded hover:bg-slate-900 hover:text-indigo-400 transition-colors" active-class="bg-slate-900 text-indigo-400">
          Library
        </RouterLink>
        <RouterLink to="/voice" class="p-3 rounded hover:bg-slate-900 hover:text-indigo-400 transition-colors" active-class="bg-slate-900 text-indigo-400">
          Voice Studio
        </RouterLink>
        <RouterLink to="/profile" class="p-3 rounded hover:bg-slate-900 hover:text-indigo-400 transition-colors" active-class="bg-slate-900 text-indigo-400">
          Profile
        </RouterLink>
      </nav>
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
</style>
