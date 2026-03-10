<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import { useToast } from 'primevue/usetoast'
import api from '../services/api'

const router = useRouter()
const toast = useToast()

const videos = ref([])
const isLoading = ref(false)
const error = ref('')
const isUploading = ref(false)
const uploadError = ref('')
const uploadName = ref('')
const uploadFile = ref(null)
let pollTimer = null

const hasActiveJobs = computed(() =>
  videos.value.some((v) => ['queued', 'processing'].includes(String(v?.status || '').toLowerCase()))
)

const loadVideos = async () => {
  isLoading.value = true
  error.value = ''
  try {
    const res = await api.videoLibrary.list()
    videos.value = Array.isArray(res?.videos) ? res.videos : []
  } catch (e) {
    error.value = e?.response?.data?.detail || 'Failed to load video library.'
  } finally {
    isLoading.value = false
  }
}

const onPickFile = (event) => {
  const file = event?.target?.files?.[0]
  uploadFile.value = file || null
}

const uploadVideo = async () => {
  uploadError.value = ''
  if (!uploadFile.value) {
    uploadError.value = 'Pick a video file first.'
    return
  }
  isUploading.value = true
  try {
    const form = new FormData()
    form.append('video_file', uploadFile.value)
    if (uploadName.value) {
      form.append('name', uploadName.value)
    }
    await api.videoLibrary.upload(form)
    uploadName.value = ''
    uploadFile.value = null
    toast.add({ severity: 'success', summary: 'Upload Started', detail: 'Video processing job created.', life: 3000 })
    await loadVideos()
  } catch (e) {
    uploadError.value = e?.response?.data?.detail || 'Upload failed.'
  } finally {
    isUploading.value = false
  }
}

const deleteVideo = async (jobId) => {
  try {
    await api.videoLibrary.delete(jobId)
    await loadVideos()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Delete Failed', detail: 'Could not delete video entry.', life: 3000 })
  }
}

const downloadVideo = (jobId) => {
  const url = api.videoLibrary.downloadUrl(jobId)
  window.open(url, '_blank')
}

const statusBadgeClass = (status) => {
  const s = String(status || '').toLowerCase()
  if (s === 'completed') return 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
  if (s === 'failed') return 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
  if (s === 'processing') return 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
  return 'bg-slate-500/20 text-slate-300 border border-slate-500/40'
}

onMounted(async () => {
  await loadVideos()
  pollTimer = window.setInterval(async () => {
    if (hasActiveJobs.value) {
      await loadVideos()
    }
  }, 3000)
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>

<template>
  <div class="max-w-6xl mx-auto space-y-6">
    <section class="flex items-center justify-between">
      <div>
        <h1 class="text-3xl font-bold text-white">Video Library</h1>
        <p class="text-slate-400 mt-1">Store up to 5 processed videos for quick playback in the playground.</p>
      </div>
      <BaseBtn variant="secondary" @click="router.push('/training')">Back to Training</BaseBtn>
    </section>

    <BaseCard>
      <h2 class="text-lg font-semibold text-white">Upload Video</h2>
      <p class="text-xs text-slate-400 mt-1">Supported: mp4, avi, mov. Max 5 videos in library.</p>
      <div class="mt-4 grid grid-cols-1 md:grid-cols-[1fr_auto] gap-3">
        <div class="space-y-2">
          <input
            type="text"
            v-model="uploadName"
            placeholder="Optional name"
            class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white"
          />
          <input
            type="file"
            accept="video/*"
            @change="onPickFile"
            class="w-full text-slate-300"
          />
          <p v-if="uploadError" class="text-xs text-rose-400">{{ uploadError }}</p>
        </div>
        <div class="flex items-start">
          <BaseBtn variant="primary" :disabled="isUploading" @click="uploadVideo">
            {{ isUploading ? 'Uploading...' : 'Upload & Process' }}
          </BaseBtn>
        </div>
      </div>
    </BaseCard>

    <BaseCard>
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-lg font-semibold text-white">Library</h2>
        <span class="text-xs text-slate-500">Limit: 5 videos</span>
      </div>

      <div v-if="isLoading" class="text-slate-400 text-sm">Loading videos...</div>
      <div v-else-if="error" class="text-rose-400 text-sm">{{ error }}</div>
      <div v-else-if="videos.length === 0" class="text-slate-500 text-sm">No videos yet.</div>

      <div v-else class="space-y-3">
        <div
          v-for="video in videos"
          :key="video.id"
          class="flex flex-col md:flex-row md:items-center justify-between gap-3 bg-slate-900/60 border border-slate-800 rounded-lg p-3"
        >
          <div>
            <div class="text-white font-semibold">{{ video.name || video.id }}</div>
            <div class="text-xs text-slate-400">Created: {{ new Date(video.created_at).toLocaleString() }}</div>
            <div class="text-xs text-slate-500 mt-1">Progress: {{ Math.round((video.progress || 0) * 100) }}%</div>
          </div>
          <div class="flex flex-wrap items-center justify-end gap-2 w-full md:w-auto md:ml-auto">
            <span :class="['text-xs px-2 py-1 rounded', statusBadgeClass(video.status)]">
              {{ video.status || 'queued' }}
            </span>
            <BaseBtn
              v-if="video.status === 'completed'"
              variant="secondary"
              class="h-8"
              @click="downloadVideo(video.id)"
            >
              Download
            </BaseBtn>
            <BaseBtn variant="secondary" class="h-8" @click="deleteVideo(video.id)">Delete</BaseBtn>
          </div>
        </div>
      </div>
    </BaseCard>
  </div>
</template>
