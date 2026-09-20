<script setup>
import { PhArrowLeft } from '@phosphor-icons/vue'
import BaseBtn from './BaseBtn.vue'

defineProps({
  title: {
    type: String,
    required: true
  },
  description: {
    type: String,
    default: ''
  },
  // Small uppercase label shown above the title, e.g. "OVERVIEW". Optional -
  // most pages don't need it; use sparingly for the pages where a bit of
  // the landing page's brand flavor earns its place.
  eyebrow: {
    type: String,
    default: ''
  },
  eyebrowTone: {
    type: String,
    default: 'cyan' // cyan, violet, pink
  },
  // Centers the title/description with no left-aligned actions row - the
  // "idle" state of a workflow page before it has anything to act on.
  centered: {
    type: Boolean,
    default: false
  },
  // Accessible label for a back button. When set, renders the tool-page
  // layout used by full-screen workflows (Training, Fusion Workspace,
  // Realtime Playground, capture/crop tools, ...): a back button on the
  // left, the title centered, and a matching spacer on the right so the
  // title stays visually centered on wide screens. Emits `back` on click.
  backLabel: {
    type: String,
    default: ''
  }
})

defineEmits(['back'])
</script>

<template>
  <div v-if="backLabel" class="grid grid-cols-[auto_1fr] items-center gap-3 md:grid-cols-3">
    <div class="flex justify-start">
      <BaseBtn
        variant="secondary"
        class="h-11 w-11 shrink-0 p-0"
        :title="backLabel"
        :aria-label="backLabel"
        @click="$emit('back')"
      >
        <PhArrowLeft size="18" weight="bold" aria-hidden="true" />
      </BaseBtn>
    </div>
    <div class="text-left md:text-center">
      <div v-if="eyebrow" class="eyebrow mb-2" :class="`eyebrow-${eyebrowTone}`">
        <span class="eyebrow-dot"></span>{{ eyebrow }}
      </div>
      <h1 class="text-xl font-medium tracking-tight text-slate-100 sm:text-2xl">{{ title }}</h1>
      <p v-if="description" class="mt-1 text-sm text-slate-400">{{ description }}</p>
    </div>
    <div class="hidden md:block" aria-hidden="true"></div>
  </div>

  <div v-else-if="centered" class="text-center">
    <div v-if="eyebrow" class="eyebrow mb-2 justify-center" :class="`eyebrow-${eyebrowTone}`">
      <span class="eyebrow-dot"></span>{{ eyebrow }}
    </div>
    <h1 class="text-xl font-medium tracking-tight text-slate-100 sm:text-2xl">{{ title }}</h1>
    <p v-if="description" class="mt-1 text-sm text-slate-400">{{ description }}</p>
  </div>

  <div v-else class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
    <div class="min-w-0">
      <div v-if="eyebrow" class="eyebrow mb-2" :class="`eyebrow-${eyebrowTone}`">
        <span class="eyebrow-dot"></span>{{ eyebrow }}
      </div>
      <h1 class="text-xl font-medium tracking-tight text-slate-100 sm:text-2xl">{{ title }}</h1>
      <p v-if="description" class="mt-1 text-sm text-slate-400">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="flex shrink-0 items-center gap-2">
      <slot name="actions" />
    </div>
  </div>
</template>
