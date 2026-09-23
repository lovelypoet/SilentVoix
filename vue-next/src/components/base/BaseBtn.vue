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
    class="base-btn relative isolate inline-flex items-center justify-center gap-2 overflow-hidden px-4 py-2 rounded-lg text-sm font-medium cursor-pointer focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
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
.base-btn {
  transition:
    transform var(--dur-fast) var(--ease-spring),
    box-shadow var(--dur) var(--ease-out),
    background-color var(--dur-fast) ease,
    background-position 600ms var(--ease-out),
    border-color var(--dur-fast) ease,
    color var(--dur-fast) ease;
}

/* Tactile press: a quick squash that springs back on release. */
.base-btn:active:not(:disabled) {
  transform: scale(0.96);
  transition-duration: 80ms;
}

.btn-primary {
  background: linear-gradient(100deg, rgb(var(--brand-500)), rgb(var(--brand-alt-500)) 50%, rgb(var(--brand-500)));
  background-size: 200% 100%;
  background-position: 0% 0;
  border: 1px solid rgb(var(--brand-400) / 0.6);
  color: white;
  box-shadow: 0 0 20px rgb(var(--brand-400) / 0.18), inset 0 1px 0 rgb(255 255 255 / 0.2);
  --tw-ring-color: rgb(var(--brand-400));
}

/* Light sweep that crosses the button on hover. */
.btn-primary::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -1;
  background: linear-gradient(115deg, transparent 30%, rgb(255 255 255 / 0.35) 50%, transparent 70%);
  transform: translateX(-120%);
  pointer-events: none;
}

.btn-primary:hover:not(:disabled)::after {
  transform: translateX(120%);
  transition: transform 700ms var(--ease-out);
}

.btn-primary:hover:not(:disabled),
.btn-primary:focus-visible {
  transform: translateY(-2px);
  background-position: 100% 0;
  box-shadow: 0 10px 30px -8px rgb(var(--brand-400) / 0.55), inset 0 1px 0 rgb(255 255 255 / 0.25);
}

.btn-secondary {
  background: rgb(var(--surface-raised) / 0.6);
  color: rgb(var(--slate-200));
  border: 1px solid rgb(var(--border-default));
  --tw-ring-color: rgb(var(--brand-400) / 0.6);
}

.btn-secondary:hover:not(:disabled),
.btn-secondary:focus-visible {
  border-color: rgb(var(--brand-400) / 0.5);
  background: rgb(var(--brand-500) / 0.1);
  color: rgb(var(--slate-50));
  transform: translateY(-1px);
  box-shadow: 0 8px 22px -12px rgb(var(--brand-400) / 0.5);
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
