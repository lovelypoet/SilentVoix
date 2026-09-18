<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api'
import BaseBtn from '../components/base/BaseBtn.vue'
import BaseInput from '../components/base/BaseInput.vue'
import LoginGalaxyBackground from '../components/LoginGalaxyBackground.vue'

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
    <div class="register-card bg-[rgb(var(--surface))] border border-[rgb(var(--border-default))] p-8 rounded-xl w-full max-w-md shadow-2xl">
      <div class="flex flex-col items-center text-center mb-8">
        <span class="brand-orbit mb-4"><span></span></span>
        <h1 class="text-xl font-medium tracking-tight text-slate-100">Create Account</h1>
        <p class="text-sm text-slate-400 mt-1">Join SilentVoix</p>
      </div>

      <form class="space-y-5" @submit.prevent="handleRegister">
        <BaseInput
          v-model="email"
          label="Email"
          type="email"
          placeholder="you@example.com"
          required
        />

        <BaseInput
          v-model="password"
          label="Password"
          type="password"
          placeholder="At least 8 characters"
          required
        />

        <BaseInput
          v-model="confirmPassword"
          label="Confirm Password"
          type="password"
          placeholder="Re-enter password"
          required
        />

        <div v-if="error" class="text-danger-500 text-sm bg-danger-500/10 p-3 rounded-lg border border-danger-500/20">
          {{ error }}
        </div>

        <div v-if="success" class="text-success-300 text-sm bg-success-500/10 p-3 rounded-lg border border-success-500/20">
          {{ success }}
        </div>

        <BaseBtn
          variant="primary"
          class="w-full justify-center"
          :disabled="isLoading"
        >
          <span v-if="isLoading">Creating account...</span>
          <span v-else>Create Account</span>
        </BaseBtn>
      </form>

      <div class="mt-6 text-center text-sm text-slate-400">
        Already have an account?
        <button class="text-brand-400 hover:text-brand-300 underline underline-offset-2 ml-1" @click="router.push('/login')">
          Sign In
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.register-page {
  position: relative;
  isolation: isolate;
}

.register-card {
  position: relative;
  z-index: 2;
}
</style>
