<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import BasePageHeader from '../components/base/BasePageHeader.vue'

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
  router.push('/dataset-aligner')
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
    <BasePageHeader
      title="Fusion Workspace"
      description="Dedicated home for Early Fusion data capture and Late Fusion training."
      back-label="Return to training page"
      @back="goTraining"
    />

    <BaseCard>
      <div class="flex flex-wrap gap-2">
        <BaseBtn :variant="activeTab === 'early' ? 'primary' : 'secondary'" @click="setTab('early')">Early Fusion</BaseBtn>
        <BaseBtn :variant="activeTab === 'late' ? 'primary' : 'secondary'" @click="setTab('late')">Late Fusion</BaseBtn>
      </div>
    </BaseCard>

    <BaseCard v-if="activeTab === 'early'">
      <h2 class="text-lg font-semibold text-slate-100">Early Fusion Module</h2>
      <p class="text-slate-400 mt-2">
        Use this module to capture synchronized CV + sensor data and export fusion datasets. Training is handled elsewhere.
      </p>
      <div class="mt-4 flex flex-wrap gap-3">
        <BaseBtn variant="primary" @click="openEarlyModule">Open Early Fusion Capture</BaseBtn>
        <BaseBtn variant="secondary" @click="openEarlyCropper">Open Cropper</BaseBtn>
      </div>
    </BaseCard>

    <BaseCard v-else>
      <h2 class="text-lg font-semibold text-slate-100">Dataset Aligner (Late Fusion Prep)</h2>
      <p class="text-slate-400 mt-2">
        Visually synchronize CV landmarks and Glove data. Nudge, trim, and export "Golden" fused datasets for external training.
      </p>
      <div class="mt-4">
        <BaseBtn variant="primary" @click="openLateModule">Open Dataset Aligner</BaseBtn>
      </div>
    </BaseCard>
  </div>
</template>
