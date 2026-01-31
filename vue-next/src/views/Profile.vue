<script setup>
import BaseCard from '../components/base/BaseCard.vue'
import BaseInput from '../components/base/BaseInput.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import { ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const router = useRouter()

const form = ref({
  name: authStore.user?.email || '',
  email: authStore.user?.email || '',
  device: 'SignGlove-V2'
})

const handleLogout = async () => {
    await authStore.logout()
    router.push('/login')
}
</script>

<template>
  <div class="max-w-2xl mx-auto">
    <h1 class="text-3xl font-bold text-white mb-8">Profile Settings</h1>

    <div class="space-y-6">
      <!-- User Info -->
      <BaseCard>
        <h2 class="text-xl font-bold text-white mb-6 pb-4 border-b border-white/5">Personal Information</h2>
        <div class="space-y-4">
            <BaseInput label="Display Name" v-model="form.name" />
            <BaseInput label="Email Address" type="email" v-model="form.email" readonly />
        </div>
        <div class="mt-6 flex justify-end">
            <BaseBtn>Save Changes</BaseBtn>
        </div>
      </BaseCard>

      <!-- Device Settings -->
      <BaseCard>
        <h2 class="text-xl font-bold text-white mb-6 pb-4 border-b border-white/5">Device Configuration</h2>
        <div class="space-y-4">
            <BaseInput label="Active Device" v-model="form.device" />
            
            <div class="flex items-center justify-between py-2">
                <div>
                   <div class="text-white font-medium">Haptic Feedback</div>
                   <div class="text-sm text-slate-400">Vibrate when gesture is recognized</div>
                </div>
                <div class="w-12 h-6 bg-indigo-600 rounded-full cursor-pointer relative">
                    <div class="absolute right-1 top-1 bottom-1 w-4 bg-white rounded-full"></div>
                </div>
            </div>
             <div class="flex items-center justify-between py-2">
                <div>
                   <div class="text-white font-medium">Auto-Connect</div>
                   <div class="text-sm text-slate-400">Connect to glove on startup</div>
                </div>
                <div class="w-12 h-6 bg-slate-700 rounded-full cursor-pointer relative">
                    <div class="absolute left-1 top-1 bottom-1 w-4 bg-white rounded-full"></div>
                </div>
            </div>
        </div>
      </BaseCard>

        <div class="flex items-center justify-between">
            <BaseBtn @click="handleLogout" class="bg-red-500/10 hover:bg-red-500/20 text-red-500 border-red-500/20">
                Sign Out
            </BaseBtn>
        </div>
    </div>
  </div>
</template>
