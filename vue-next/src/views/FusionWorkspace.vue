<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import BasePageHeader from '../components/base/BasePageHeader.vue'
import { PhVideoCamera, PhScissors, PhFlowArrow, PhArrowRight, PhHandGrabbing, PhWaveSine, PhExport } from '@phosphor-icons/vue'

/*
 * One entry per fusion strategy. Each module lists the pipeline it walks
 * the user through, so the workspace explains itself instead of being a
 * pair of bare buttons.
 */
const modules = {
  early: {
    eyebrow: 'Early Fusion',
    title: 'Capture synchronized CV + sensor data',
    description: 'Record camera landmarks and glove frames on one clock, then crop takes into clean 30-frame windows for the 74-feature fusion model. Training runs elsewhere.',
    steps: [
      { icon: PhHandGrabbing, label: 'Capture', detail: 'Camera + glove, one timeline' },
      { icon: PhScissors, label: 'Crop', detail: 'Trim takes into windows' },
      { icon: PhExport, label: 'Export', detail: '30 × 74 fused dataset' }
    ]
  },
  late: {
    eyebrow: 'Late Fusion',
    title: 'Align CV and glove recordings',
    description: 'Visually synchronize CV landmarks and glove data. Nudge, trim, and export "Golden" fused datasets for external training.',
    steps: [
      { icon: PhWaveSine, label: 'Load', detail: 'CV + sensor CSVs' },
      { icon: PhFlowArrow, label: 'Align', detail: 'Nudge and trim offsets' },
      { icon: PhExport, label: 'Export', detail: 'Golden fused dataset' }
    ]
  }
}

const activeModule = computed(() => modules[activeTab.value])

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

    <div class="flex justify-center">
      <div class="segmented fusion-tabs" role="tablist" aria-label="Fusion strategy">
        <span class="fusion-tabs-indicator" :class="{ 'is-late': activeTab === 'late' }" aria-hidden="true"></span>
        <button
          id="fusion-tab-early"
          type="button"
          role="tab"
          class="focus-ring segmented-option fusion-tab"
          :aria-selected="activeTab === 'early'"
          aria-controls="fusion-panel"
          @click="setTab('early')"
        >
          Early Fusion
        </button>
        <button
          id="fusion-tab-late"
          type="button"
          role="tab"
          class="focus-ring segmented-option fusion-tab"
          :aria-selected="activeTab === 'late'"
          aria-controls="fusion-panel"
          @click="setTab('late')"
        >
          Late Fusion
        </button>
      </div>
    </div>

    <Transition name="fusion-panel" mode="out-in">
      <BaseCard
        id="fusion-panel"
        :key="activeTab"
        role="tabpanel"
        :aria-labelledby="`fusion-tab-${activeTab}`"
        class="fusion-module overflow-hidden !p-0"
        :class="`is-${activeTab}`"
      >
        <div class="grid gap-0 md:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
          <div class="p-6 sm:p-8">
            <div class="eyebrow mb-3" :class="activeTab === 'early' ? 'eyebrow-cyan' : 'eyebrow-violet'">
              <span class="eyebrow-dot"></span>{{ activeModule.eyebrow }}
            </div>
            <h2 class="text-xl font-semibold tracking-tight text-slate-50 sm:text-2xl">{{ activeModule.title }}</h2>
            <p class="mt-3 text-sm leading-relaxed text-slate-400">{{ activeModule.description }}</p>

            <div class="mt-6 flex flex-wrap gap-3">
              <template v-if="activeTab === 'early'">
                <BaseBtn variant="primary" @click="openEarlyModule">
                  <PhVideoCamera size="16" weight="bold" aria-hidden="true" />
                  Open Early Fusion Capture
                </BaseBtn>
                <BaseBtn variant="secondary" @click="openEarlyCropper">
                  <PhScissors size="16" weight="bold" aria-hidden="true" />
                  Open Cropper
                </BaseBtn>
              </template>
              <BaseBtn v-else variant="primary" @click="openLateModule">
                Open Dataset Aligner
                <PhArrowRight size="16" weight="bold" aria-hidden="true" />
              </BaseBtn>
            </div>
          </div>

          <ol class="fusion-steps grid-texture p-6 sm:p-8" aria-label="Workflow">
            <li v-for="(step, index) in activeModule.steps" :key="step.label" class="fusion-step" :style="{ '--i': index }">
              <span class="fusion-step-icon grid place-items-center">
                <component :is="step.icon" size="18" weight="duotone" aria-hidden="true" />
              </span>
              <span class="min-w-0">
                <span class="block text-xs font-semibold uppercase tracking-wider text-slate-500">Step {{ index + 1 }}</span>
                <span class="block text-sm font-semibold text-slate-100">{{ step.label }}</span>
                <span class="block text-xs text-slate-400">{{ step.detail }}</span>
              </span>
            </li>
          </ol>
        </div>
      </BaseCard>
    </Transition>
  </div>
</template>

<style scoped>
.fusion-tabs {
  position: relative;
  isolation: isolate;
}

/* Gradient pill that slides between the two tabs. */
.fusion-tabs-indicator {
  position: absolute;
  z-index: -1;
  top: 0.25rem;
  bottom: 0.25rem;
  left: 0.25rem;
  width: calc(50% - 0.3125rem);
  border-radius: 0.4375rem;
  background: linear-gradient(100deg, rgb(var(--brand-500)), rgb(var(--brand-alt-500)));
  box-shadow: 0 6px 18px -8px rgb(var(--brand-500) / 0.8);
  transition: transform 460ms var(--ease-spring);
}

.fusion-tabs-indicator.is-late {
  transform: translateX(calc(100% + 0.125rem));
}

.fusion-tab {
  min-width: 8.5rem;
  text-align: center;
}

.fusion-tab[aria-selected='true'] {
  color: white;
}

.fusion-module {
  --module-accent: var(--brand-400);
}

.fusion-module.is-late {
  --module-accent: var(--brand-alt-400);
}

.fusion-steps {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 1.25rem;
  border-top: 1px solid rgb(var(--border-subtle));
  background-color: rgb(var(--module-accent) / 0.04);
}

@media (min-width: 768px) {
  .fusion-steps {
    border-top: 0;
    border-left: 1px solid rgb(var(--border-subtle));
  }
}

.fusion-step {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 0.875rem;
  animation: rise-in 520ms var(--ease-out) backwards;
  animation-delay: calc(160ms + var(--i) * 90ms);
}

/* Dotted connector between consecutive steps. */
.fusion-step:not(:last-child)::after {
  content: '';
  position: absolute;
  left: 1.25rem;
  top: 2.875rem;
  bottom: -1.125rem;
  border-left: 1px dashed rgb(var(--module-accent) / 0.5);
}

.fusion-step-icon {
  width: 2.5rem;
  height: 2.5rem;
  flex-shrink: 0;
  border-radius: 0.75rem;
  color: rgb(var(--module-accent));
  background: rgb(var(--module-accent) / 0.12);
  box-shadow: inset 0 0 0 1px rgb(var(--module-accent) / 0.3);
}

.fusion-panel-enter-active {
  transition: opacity 280ms var(--ease-out), transform 360ms var(--ease-out);
}

.fusion-panel-leave-active {
  transition: opacity 150ms var(--ease-in), transform 150ms var(--ease-in);
}

.fusion-panel-enter-from {
  opacity: 0;
  transform: translateY(12px);
}

.fusion-panel-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
