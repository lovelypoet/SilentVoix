<script setup>
defineProps({
  variant: {
    type: String,
    // `amber` is kept as a deprecated alias for `warning`.
    default: 'primary' // primary, secondary, danger, warning
  },
  label: {
    type: String,
    default: ''
  }
})
</script>

<template>
  <button
    v-bind="$attrs"
    class="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
    :class="{
      'btn-primary': variant === 'primary',
      'btn-secondary': variant === 'secondary',
      'btn-danger': variant === 'danger',
      'btn-warning': variant === 'warning' || variant === 'amber'
    }"
  >
    <slot>{{ label }}</slot>
  </button>
</template>

<style scoped>
/*
 * All button colors resolve to the design tokens in src/style.css.
 * Nothing here hardcodes a hue. Flat surfaces, border does the separating -
 * no gradients or colored glow shadows.
 */
.btn-primary {
  background: rgb(var(--brand-600));
  color: white;
  --tw-ring-color: rgb(var(--brand-500));
}

.btn-primary:hover,
.btn-primary:focus-visible {
  background: rgb(var(--brand-500));
}

.btn-secondary {
  background: rgb(var(--surface-raised));
  color: rgb(226 232 240);
  border: 1px solid rgb(var(--border-default));
  --tw-ring-color: rgb(var(--brand-400) / 0.6);
}

.btn-secondary:hover,
.btn-secondary:focus-visible {
  background: rgb(51 65 85);
  color: white;
}

.btn-danger {
  background: rgb(var(--danger-500) / 0.1);
  color: rgb(var(--danger-300));
  border: 1px solid rgb(var(--danger-500) / 0.28);
  --tw-ring-color: rgb(var(--danger-400) / 0.55);
}

.btn-danger:hover,
.btn-danger:focus-visible {
  background: rgb(var(--danger-500) / 0.18);
  color: rgb(var(--danger-200));
}

.btn-warning {
  background: rgb(var(--warning-500));
  color: rgb(var(--warning-950));
  --tw-ring-color: rgb(var(--warning-500));
}

.btn-warning:hover,
.btn-warning:focus-visible {
  background: rgb(var(--warning-400));
}
</style>
