<script setup>
defineProps({
  icon: {
    type: [Object, Function],
    required: true
  },
  title: {
    type: String,
    required: true
  },
  description: {
    type: String,
    default: ''
  }
})
</script>

<template>
  <div class="flex flex-col items-center gap-3 py-12 text-center">
    <span class="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-[rgb(var(--surface-raised))] text-slate-600">
      <component :is="icon" size="22" weight="duotone" aria-hidden="true" />
    </span>
    <div>
      <p class="text-sm font-medium text-slate-300">{{ title }}</p>
      <p v-if="description" class="mt-1 max-w-sm text-xs text-slate-500">{{ description }}</p>
    </div>
    <div v-if="$slots.default" class="mt-1 flex flex-wrap items-center justify-center gap-2">
      <slot />
    </div>
  </div>
</template>
