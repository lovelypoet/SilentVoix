<script setup>
import BaseCard from '../components/base/BaseCard.vue'
import BaseInput from '../components/base/BaseInput.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import { ref, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth.js'
import api from '../services/api.js'
import { useToast } from 'primevue/usetoast'; // Import useToast

const authStore = useAuthStore()
const toast = useToast(); // Initialize toast

const form = ref({
  name: authStore.user?.email || '',
  email: authStore.user?.email || '',
  device: 'SignGlove-V2'
})

onMounted(() => {
  if (authStore.user) {
    form.value.name = authStore.user.display_name || ''
    form.value.email = authStore.user.email || ''
    // form.value.device = authStore.user.device || '' // Assuming device might be part of user profile
  }
})

const saveChanges = async () => {
  try {
    const updatedUser = await api.auth.updateProfile({
      display_name: form.value.name,
      email: form.value.email,
      // device: form.value.device, // Include if device is part of user profile update
    })
    authStore.user = updatedUser
    localStorage.setItem('user', JSON.stringify(updatedUser))
    toast.add({ severity: 'success', summary: 'Success', detail: 'Profile updated successfully!', life: 3000 });
  } catch (error) {
    console.error('Failed to update profile:', error)
    toast.add({ severity: 'error', summary: 'Error', detail: 'Failed to update profile.', life: 3000 });
  }
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
            <BaseInput v-model="form.name" label="Display Name" />
            <BaseInput v-model="form.email" label="Email Address" type="email" />
        </div>
        <div class="mt-6 flex justify-end">
            <BaseBtn @click="saveChanges">Save Changes</BaseBtn>
        </div>
      </BaseCard>

      <!-- Device Settings -->
      <BaseCard>
        <h2 class="text-xl font-bold text-white mb-6 pb-4 border-b border-white/5">Device Configuration</h2>
        <div class="space-y-4">
            <BaseInput v-model="form.device" label="Active Device" />
            
            <div class="flex items-center justify-between py-2">
                <div>
                   <div class="text-white font-medium">Haptic Feedback</div>
                   <div class="text-sm text-slate-400">Vibrate when gesture is recognized</div>
                </div>
                <div class="w-12 h-6 bg-teal-600 rounded-full cursor-pointer relative">
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
            <BaseBtn class="bg-red-500/10 hover:bg-red-500/20 text-red-500 border-red-500/20" @click="handleLogout">
                Sign Out
            </BaseBtn>
        </div>
    </div>
  </div>
</template>
