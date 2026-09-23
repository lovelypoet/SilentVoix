<script setup>
import { RouterLink } from 'vue-router'
import { PhArrowLeft } from '@phosphor-icons/vue'
</script>

<!--
  Way back to the marketing page from the auth screens (Login / Register),
  which render in the chrome-less `empty` layout and otherwise have no
  navigation at all. Pinned top-left, mirroring the graphics-settings gear
  pinned top-right on Login.
-->
<template>
  <RouterLink to="/" class="focus-ring auth-back" aria-label="Back to home page">
    <span class="auth-back-arrow grid place-items-center" aria-hidden="true">
      <PhArrowLeft size="16" weight="bold" />
    </span>
    <span class="auth-back-label">Back to home</span>
  </RouterLink>
</template>

<style scoped>
.auth-back {
  position: fixed;
  top: 1rem;
  left: 1rem;
  z-index: 3;
  display: inline-flex;
  align-items: center;
  gap: 0.625rem;
  min-height: 2.75rem;
  padding: 0.3rem 1rem 0.3rem 0.3rem;
  border-radius: 9999px;
  border: 1px solid rgb(var(--border-default));
  background: rgb(var(--surface) / 0.7);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  color: rgb(var(--slate-300));
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition:
    border-color var(--dur) var(--ease-out),
    color var(--dur-fast) ease,
    box-shadow var(--dur) var(--ease-out),
    transform var(--dur-fast) var(--ease-spring);
  animation: auth-back-in 600ms var(--ease-out) 200ms backwards;
}

.auth-back:hover {
  border-color: rgb(var(--brand-400) / 0.5);
  color: rgb(var(--slate-50));
  box-shadow: 0 8px 26px -10px rgb(var(--brand-400) / 0.55);
}

.auth-back:active {
  transform: scale(0.96);
}

.auth-back-arrow {
  width: 2.125rem;
  height: 2.125rem;
  border-radius: 9999px;
  color: white;
  background: linear-gradient(135deg, rgb(var(--brand-500)), rgb(var(--brand-alt-500)));
  box-shadow: 0 0 14px rgb(var(--brand-400) / 0.35);
  transition: transform var(--dur) var(--ease-spring);
}

.auth-back:hover .auth-back-arrow {
  transform: translateX(-3px);
}

@keyframes auth-back-in {
  from {
    opacity: 0;
    transform: translateX(-12px);
  }
}

/* Icon-only on very narrow screens so it never collides with the card. */
@media (max-width: 380px) {
  .auth-back {
    padding-right: 0.3rem;
  }

  .auth-back-label {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
  }
}
</style>
