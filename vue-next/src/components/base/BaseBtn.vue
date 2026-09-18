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
    class="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
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
 * Primary matches the landing page's gradient CTA (button-primary/nav-cta)
 * so the "Sign in" -> app transition feels continuous.
 */
.btn-primary {
  background: linear-gradient(100deg, rgb(var(--brand-500)), rgb(var(--brand-alt-500)));
  border: 1px solid rgb(var(--brand-400) / 0.6);
  color: white;
  box-shadow: 0 0 20px rgb(var(--brand-400) / 0.18);
  --tw-ring-color: rgb(var(--brand-400));
}

.btn-primary:hover,
.btn-primary:focus-visible {
  transform: translateY(-1px);
  box-shadow: 0 0 26px rgb(var(--brand-400) / 0.32);
}

.btn-secondary {
  background: rgb(var(--surface-raised) / 0.6);
  color: rgb(226 232 240);
  border: 1px solid rgb(var(--border-default));
  --tw-ring-color: rgb(var(--brand-400) / 0.6);
}

.btn-secondary:hover,
.btn-secondary:focus-visible {
  border-color: rgb(var(--brand-400) / 0.5);
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
