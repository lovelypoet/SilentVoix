<script setup>
import { ref } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { PhCircleNotch } from '@phosphor-icons/vue'
import api from '../services/api'
import BaseBtn from '../components/base/BaseBtn.vue'
import BaseInput from '../components/base/BaseInput.vue'
import LoginGalaxyBackground from '../components/LoginGalaxyBackground.vue'
import AuthBackLink from '../components/AuthBackLink.vue'

const router = useRouter()

const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const isLoading = ref(false)
const error = ref('')
const success = ref('')

const handleRegister = async () => {
  error.value = ''
  success.value = ''

  if (password.value.length < 8) {
    error.value = 'Password must be at least 8 characters.'
    return
  }

  if (password.value !== confirmPassword.value) {
    error.value = 'Passwords do not match.'
    return
  }

  isLoading.value = true
  try {
    await api.auth.register(email.value, password.value)
    success.value = 'Account created. Redirecting to login...'
    setTimeout(() => {
      router.push('/login')
    }, 1200)
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to create account.'
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen register-page flex items-center justify-center p-4">
    <LoginGalaxyBackground />
    <AuthBackLink />
    <div class="register-card auth-card-enter bg-[rgb(var(--surface))] border border-[rgb(var(--border-default))] p-8 rounded-xl w-full max-w-md shadow-2xl">
      <div class="flex flex-col items-center text-center mb-8">
        <RouterLink to="/" class="focus-ring auth-home-mark mb-4" aria-label="SilentVoix home">
          <span class="brand-orbit"><span></span></span>
        </RouterLink>
        <h1 class="text-xl font-medium tracking-tight text-slate-100">Create Account</h1>
        <p class="text-sm text-slate-400 mt-1">Join SilentVoix</p>
      </div>

      <form class="space-y-5" @submit.prevent="handleRegister">
        <BaseInput
          v-model="email"
          label="Email"
          type="email"
          placeholder="you@example.com"
          autocomplete="username"
          required
        />

        <BaseInput
          v-model="password"
          label="Password"
          type="password"
          placeholder="At least 8 characters"
          autocomplete="new-password"
          minlength="8"
          required
        />

        <BaseInput
          v-model="confirmPassword"
          label="Confirm Password"
          type="password"
          placeholder="Re-enter password"
          autocomplete="new-password"
          required
        />

        <div v-if="error" role="alert" class="text-danger-500 text-sm bg-danger-500/10 p-3 rounded-lg border border-danger-500/20">
          {{ error }}
        </div>

        <div v-if="success" role="status" class="text-success-300 text-sm bg-success-500/10 p-3 rounded-lg border border-success-500/20">
          {{ success }}
        </div>

        <BaseBtn
          variant="primary"
          class="w-full justify-center"
          :disabled="isLoading"
        >
          <PhCircleNotch v-if="isLoading" size="16" weight="bold" class="animate-spin" aria-hidden="true" />
          {{ isLoading ? 'Creating account…' : 'Create Account' }}
        </BaseBtn>
      </form>

      <div class="mt-6 text-center text-sm text-slate-400">
        Already have an account?
        <RouterLink to="/login" class="focus-ring text-brand-400 hover:text-brand-300 underline underline-offset-2 ml-1">
          Sign In
        </RouterLink>
      </div>
    </div>
  </div>
</template>

<style scoped>
.register-page {
  position: relative;
  isolation: isolate;
  background: radial-gradient(circle at 20% 20%, #1a1638 0%, #020617 55%, #000000 100%);
}

.register-card {
  position: relative;
  z-index: 2;
}
/* Card rises in over the galaxy; brand mark doubles as a home link. */
.auth-card-enter {
  animation: auth-card-in 700ms var(--ease-out) backwards;
}

@keyframes auth-card-in {
  from {
    opacity: 0;
    transform: translateY(18px) scale(0.98);
  }
}

.auth-home-mark {
  border-radius: 9999px;
  cursor: pointer;
  transition: transform var(--dur) var(--ease-spring);
}

.auth-home-mark:hover {
  transform: scale(1.12);
}
</style>
