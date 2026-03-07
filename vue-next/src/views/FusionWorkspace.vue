<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'

const route = useRoute()
const router = useRouter()

const activeTab = computed(() => {
  const tab = String(route.query?.tab || 'early').toLowerCase()
  return tab === 'late' ? 'late' : 'early'
})

const openEarlyModule = () => {
  router.push('/fusion/early-module')
}

const openEarlyCropper = () => {
  router.push('/fusion/early-cropper')
}

const openLateModule = () => {
  router.push('/fusion/late-module')
}

const setTab = (tab) => {
  router.replace({ path: '/fusion', query: { tab } })
}

const goTraining = () => {
  router.push('/training')
}
</script>

<template>
  <div class="max-w-6xl mx-auto space-y-6">
    <section class="mb-2 grid grid-cols-[auto_1fr] md:grid-cols-3 items-center gap-3">
      <div class="flex justify-start">
        <BaseBtn variant="secondary" title="Return to training page" class="px-3" @click="goTraining">
          &larr;
        </BaseBtn>
      </div>
      <div class="text-left md:text-center">
        <h1 class="text-2xl md:text-3xl font-bold text-white mb-2">Fusion Workspace</h1>
        <p class="text-slate-400">Dedicated home for Early Fusion data capture and Late Fusion training.</p>
      </div>
      <div class="hidden md:block"></div>
    </section>

    <BaseCard>
      <div class="flex flex-wrap gap-2">
        <BaseBtn :variant="activeTab === 'early' ? 'primary' : 'secondary'" @click="setTab('early')">Early Fusion</BaseBtn>
        <BaseBtn :variant="activeTab === 'late' ? 'primary' : 'secondary'" @click="setTab('late')">Late Fusion</BaseBtn>
      </div>
    </BaseCard>

    <BaseCard v-if="activeTab === 'early'">
      <h2 class="text-xl font-semibold text-white">Early Fusion Module</h2>
      <p class="text-slate-400 mt-2">
        Use this module to capture synchronized CV + sensor data and export fusion datasets. Training is handled elsewhere.
      </p>
      <div class="mt-4 flex flex-wrap gap-3">
        <BaseBtn variant="primary" @click="openEarlyModule">Open Early Fusion Capture</BaseBtn>
        <BaseBtn variant="secondary" @click="openEarlyCropper">Open Cropper</BaseBtn>
      </div>
    </BaseCard>

    <BaseCard v-else>
      <h2 class="text-xl font-semibold text-white">Late Fusion Module</h2>
      <p class="text-slate-400 mt-2">
        Select paired datasets, run training jobs, monitor status, and test prediction.
      </p>
      <div class="mt-4">
        <BaseBtn variant="primary" @click="openLateModule">Open Late Fusion Training</BaseBtn>
      </div>
    </BaseCard>
  </div>
</template>
