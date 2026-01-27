<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import api from '../services/api'
import { useToast } from 'primevue/usetoast' // Import useToast
import Dialog from 'primevue/dialog' // Import Dialog
import InputText from 'primevue/inputtext' // Import InputText

const router = useRouter()
const toast = useToast() // Initialize toast

const gestures = ref([])
const displayDialog = ref(false)
const newGestureNameInput = ref('')

const recordNewGesture = () => {
  newGestureNameInput.value = '' // Clear previous input
  displayDialog.value = true // Open the dialog
}

const confirmRecordNewGesture = () => {
  if (newGestureNameInput.value.trim()) {
    router.push({ path: '/training', query: { newGestureName: newGestureNameInput.value.trim() } })
    toast.add({ severity: 'success', summary: 'Gesture Recording Started', detail: `Recording for "${newGestureNameInput.value.trim()}"`, life: 3000 })
    displayDialog.value = false
  } else {
    toast.add({ severity: 'error', summary: 'Input Required', detail: 'Please enter a name for the new gesture.', life: 3000 })
  }
}

const cancelRecordNewGesture = () => {
  displayDialog.value = false
  newGestureNameInput.value = ''
  toast.add({ severity: 'info', summary: 'Cancelled', detail: 'Gesture recording cancelled.', life: 3000 })
}

onMounted(async () => {
    try {
        const res = await api.gestures.getAll()
        gestures.value = Array.isArray(res) ? res : []
    } catch (e) {
        gestures.value = []
    }
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex justify-between items-center">
      <div>
        <h1 class="text-3xl font-bold text-white">Gesture Library</h1>
        <p class="text-slate-400">View and manage your learned signs</p>
      </div>
      <BaseBtn variant="primary" @click="recordNewGesture">Record New</BaseBtn>
    </div>

    <!-- Filter/Search Bar -->
    <div class="flex gap-4">
       <input type="text" placeholder="Search gestures..." class="bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-white w-64 focus:border-indigo-500 focus:outline-none" />
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
       <BaseCard v-for="gesture in gestures" :key="gesture.id" class="group hover:border-indigo-500/50 transition-all">
          <div class="flex justify-between items-start mb-4">
             <div class="bg-emerald-500/10 text-emerald-500 px-2 py-1 rounded text-xs font-bold">ACTIVE</div>
             <button class="text-slate-600 hover:text-indigo-400">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 256 256"><path fill="currentColor" d="M192 120a8 8 0 0 1-8 8H72a8 8 0 0 1 0-16h112a8 8 0 0 1 8 8m0 32a8 8 0 0 1-8 8H72a8 8 0 0 1 0-16h112a8 8 0 0 1 8 8m0 32a8 8 0 0 1-8 8H72a8 8 0 0 1 0-16h112a8 8 0 0 1 8 8M216 40H40a16 16 0 0 0-16 16v144a16 16 0 0 0 16 16h176a16 16 0 0 0 16-16V56a16 16 0 0 0-16-16m0 160H40V56h176Z"/></svg>
             </button>
          </div>
          
          <h3 class="text-lg font-bold text-white mb-1">{{ gesture.title || ('Gesture ' + gesture.id) }}</h3>
          <div class="text-sm text-slate-400 mb-4">{{ gesture.samples || 0 }} samples collected</div>

          <div class="flex items-center gap-2 mb-4">
             <div class="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div class="h-full bg-indigo-500 rounded-full" :style="{ width: (gesture.accuracy || 0) + '%' }"></div>
             </div>
             <span class="text-xs text-indigo-400">{{ gesture.accuracy || 0 }}%</span>
          </div>

          <div class="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
             <BaseBtn variant="secondary" class="flex-1 text-xs py-1.5">Edit</BaseBtn>
             <BaseBtn variant="danger" class="flex-1 text-xs py-1.5">Delete</BaseBtn>
          </div>
       </BaseCard>

       <BaseCard v-if="gestures.length === 0" class="col-span-full p-8 text-center text-slate-500">
         No gestures found in library.
       </BaseCard>
    </div>

    <Dialog v-model:visible="displayDialog" modal header="Record New Gesture" :style="{ width: '30rem' }" @hide="cancelRecordNewGesture">
      <div class="p-fluid">
        <div class="field">
          <label for="gestureName" class="font-bold mb-3">Gesture Name</label>
          <InputText id="gestureName" v-model="newGestureNameInput" autofocus @keyup.enter="confirmRecordNewGesture" class="bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all duration-200" />
        </div>
      </div>
      <template #footer>
        <BaseBtn variant="secondary" @click="cancelRecordNewGesture">Cancel</BaseBtn>
        <BaseBtn variant="primary" @click="confirmRecordNewGesture">Record</BaseBtn>
      </template>
    </Dialog>
  </div>
</template>
