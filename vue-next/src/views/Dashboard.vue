<script setup>
import { useRouter } from 'vue-router'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'

const router = useRouter()

const startNewSession = () => {
  router.push('/training')
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex justify-between items-center">
      <h1 class="text-3xl font-bold text-white">Dashboard</h1>
      <BaseBtn variant="primary" @click="startNewSession">New Session</BaseBtn>
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
