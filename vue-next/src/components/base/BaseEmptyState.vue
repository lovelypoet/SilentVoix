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
    <span class="empty-icon relative grid h-14 w-14 shrink-0 place-items-center rounded-2xl text-brand-400">
      <component :is="icon" size="24" weight="duotone" aria-hidden="true" />
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

<style scoped>
.empty-icon {
  background: linear-gradient(145deg, rgb(var(--brand-500) / 0.16), rgb(var(--brand-alt-500) / 0.1));
  box-shadow: inset 0 0 0 1px rgb(var(--brand-400) / 0.22);
  animation: empty-float 4.5s ease-in-out infinite;
}

/* Soft halo pulsing behind the icon. */
.empty-icon::before {
  content: '';
  position: absolute;
  inset: -6px;
  z-index: -1;
  border-radius: 1.25rem;
  background: radial-gradient(circle, rgb(var(--brand-400) / 0.25), transparent 70%);
  animation: empty-halo 4.5s ease-in-out infinite;
}

@keyframes empty-float {
  50% { transform: translateY(-5px); }
}

@keyframes empty-halo {
  50% { opacity: 0.4; transform: scale(1.15); }
}
</style>
