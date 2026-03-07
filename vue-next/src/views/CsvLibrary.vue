<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import BaseEllipsisMenu from '../components/base/BaseEllipsisMenu.vue'
import api from '../services/api'
const toast = useToast()
const route = useRoute()

const files = ref([])
const isLoading = ref(false)
const error = ref('')

const includeArchived = ref(false)
const pipeline = ref('early')
const mode = ref('single')
const compatibleOnly = ref(false)
const selectedByKey = ref({})
const selectingByName = ref({})

const compatibilityByName = ref({})
const checkingByName = ref({})
const archivingByName = ref({})
const deletingByName = ref({})
const reviewingByName = ref({})

const previewData = ref(null)
const previewLoading = ref(false)
const previewError = ref('')
const statsData = ref(null)
const statsLoading = ref(false)
const statsError = ref('')
const previewModalOpen = ref(false)
const statsModalOpen = ref(false)
const confirmDialogOpen = ref(false)
const confirmActionType = ref('')
const confirmFileName = ref('')
const confirmTypedName = ref('')
const reviewDialogOpen = ref(false)
const reviewFileName = ref('')
const reviewDecision = ref('')
const reviewNotes = ref('')

const schemaFilter = ref('all')
const validationFilter = ref('all')
const sortBy = ref('manual')
const dragFileName = ref(null)
const isReordering = ref(false)

const schemaOptions = computed(() => {
  const set = new Set(files.value.map(f => f.schema_id).filter(Boolean))
  return ['all', ...Array.from(set).sort()]
})

const workerValidationRank = (status = '') => {
  if (status === 'reject') return 0
  if (status === 'warning') return 1
  if (status === 'unreviewed') return 2
  if (status === 'pass') return 3
  return 4
}

const filteredFiles = computed(() => {
  const filtered = files.value.filter((file) => {
    const schemaMatch = schemaFilter.value === 'all' || file.schema_id === schemaFilter.value
    const status = String(file?.worker_validation?.status || 'unreviewed').toLowerCase()
    const validationMatch = validationFilter.value === 'all' || status === validationFilter.value
    return schemaMatch && validationMatch
  })

  if (sortBy.value === 'manual') {
    return filtered
  }

  const sorted = [...filtered]
  sorted.sort((a, b) => {
    const aStatus = String(a?.worker_validation?.status || 'unreviewed').toLowerCase()
    const bStatus = String(b?.worker_validation?.status || 'unreviewed').toLowerCase()
    const aModified = new Date(a?.modified_at || 0).getTime()
    const bModified = new Date(b?.modified_at || 0).getTime()
    const aOffset = Math.abs(Number(a?.worker_validation?.offset_ms ?? -1))
    const bOffset = Math.abs(Number(b?.worker_validation?.offset_ms ?? -1))

    if (sortBy.value === 'validation') {
      const rankDelta = workerValidationRank(aStatus) - workerValidationRank(bStatus)
      if (rankDelta !== 0) return rankDelta
      return bModified - aModified
    }

    if (sortBy.value === 'offset_desc') {
      if (aOffset !== bOffset) return bOffset - aOffset
      return bModified - aModified
    }

    if (sortBy.value === 'modified_asc') {
      return aModified - bModified
    }

    return bModified - aModified
  })

  return sorted
})
const isManualSort = computed(() => sortBy.value === 'manual')
const activeSelectionKey = computed(() => `${pipeline.value}:${mode.value}`)
const lateSelectionCvKey = computed(() => `${pipeline.value}:${mode.value}:cv`)
const lateSelectionSensorKey = computed(() => `${pipeline.value}:${mode.value}:sensor`)
const latePairStatus = computed(() => {
  if (pipeline.value !== 'late') return null
  const cv = selectedByKey.value?.[lateSelectionCvKey.value]
  const sensor = selectedByKey.value?.[lateSelectionSensorKey.value]
  return {
    cv,
    sensor,
    isComplete: Boolean(cv && sensor)
  }
})

const schemaModality = (schemaId = '') => {
  if (schemaId.startsWith('cv_')) return 'cv'
  if (schemaId.startsWith('sensor_')) return 'sensor'
  if (schemaId.startsWith('fusion_')) return 'fusion'
  return 'unknown'
}

const isFileSelectedForActiveSlot = (file) => {
  if (!file?.name) return false
  if (pipeline.value === 'late') {
    const modality = schemaModality(file.schema_id)
    if (modality !== 'cv' && modality !== 'sensor') return false
    const key = `${pipeline.value}:${mode.value}:${modality}`
    return selectedByKey.value?.[key]?.name === file.name
  }
  return selectedByKey.value?.[activeSelectionKey.value]?.name === file.name
}

const encodePathParam = (name) => name
  .split('/')
  .map(part => encodeURIComponent(part))
  .join('/')

const formatBytes = (value) => {
  const n = Number(value)
  if (!Number.isFinite(n) || n < 0) return '--'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

const formatDate = (value) => {
  if (!value) return '--'
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? '--' : d.toLocaleString()
}

const workerValidationClass = (status) => {
  if (status === 'pass') return 'bg-emerald-500/20 text-emerald-300'
  if (status === 'warning') return 'bg-amber-500/20 text-amber-300'
  if (status === 'reject') return 'bg-rose-500/20 text-rose-300'
  return 'bg-slate-800 text-slate-400'
}

const operatorReviewClass = (decision) => {
  if (decision === 'approved') return 'bg-emerald-500/15 text-emerald-200'
  if (decision === 'needs_review') return 'bg-amber-500/15 text-amber-200'
  if (decision === 'rejected') return 'bg-rose-500/15 text-rose-200'
  return 'bg-slate-800 text-slate-400'
}

const loadFiles = async () => {
  isLoading.value = true
  error.value = ''
  previewData.value = null
  previewError.value = ''
  statsData.value = null
  statsError.value = ''
  compatibilityByName.value = {}
  try {
    const res = compatibleOnly.value
      ? await api.admin.csvLibrary.listCompatible(pipeline.value, mode.value, includeArchived.value)
      : await api.admin.csvLibrary.listFiles(includeArchived.value)
    files.value = Array.isArray(res?.files) ? res.files : []
    await loadSelections()
  } catch (e) {
    error.value = e?.response?.data?.detail || 'Failed to load CSV Library files.'
    files.value = []
  } finally {
    isLoading.value = false
  }
}

const loadSelections = async () => {
  try {
    const res = await api.admin.csvLibrary.selection.getAll()
    selectedByKey.value = res?.selections || {}
  } catch {
    selectedByKey.value = {}
  }
}

const checkCompatibility = async (name) => {
  checkingByName.value = { ...checkingByName.value, [name]: true }
  try {
    const res = await api.admin.csvLibrary.compatibility(encodePathParam(name), pipeline.value, mode.value)
    compatibilityByName.value = {
      ...compatibilityByName.value,
      [name]: {
        checked: true,
        isCompatible: Boolean(res?.is_compatible),
        reason: res?.reason || '',
        compatibleSchemaIds: Array.isArray(res?.compatible_schema_ids) ? res.compatible_schema_ids : [],
        legacyRenameMap: res?.legacy_rename_map || {}
      }
    }
  } catch (e) {
    compatibilityByName.value = {
      ...compatibilityByName.value,
      [name]: {
        checked: true,
        isCompatible: false,
        reason: e?.response?.data?.detail || 'Compatibility check failed.',
        compatibleSchemaIds: [],
        legacyRenameMap: {}
      }
    }
  } finally {
    checkingByName.value = { ...checkingByName.value, [name]: false }
  }
}

const checkAllCompatibility = async () => {
  for (const f of filteredFiles.value) {
    // Sequential to avoid hammering rate limiter.
    await checkCompatibility(f.name)
  }
}

const openPreview = async (name) => {
  previewModalOpen.value = true
  previewLoading.value = true
  previewError.value = ''
  previewData.value = null
  try {
    const res = await api.admin.csvLibrary.preview(encodePathParam(name), 20, 0)
    previewData.value = res
  } catch (e) {
    previewError.value = e?.response?.data?.detail || 'Failed to load preview.'
  } finally {
    previewLoading.value = false
  }
}

const openStats = async (name) => {
  statsModalOpen.value = true
  statsLoading.value = true
  statsError.value = ''
  statsData.value = null
  try {
    const res = await api.admin.csvLibrary.stats(encodePathParam(name))
    statsData.value = res
  } catch (e) {
    statsError.value = e?.response?.data?.detail || 'Failed to load stats.'
  } finally {
    statsLoading.value = false
  }
}

const downloadFile = async (name) => {
  try {
    const blob = await api.admin.csvLibrary.download(encodePathParam(name))
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = name.split('/').pop() || 'dataset.csv'
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    error.value = e?.response?.data?.detail || 'Download failed.'
  }
}

const closePreviewModal = () => {
  previewModalOpen.value = false
}

const closeStatsModal = () => {
  statsModalOpen.value = false
}

const archiveFile = async (name) => {
  archivingByName.value = { ...archivingByName.value, [name]: true }
  try {
    await api.admin.csvLibrary.archive(encodePathParam(name))
    if (previewData.value?.name === name) previewData.value = null
    if (statsData.value?.name === name) statsData.value = null
    await loadFiles()
    toast.add({ severity: 'success', summary: 'Archived', detail: `${name} moved to archive.`, life: 3000 })
  } catch (e) {
    error.value = e?.response?.data?.detail || 'Archive failed.'
    toast.add({ severity: 'error', summary: 'Archive Failed', detail: error.value, life: 3500 })
  } finally {
    archivingByName.value = { ...archivingByName.value, [name]: false }
  }
}

const reviewLabel = (decision) => {
  if (decision === 'approved') return 'approved'
  if (decision === 'needs_review') return 'needs review'
  if (decision === 'rejected') return 'rejected'
  return decision
}

const reviewFile = async (name, decision, notes = '') => {
  reviewingByName.value = { ...reviewingByName.value, [name]: true }
  error.value = ''
  try {
    await api.admin.csvLibrary.review(encodePathParam(name), decision, notes)
    if (previewData.value?.name === name) {
      await openPreview(name)
    }
    if (statsData.value?.name === name) {
      await openStats(name)
    }
    await loadFiles()
    toast.add({ severity: 'success', summary: 'Review Saved', detail: `${name} marked as ${reviewLabel(decision)}.`, life: 3000 })
  } catch (e) {
    error.value = e?.response?.data?.detail || 'Failed to save review state.'
    toast.add({ severity: 'error', summary: 'Review Failed', detail: error.value, life: 3500 })
  } finally {
    reviewingByName.value = { ...reviewingByName.value, [name]: false }
  }
}

const deleteFilePermanently = async (name) => {
  deletingByName.value = { ...deletingByName.value, [name]: true }
  error.value = ''
  try {
    await api.admin.csvLibrary.deletePermanent(encodePathParam(name), name)
    if (previewData.value?.name === name) previewData.value = null
    if (statsData.value?.name === name) statsData.value = null
    await loadFiles()
    toast.add({ severity: 'success', summary: 'Deleted', detail: `${name} was permanently deleted.`, life: 3000 })
  } catch (e) {
    error.value = e?.response?.data?.detail || 'Permanent delete failed.'
    toast.add({ severity: 'error', summary: 'Delete Failed', detail: error.value, life: 3500 })
  } finally {
    deletingByName.value = { ...deletingByName.value, [name]: false }
  }
}

const useDataset = async (name) => {
  selectingByName.value = { ...selectingByName.value, [name]: true }
  error.value = ''
  try {
    const file = files.value.find(f => f.name === name)
    const modality = pipeline.value === 'late' ? schemaModality(file?.schema_id) : null
    await api.admin.csvLibrary.selection.set(name, pipeline.value, mode.value, modality)
    await loadSelections()
    toast.add({
      severity: 'success',
      summary: 'Dataset Selected',
      detail: `${name} selected for ${pipeline.value}/${mode.value}${pipeline.value === 'late' ? `/${modality}` : ''}.`,
      life: 2800
    })
  } catch (e) {
    error.value = e?.response?.data?.detail || 'Failed to set selected dataset.'
    toast.add({ severity: 'error', summary: 'Selection Failed', detail: error.value, life: 3500 })
  } finally {
    selectingByName.value = { ...selectingByName.value, [name]: false }
  }
}

const openArchiveConfirm = (name) => {
  confirmActionType.value = 'archive'
  confirmFileName.value = name
  confirmTypedName.value = ''
  confirmDialogOpen.value = true
}

const openDeleteConfirm = (name) => {
  confirmActionType.value = 'delete'
  confirmFileName.value = name
  confirmTypedName.value = ''
  confirmDialogOpen.value = true
}

const closeConfirmDialog = () => {
  confirmDialogOpen.value = false
  confirmActionType.value = ''
  confirmFileName.value = ''
  confirmTypedName.value = ''
}

const openReviewDialog = (name, decision) => {
  reviewFileName.value = name
  reviewDecision.value = decision
  reviewNotes.value = ''
  reviewDialogOpen.value = true
}

const closeReviewDialog = () => {
  reviewDialogOpen.value = false
  reviewFileName.value = ''
  reviewDecision.value = ''
  reviewNotes.value = ''
}

const submitReviewDialog = async () => {
  const name = reviewFileName.value
  const decision = reviewDecision.value
  const notes = reviewNotes.value
  if (!name || !decision) {
    closeReviewDialog()
    return
  }
  closeReviewDialog()
  await reviewFile(name, decision, notes)
}

const confirmDialogSubmit = async () => {
  const action = confirmActionType.value
  const name = confirmFileName.value
  if (!name) {
    closeConfirmDialog()
    return
  }

  if (action === 'delete') {
    if (confirmTypedName.value !== name) {
      toast.add({
        severity: 'warn',
        summary: 'Name Mismatch',
        detail: 'Type the exact file name to confirm delete.',
        life: 3200
      })
      return
    }
    closeConfirmDialog()
    await deleteFilePermanently(name)
    return
  }

  if (action === 'archive') {
    closeConfirmDialog()
    await archiveFile(name)
  }
}

const checkCompatibilityFromMenu = async (name, close) => {
  await checkCompatibility(name)
  close()
}

const previewFromMenu = async (name, close) => {
  await openPreview(name)
  close()
}

const statsFromMenu = async (name, close) => {
  await openStats(name)
  close()
}

const downloadFromMenu = async (name, close) => {
  await downloadFile(name)
  close()
}

const useFromMenu = async (name, close) => {
  await useDataset(name)
  close()
}

const archiveConfirmFromMenu = (name, close) => {
  openArchiveConfirm(name)
  close()
}

const deleteConfirmFromMenu = (name, close) => {
  openDeleteConfirm(name)
  close()
}

const reviewFromMenu = (name, decision, close) => {
  openReviewDialog(name, decision)
  close()
}

const reorderSubset = (allNames, visibleNames, nextVisibleNames) => {
  const visibleSet = new Set(visibleNames)
  const queue = [...nextVisibleNames]
  return allNames.map((name) => (visibleSet.has(name) ? queue.shift() : name))
}

const persistCsvOrder = async (orderedNames) => {
  isReordering.value = true
  error.value = ''
  try {
    await api.admin.csvLibrary.reorder(orderedNames)
  } catch (e) {
    error.value = e?.response?.data?.detail || 'Failed to reorder CSV files.'
    await loadFiles()
  } finally {
    isReordering.value = false
  }
}

const onRowDragStart = (name) => {
  if (!isManualSort.value || isReordering.value) return
  dragFileName.value = name
}

const onRowDragOver = (event, name) => {
  if (!isManualSort.value || isReordering.value || !dragFileName.value || dragFileName.value === name) return
  event.preventDefault()
}

const onRowDrop = async (name) => {
  if (!isManualSort.value || isReordering.value || !dragFileName.value || dragFileName.value === name) {
    dragFileName.value = null
    return
  }

  const visibleNames = filteredFiles.value.map((file) => file.name)
  const fromIndex = visibleNames.indexOf(dragFileName.value)
  const toIndex = visibleNames.indexOf(name)
  if (fromIndex < 0 || toIndex < 0) {
    dragFileName.value = null
    return
  }

  const nextVisibleNames = [...visibleNames]
  const [moved] = nextVisibleNames.splice(fromIndex, 1)
  nextVisibleNames.splice(toIndex, 0, moved)

  const allNames = files.value.map((file) => file.name)
  const mergedNames = reorderSubset(allNames, visibleNames, nextVisibleNames)
  const byName = Object.fromEntries(files.value.map((file) => [file.name, file]))
  files.value = mergedNames.map((fileName) => byName[fileName]).filter(Boolean)
  dragFileName.value = null
  await persistCsvOrder(mergedNames)
}

const onRowDragEnd = () => {
  dragFileName.value = null
}

const menuItemClass = 'w-full text-left px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50'
const menuAccentClass = 'w-full text-left px-3 py-2 text-sm text-cyan-300 hover:bg-slate-800 disabled:opacity-50'
const menuWarningClass = 'w-full text-left px-3 py-2 text-sm text-amber-300 hover:bg-slate-800 disabled:opacity-50'
const menuDangerClass = 'w-full text-left px-3 py-2 text-sm text-red-300 hover:bg-red-500/10 disabled:opacity-50'

onMounted(() => {
  const queryPipeline = String(route.query?.pipeline || '').toLowerCase()
  const queryMode = String(route.query?.mode || '').toLowerCase()
  if (queryPipeline === 'early' || queryPipeline === 'late') {
    pipeline.value = queryPipeline
  }
  if (queryMode === 'single' || queryMode === 'dual') {
    mode.value = queryMode
  }
  void loadFiles()
})

watch([compatibleOnly, pipeline, mode, includeArchived], () => {
  void loadFiles()
})

</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
      <div>
        <h1 class="text-3xl font-bold text-white">CSV Library</h1>
        <p class="text-slate-400 text-sm">Admin data controller for schema validation and compatibility checks.</p>
      </div>
      <div class="flex gap-2">
        <BaseBtn variant="secondary" :disabled="isLoading" @click="loadFiles">
          {{ isLoading ? 'Refreshing...' : 'Refresh' }}
        </BaseBtn>
      </div>
    </div>

    <BaseCard>
      <div class="grid grid-cols-1 md:grid-cols-7 gap-3">
        <label class="text-sm text-slate-300 md:col-span-1">
          Pipeline
          <select v-model="pipeline" class="mt-1 w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white">
            <option value="early">Early</option>
            <option value="late">Late</option>
          </select>
        </label>

        <label class="text-sm text-slate-300 md:col-span-1">
          Mode
          <select v-model="mode" class="mt-1 w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white">
            <option value="single">Single</option>
            <option value="dual">Dual</option>
          </select>
        </label>

        <label class="text-sm text-slate-300 md:col-span-1">
          Schema
          <select v-model="schemaFilter" class="mt-1 w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white">
            <option v-for="item in schemaOptions" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>

        <label class="text-sm text-slate-300 md:col-span-1">
          Validation
          <select v-model="validationFilter" class="mt-1 w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white">
            <option value="all">all</option>
            <option value="pass">pass</option>
            <option value="warning">warning</option>
            <option value="reject">reject</option>
            <option value="unreviewed">unreviewed</option>
          </select>
        </label>

        <label class="text-sm text-slate-300 md:col-span-1">
          Sort
          <select v-model="sortBy" class="mt-1 w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white">
            <option value="manual">manual order</option>
            <option value="modified_desc">modified: newest</option>
            <option value="modified_asc">modified: oldest</option>
            <option value="validation">validation: worst first</option>
            <option value="offset_desc">offset: largest first</option>
          </select>
        </label>

        <label class="text-sm text-slate-300 md:col-span-1 flex items-end">
          <input v-model="includeArchived" type="checkbox" class="mr-2" /> Include archived
        </label>

        <div class="md:col-span-1 flex items-end">
          <BaseBtn variant="primary" class="w-full" :disabled="isLoading || filteredFiles.length === 0" @click="checkAllCompatibility">
            Check Compatibility
          </BaseBtn>
        </div>
      </div>
      <div class="mt-3">
        <label class="text-sm text-slate-300 inline-flex items-center">
          <input v-model="compatibleOnly" type="checkbox" class="mr-2" />
          Compatible only for selected pipeline/mode (training picker view)
        </label>
      </div>
      <div v-if="pipeline === 'late'" class="mt-3 rounded border border-slate-700 bg-slate-900/50 p-3 text-xs">
        <p class="text-slate-300">
          Late fusion needs both slots selected:
          <span :class="latePairStatus?.cv ? 'text-emerald-300' : 'text-amber-300'">CV</span> +
          <span :class="latePairStatus?.sensor ? 'text-emerald-300' : 'text-amber-300'">Sensor</span>
        </p>
        <p class="mt-1" :class="latePairStatus?.isComplete ? 'text-emerald-300' : 'text-amber-300'">
          {{ latePairStatus?.isComplete ? 'Pair complete for late-fusion training.' : 'Pair incomplete: select both CV and Sensor datasets.' }}
        </p>
      </div>

      <p v-if="error" class="text-red-300 text-sm mt-3">{{ error }}</p>
      <p class="mt-2 text-xs" :class="isManualSort ? 'text-cyan-300' : 'text-slate-500'">
        {{ isManualSort ? 'Drag rows to reorder datasets. The saved order persists across sessions.' : 'Switch Sort to manual order to drag and reorder.' }}
      </p>
    </BaseCard>

    <BaseCard>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-slate-400 border-b border-slate-800">
              <th class="py-2 pr-3">File</th>
              <th class="py-2 pr-3">Schema</th>
              <th class="py-2 pr-3">Rows</th>
              <th class="py-2 pr-3">Size</th>
              <th class="py-2 pr-3">Updated</th>
              <th class="py-2 pr-3">Validation</th>
              <th class="py-2 pr-3">Selected</th>
              <th class="py-2 pr-3">Compatibility</th>
              <th class="py-2 pr-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="isLoading">
              <td colspan="9" class="py-4 text-slate-400">Loading files...</td>
            </tr>
            <tr v-else-if="filteredFiles.length === 0">
              <td colspan="9" class="py-4 text-slate-400">No CSV files found.</td>
            </tr>
            <tr
              v-for="file in filteredFiles"
              :key="file.name"
              class="border-b border-slate-900/70"
              :class="isManualSort ? 'cursor-grab active:cursor-grabbing' : ''"
              :draggable="isManualSort && !isReordering"
              @dragstart="onRowDragStart(file.name)"
              @dragover="onRowDragOver($event, file.name)"
              @drop.prevent="onRowDrop(file.name)"
              @dragend="onRowDragEnd"
            >
              <td class="py-2 pr-3 text-slate-200 font-medium">{{ isManualSort ? ':: ' : '' }}{{ file.name }}</td>
              <td class="py-2 pr-3 text-slate-300">{{ file.schema_id }}</td>
              <td class="py-2 pr-3 text-slate-300">{{ file.row_count }}</td>
              <td class="py-2 pr-3 text-slate-300">{{ formatBytes(file.size_bytes) }}</td>
              <td class="py-2 pr-3 text-slate-300">{{ formatDate(file.modified_at) }}</td>
              <td class="py-2 pr-3">
                <span
                  class="px-2 py-1 rounded text-xs font-semibold"
                  :class="workerValidationClass(file.worker_validation?.status)"
                >
                  {{ file.worker_validation?.status || 'Unreviewed' }}
                </span>
                <p v-if="file.worker_validation?.offset_ms !== undefined && file.worker_validation?.offset_ms !== null" class="text-[11px] text-slate-500 mt-1">
                  offset {{ file.worker_validation.offset_ms }} ms
                </p>
                <p v-if="file.operator_review?.decision" class="mt-1">
                  <span class="px-2 py-1 rounded text-[11px] font-semibold" :class="operatorReviewClass(file.operator_review.decision)">
                    {{ file.operator_review.decision }}
                  </span>
                </p>
                <p v-if="file.review_history_count" class="text-[11px] text-slate-500 mt-1">
                  {{ file.review_history_count }} review {{ file.review_history_count === 1 ? 'entry' : 'entries' }}
                </p>
              </td>
              <td class="py-2 pr-3">
                <span
                  v-if="isFileSelectedForActiveSlot(file)"
                  class="px-2 py-1 rounded text-xs font-semibold bg-cyan-500/20 text-cyan-300"
                >
                  Active {{ pipeline === 'late' ? schemaModality(file.schema_id).toUpperCase() : '' }}
                </span>
                <span v-else class="text-xs text-slate-500">-</span>
              </td>
              <td class="py-2 pr-3">
                <div v-if="compatibilityByName[file.name]?.checked">
                  <span
                    class="px-2 py-1 rounded text-xs font-semibold"
                    :class="compatibilityByName[file.name]?.isCompatible ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'"
                  >
                    {{ compatibilityByName[file.name]?.isCompatible ? 'Compatible' : 'Not Compatible' }}
                  </span>
                  <p class="text-[11px] text-slate-500 mt-1">{{ compatibilityByName[file.name]?.reason }}</p>
                </div>
                <span v-else class="text-xs text-slate-500">Not checked</span>
              </td>
              <td class="py-2 pr-3">
                <BaseEllipsisMenu>
                  <template #menu="{ close }">
                    <button
                      :class="menuItemClass"
                      :disabled="checkingByName[file.name]"
                      @click="checkCompatibilityFromMenu(file.name, close)"
                    >
                      {{ checkingByName[file.name] ? 'Testing...' : 'Test Check' }}
                    </button>
                    <button
                      :class="menuItemClass"
                      @click="previewFromMenu(file.name, close)"
                    >
                      Preview
                    </button>
                    <button
                      :class="menuItemClass"
                      @click="statsFromMenu(file.name, close)"
                    >
                      Stats
                    </button>
                    <button
                      :class="menuItemClass"
                      @click="downloadFromMenu(file.name, close)"
                    >
                      Download
                    </button>
                    <button
                      :class="menuAccentClass"
                      :disabled="!file.worker_validation || reviewingByName[file.name]"
                      @click="reviewFromMenu(file.name, 'approved', close)"
                    >
                      {{ reviewingByName[file.name] ? 'Saving...' : 'Approve' }}
                    </button>
                    <button
                      :class="menuWarningClass"
                      :disabled="!file.worker_validation || reviewingByName[file.name]"
                      @click="reviewFromMenu(file.name, 'needs_review', close)"
                    >
                      {{ reviewingByName[file.name] ? 'Saving...' : 'Needs Review' }}
                    </button>
                    <button
                      :class="menuDangerClass"
                      :disabled="!file.worker_validation || reviewingByName[file.name]"
                      @click="reviewFromMenu(file.name, 'rejected', close)"
                    >
                      {{ reviewingByName[file.name] ? 'Saving...' : 'Reject Override' }}
                    </button>
                    <button
                      :class="menuAccentClass"
                      :disabled="selectingByName[file.name]"
                      @click="useFromMenu(file.name, close)"
                    >
                      {{ selectingByName[file.name] ? 'Selecting...' : 'Use' }}
                    </button>
                    <button
                      :class="menuWarningClass"
                      :disabled="file.scope === 'archive' || archivingByName[file.name]"
                      @click="archiveConfirmFromMenu(file.name, close)"
                    >
                      {{ file.scope === 'archive' ? 'Archived' : (archivingByName[file.name] ? 'Archiving...' : 'Archive') }}
                    </button>
                    <button
                      :class="menuDangerClass"
                      :disabled="deletingByName[file.name]"
                      @click="deleteConfirmFromMenu(file.name, close)"
                    >
                      {{ deletingByName[file.name] ? 'Deleting...' : 'Delete' }}
                    </button>
                  </template>
                </BaseEllipsisMenu>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </BaseCard>

    <div v-if="previewModalOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4" @click.self="closePreviewModal">
      <div class="w-full max-w-5xl rounded-xl border border-slate-700 bg-slate-950 p-5 shadow-2xl">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-lg font-semibold text-white">CSV Preview</h2>
          <BaseBtn variant="secondary" @click="closePreviewModal">Close</BaseBtn>
        </div>
        <p v-if="previewLoading" class="text-slate-400">Loading preview...</p>
        <p v-else-if="previewError" class="text-red-300">{{ previewError }}</p>
        <p v-else-if="!previewData" class="text-slate-500">No preview data.</p>
        <div v-else>
          <div class="text-sm text-slate-300 mb-3">
            {{ previewData.name }} | schema: {{ previewData.schema_id }} | check: {{ previewData.schema_check }}
          </div>
          <div class="max-h-[60vh] overflow-x-auto overflow-y-auto border border-slate-800 rounded">
            <table class="w-full text-xs">
              <thead>
                <tr class="bg-slate-900 text-slate-400">
                  <th v-for="h in previewData.header" :key="h" class="px-2 py-2 text-left">{{ h }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, idx) in previewData.rows" :key="`p-${idx}`" class="border-t border-slate-900">
                  <td v-for="h in previewData.header" :key="`c-${idx}-${h}`" class="px-2 py-1 text-slate-300">{{ row[h] }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <div v-if="statsModalOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4" @click.self="closeStatsModal">
      <div class="w-full max-w-3xl rounded-xl border border-slate-700 bg-slate-950 p-5 shadow-2xl">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-lg font-semibold text-white">CSV Stats</h2>
          <BaseBtn variant="secondary" @click="closeStatsModal">Close</BaseBtn>
        </div>
        <p v-if="statsLoading" class="text-slate-400">Loading stats...</p>
        <p v-else-if="statsError" class="text-red-300">{{ statsError }}</p>
        <p v-else-if="!statsData" class="text-slate-500">No stats data.</p>
        <div v-else class="space-y-3 text-sm max-h-[60vh] overflow-y-auto pr-1">
          <div class="text-slate-300">
            {{ statsData.name }} | schema: {{ statsData.schema_id }} | columns: {{ statsData.column_count }} | rows: {{ statsData.row_count }}
          </div>
          <div v-if="statsData.worker_validation" class="rounded border border-slate-800 p-3 bg-slate-950/40">
            <p class="text-slate-400 mb-1">Worker Validation</p>
            <div class="flex flex-wrap items-center gap-2">
              <span class="px-2 py-1 rounded text-xs font-semibold" :class="workerValidationClass(statsData.worker_validation.status)">
                {{ statsData.worker_validation.status }}
              </span>
              <span class="text-slate-200 text-xs">
                offset: {{ statsData.worker_validation.offset_ms ?? '--' }} ms
              </span>
            </div>
            <p class="text-slate-300 text-xs mt-2">
              {{ Array.isArray(statsData.worker_validation.reasons) ? statsData.worker_validation.reasons.join(' | ') : '--' }}
            </p>
            <div v-if="statsData.operator_review?.decision" class="mt-3">
              <span class="px-2 py-1 rounded text-xs font-semibold" :class="operatorReviewClass(statsData.operator_review.decision)">
                {{ statsData.operator_review.decision }}
              </span>
              <p class="text-slate-400 text-xs mt-2">
                reviewed at: {{ formatDate(statsData.operator_review.reviewed_at) }}
              </p>
              <p v-if="statsData.operator_review.notes" class="text-slate-300 text-xs mt-1">
                {{ statsData.operator_review.notes }}
              </p>
            </div>
            <div v-if="statsData.review_history?.length" class="mt-3">
              <p class="text-slate-400 text-xs mb-2">Review History</p>
              <div class="space-y-2">
                <div
                  v-for="(entry, idx) in statsData.review_history"
                  :key="`review-history-${idx}`"
                  class="rounded border border-slate-800 bg-slate-900/40 p-2"
                >
                  <div class="flex flex-wrap items-center gap-2">
                    <span class="px-2 py-1 rounded text-[11px] font-semibold" :class="operatorReviewClass(entry.decision)">
                      {{ entry.decision }}
                    </span>
                    <span class="text-slate-500 text-[11px]">
                      {{ formatDate(entry.reviewed_at) }}
                    </span>
                  </div>
                  <p v-if="entry.notes" class="text-slate-300 text-xs mt-2">
                    {{ entry.notes }}
                  </p>
                </div>
              </div>
            </div>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div class="rounded border border-slate-800 p-3 bg-slate-950/40">
              <p class="text-slate-400">Feature Dim</p>
              <p class="text-slate-200">
                expected: {{ statsData.expected_feature_dim ?? '--' }},
                actual: {{ statsData.actual_feature_dim ?? '--' }}
              </p>
              <p class="text-slate-400 mt-2">Missing Values</p>
              <p class="text-slate-200">{{ statsData.missing_values_count }}</p>
              <p class="text-slate-400 mt-2">Duplicate Timestamps</p>
              <p class="text-slate-200">{{ statsData.duplicate_timestamp_count }}</p>
            </div>
            <div class="rounded border border-slate-800 p-3 bg-slate-950/40">
              <p class="text-slate-400 mb-1">Health Flags</p>
              <div v-if="statsData.health_flags?.length" class="flex flex-wrap gap-2">
                <span
                  v-for="flag in statsData.health_flags"
                  :key="`flag-${flag}`"
                  class="px-2 py-1 rounded text-xs bg-slate-800 text-slate-200"
                >
                  {{ flag }}
                </span>
              </div>
              <p v-else class="text-emerald-300">No health flags.</p>
            </div>
          </div>
          <div class="rounded border border-slate-800 p-3 bg-slate-950/40">
            <p class="text-slate-400 mb-1">Schema Mismatch Details</p>
            <p v-if="!(statsData.schema_mismatch_details?.missing_required_columns?.length || statsData.schema_mismatch_details?.notes?.length)" class="text-emerald-300">
              No mismatch details.
            </p>
            <div v-else class="space-y-2">
              <div v-if="statsData.schema_mismatch_details?.missing_required_columns?.length">
                <p class="text-rose-300 text-xs">Missing required columns</p>
                <p class="text-slate-200 text-xs">
                  {{ statsData.schema_mismatch_details.missing_required_columns.join(', ') }}
                </p>
              </div>
              <div v-if="statsData.schema_mismatch_details?.notes?.length">
                <p class="text-amber-300 text-xs">Notes</p>
                <p class="text-slate-200 text-xs">
                  {{ statsData.schema_mismatch_details.notes.join(' | ') }}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="confirmDialogOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">
      <div class="w-full max-w-lg rounded-xl border border-slate-700 bg-slate-950 p-5 shadow-2xl">
        <h3 class="text-lg font-semibold text-white">
          {{ confirmActionType === 'delete' ? 'Confirm Permanent Delete' : 'Confirm Archive' }}
        </h3>
        <p class="mt-2 text-sm text-slate-300">
          <span v-if="confirmActionType === 'archive'">
            Archive <span class="font-semibold text-white">{{ confirmFileName }}</span>?
          </span>
          <span v-else>
            Delete <span class="font-semibold text-white">{{ confirmFileName }}</span> permanently. This cannot be undone.
          </span>
        </p>
        <div v-if="confirmActionType === 'delete'" class="mt-3">
          <label class="block text-xs text-slate-400 mb-1">Type exact file name to confirm</label>
          <input
            v-model="confirmTypedName"
            type="text"
            class="w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-slate-200"
            :placeholder="confirmFileName"
          />
        </div>
        <div class="mt-5 flex justify-end gap-2">
          <BaseBtn variant="secondary" @click="closeConfirmDialog">Cancel</BaseBtn>
          <BaseBtn variant="danger" @click="confirmDialogSubmit">
            {{ confirmActionType === 'delete' ? 'Delete Permanently' : 'Archive' }}
          </BaseBtn>
        </div>
      </div>
    </div>

    <div v-if="reviewDialogOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4" @click.self="closeReviewDialog">
      <div class="w-full max-w-lg rounded-xl border border-slate-700 bg-slate-950 p-5 shadow-2xl">
        <h3 class="text-lg font-semibold text-white">Save Review</h3>
        <p class="mt-2 text-sm text-slate-300">
          Mark <span class="font-semibold text-white">{{ reviewFileName }}</span> as
          <span class="font-semibold text-white">{{ reviewLabel(reviewDecision) }}</span>.
        </p>
        <div class="mt-3">
          <label class="block text-xs text-slate-400 mb-1">Review notes (optional)</label>
          <textarea
            v-model="reviewNotes"
            rows="4"
            class="w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-slate-200"
            placeholder="Explain why this dataset was approved, flagged, or overridden."
          />
        </div>
        <div class="mt-5 flex justify-end gap-2">
          <BaseBtn variant="secondary" @click="closeReviewDialog">Cancel</BaseBtn>
          <BaseBtn variant="primary" :disabled="reviewingByName[reviewFileName]" @click="submitReviewDialog">
            {{ reviewingByName[reviewFileName] ? 'Saving...' : 'Save Review' }}
          </BaseBtn>
        </div>
      </div>
    </div>
  </div>
</template>
