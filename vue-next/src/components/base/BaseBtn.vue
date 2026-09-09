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
    class="px-5 py-2.5 rounded-lg font-medium transition-all duration-200 focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
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
 * Nothing here hardcodes a hue.
 */
.btn-primary {
  background: rgb(var(--brand-600));
  color: white;
  box-shadow:
    0 10px 15px -3px rgb(var(--brand-500) / 0.25),
    0 4px 6px -4px rgb(var(--brand-500) / 0.25);
  transition: all 300ms ease;
  --tw-ring-color: rgb(var(--brand-500));
}

.btn-primary:hover,
.btn-primary:focus-visible {
  background: rgb(var(--brand-500));
  box-shadow:
    0 10px 15px -3px rgb(var(--brand-400) / 0.35),
    0 4px 6px -4px rgb(var(--brand-400) / 0.35);
}

.btn-warning {
  background: rgb(var(--warning-500));
  color: rgb(var(--warning-950));
  box-shadow:
    0 10px 15px -3px rgb(var(--warning-400) / 0.25),
    0 4px 6px -4px rgb(var(--warning-400) / 0.25);
  transition: all 300ms ease;
  --tw-ring-color: rgb(var(--warning-500));
}

.btn-warning:hover,
.btn-warning:focus-visible {
  background: rgb(var(--warning-400));
  box-shadow:
    0 10px 15px -3px rgb(var(--warning-300) / 0.35),
    0 4px 6px -4px rgb(var(--warning-300) / 0.35);
}

.btn-secondary {
  background: linear-gradient(180deg, rgb(var(--brand-700) / 0.18), rgba(15, 23, 42, 0.2));
  color: rgb(var(--brand-100));
  border: 1px solid rgb(var(--brand-400) / 0.25);
  box-shadow:
    0 10px 15px -3px rgb(var(--brand-400) / 0.12),
    0 4px 6px -4px rgb(var(--brand-400) / 0.12);
  transition: all 300ms ease;
  --tw-ring-color: rgb(var(--brand-400) / 0.6);
}

.btn-secondary:hover,
.btn-secondary:focus-visible {
  background: linear-gradient(180deg, rgb(var(--brand-500) / 0.22), rgba(15, 23, 42, 0.2));
  color: white;
  box-shadow:
    0 10px 15px -3px rgb(var(--brand-400) / 0.22),
    0 4px 6px -4px rgb(var(--brand-400) / 0.22);
}

.btn-danger {
  background: rgb(var(--danger-400) / 0.12);
  color: rgb(var(--danger-300));
  border: 1px solid rgb(var(--danger-400) / 0.25);
  transition: all 300ms ease;
  --tw-ring-color: rgb(var(--danger-400) / 0.55);
}

.btn-danger:hover,
.btn-danger:focus-visible {
  background: rgb(var(--danger-400) / 0.2);
  color: rgb(var(--danger-200));
  box-shadow:
    0 10px 15px -3px rgb(var(--danger-400) / 0.2),
    0 4px 6px -4px rgb(var(--danger-400) / 0.2);
}
</style>
