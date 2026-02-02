<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import BaseBtn from '../components/base/BaseBtn.vue'
import BaseInput from '../components/base/BaseInput.vue'

const router = useRouter()
const authStore = useAuthStore()

const email = ref('')
const password = ref('')
const isLoading = ref(false)
const error = ref('')

const handleLogin = async () => {
  isLoading.value = true
  error.value = ''
  try {
    await authStore.login(email.value, password.value)
    router.push('/')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Login failed. Please check your credentials.'
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-slate-950 flex items-center justify-center p-4">
    <div class="bg-slate-900 border border-slate-800 p-8 rounded-2xl w-full max-w-md shadow-2xl">
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold text-white mb-2">SilentVoix</h1>
        <p class="text-slate-400">Sign Language Translation System</p>
      </div>

      <form @submit.prevent="handleLogin" class="space-y-6">
        <BaseInput 
            v-model="email" 
            label="Email" 
            type="email" 
            placeholder="admin@example.com"
            required
        />
        <BaseInput 
            v-model="password" 
            label="Password" 
            type="password" 
            placeholder="••••••••"
            required
        />

        <div v-if="error" class="text-red-500 text-sm bg-red-500/10 p-3 rounded-lg border border-red-500/20">
            {{ error }}
        </div>

        <BaseBtn 
            variant="primary" 
            class="w-full justify-center" 
            :disabled="isLoading"
        >
            <span v-if="isLoading">Signing in...</span>
            <span v-else>Sign In</span>
        </BaseBtn>
      </form>
    </div>
  </div>
</template>
