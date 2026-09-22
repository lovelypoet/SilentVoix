<script setup>
import { PhCompass } from '@phosphor-icons/vue'
import { useRoute } from 'vue-router'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'

const route = useRoute()
</script>

<template>
  <div class="not-found-shell">
    <BaseCard class="not-found-card text-center">
      <div class="not-found-icon">
        <PhCompass size="28" weight="duotone" aria-hidden="true" />
      </div>
      <h1 class="text-xl font-semibold text-slate-100 mt-4">Page not found</h1>
      <p class="text-sm text-slate-400 mt-2">
        There's nothing at <code class="not-found-path">{{ route.fullPath }}</code>.
        It may have moved, or the link is out of date.
      </p>
      <div class="flex items-center justify-center gap-3 mt-6">
        <BaseBtn variant="primary" @click="$router.push('/dashboard')">
          Back to Dashboard
        </BaseBtn>
        <BaseBtn variant="secondary" @click="$router.back()">
          Go back
        </BaseBtn>
      </div>
    </BaseCard>
  </div>
</template>

<style scoped>
.not-found-shell {
  min-height: calc(100vh - 4rem);
  display: flex;
  align-items: center;
  justify-content: center;
}

.not-found-card {
  max-width: 26rem;
  padding: 2.5rem 2rem;
}

.not-found-icon {
  width: 3.25rem;
  height: 3.25rem;
  margin: 0 auto;
  border-radius: 9999px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgb(var(--brand-400));
  background: rgb(var(--brand-400) / 0.12);
  border: 1px solid rgb(var(--brand-400) / 0.3);
}

.not-found-path {
  color: rgb(var(--slate-200));
  background: rgb(var(--surface-raised) / 0.7);
  border-radius: 0.25rem;
  padding: 0.05rem 0.35rem;
  font-size: 0.8em;
  word-break: break-all;
}
</style>
