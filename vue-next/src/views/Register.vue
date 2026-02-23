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
    <div class="register-card bg-slate-900/75 backdrop-blur-md border border-teal-500/20 p-8 rounded-2xl w-full max-w-md shadow-2xl">
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold text-teal-300 mb-2">Create Account</h1>
        <p class="text-slate-300">Join SilentVoix</p>
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

        <div v-if="error" class="text-red-500 text-sm bg-red-500/10 p-3 rounded-lg border border-red-500/20">
          {{ error }}
        </div>

        <div v-if="success" class="text-emerald-300 text-sm bg-emerald-500/10 p-3 rounded-lg border border-emerald-500/20">
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

      <div class="mt-6 text-center text-sm text-slate-300">
        Already have an account?
        <button class="text-teal-300 hover:text-teal-200 underline underline-offset-2 ml-1" @click="router.push('/login')">
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
