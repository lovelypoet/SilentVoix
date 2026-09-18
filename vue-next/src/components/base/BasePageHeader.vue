<script setup>
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
  }
})
</script>

<template>
  <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
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
