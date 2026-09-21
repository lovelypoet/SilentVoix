<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import { PhFileCsv, PhCircleNotch } from '@phosphor-icons/vue'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import BaseEllipsisMenu from '../components/base/BaseEllipsisMenu.vue'
import BasePageHeader from '../components/base/BasePageHeader.vue'
import BaseModal from '../components/base/BaseModal.vue'
import BaseEmptyState from '../components/base/BaseEmptyState.vue'
import api from '../services/api'
const toast = useToast()
const route = useRoute()

const files = ref([])
const isLoading = ref(false)
const error = ref('')

const pipeline = ref('early')
const mode = ref('single')
const compatibleOnly = ref(false)
const selectedByKey = ref({})
const selectingByName = ref({})

const compatibilityByName = ref({})
const checkingByName = ref({})
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
  if (status === 'pass') return 'bg-success-500/20 text-success-300'
  if (status === 'warning') return 'bg-warning-500/20 text-warning-300'
  if (status === 'reject') return 'bg-danger-500/20 text-danger-300'
  return 'bg-slate-800 text-slate-400'
}

const operatorReviewClass = (decision) => {
  if (decision === 'approved') return 'bg-success-500/15 text-success-200'
  if (decision === 'needs_review') return 'bg-warning-500/15 text-warning-200'
  if (decision === 'rejected') return 'bg-danger-500/15 text-danger-200'
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
      ? await api.admin.csvLibrary.listCompatible(pipeline.value, mode.value)
      : await api.admin.csvLibrary.listFiles()
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
const menuAccentClass = 'w-full text-left px-3 py-2 text-sm text-brand-300 hover:bg-slate-800 disabled:opacity-50'
const menuWarningClass = 'w-full text-left px-3 py-2 text-sm text-warning-300 hover:bg-slate-800 disabled:opacity-50'
const menuDangerClass = 'w-full text-left px-3 py-2 text-sm text-danger-300 hover:bg-danger-500/10 disabled:opacity-50'

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

watch([compatibleOnly, pipeline, mode], () => {
  void loadFiles()
})

</script>

<template>
  <div class="space-y-6">
    <BasePageHeader title="CSV Library" description="Admin data controller for schema validation and compatibility checks.">
      <template #actions>
        <BaseBtn variant="secondary" :disabled="isLoading" @click="loadFiles">
          {{ isLoading ? 'Refreshing...' : 'Refresh' }}
        </BaseBtn>
      </template>
    </BasePageHeader>

    <BaseCard>
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-7">
        <div>
          <label class="field-label" for="csv-filter-pipeline">Pipeline</label>
          <select id="csv-filter-pipeline" v-model="pipeline" class="field-control">
            <option value="early">Early</option>
            <option value="late">Late</option>
          </select>
        </div>

        <div>
          <label class="field-label" for="csv-filter-mode">Mode</label>
          <select id="csv-filter-mode" v-model="mode" class="field-control">
            <option value="single">Single</option>
            <option value="dual">Dual</option>
          </select>
        </div>

        <div>
          <label class="field-label" for="csv-filter-schema">Schema</label>
          <select id="csv-filter-schema" v-model="schemaFilter" class="field-control">
            <option v-for="item in schemaOptions" :key="item" :value="item">{{ item }}</option>
          </select>
        </div>

        <div>
          <label class="field-label" for="csv-filter-validation">Validation</label>
          <select id="csv-filter-validation" v-model="validationFilter" class="field-control">
            <option value="all">All</option>
            <option value="pass">Pass</option>
            <option value="warning">Warning</option>
            <option value="reject">Reject</option>
            <option value="unreviewed">Unreviewed</option>
          </select>
        </div>

        <div>
          <label class="field-label" for="csv-filter-sort">Sort</label>
          <select id="csv-filter-sort" v-model="sortBy" class="field-control">
            <option value="manual">Manual order</option>
            <option value="modified_desc">Modified: newest</option>
            <option value="modified_asc">Modified: oldest</option>
            <option value="validation">Validation: worst first</option>
            <option value="offset_desc">Offset: largest first</option>
          </select>
        </div>

        <div class="sm:col-span-2 md:col-span-2 flex items-end">
          <BaseBtn variant="primary" class="w-full" :disabled="isLoading || filteredFiles.length === 0" @click="checkAllCompatibility">
            Check Compatibility
          </BaseBtn>
        </div>
      </div>
      <div class="mt-4">
        <label class="inline-flex items-center gap-2 text-sm text-slate-300">
          <input v-model="compatibleOnly" type="checkbox" class="h-4 w-4 rounded border-[rgb(var(--border-default))] bg-[rgb(var(--surface))] accent-brand-500" />
          Compatible only for selected pipeline/mode (training picker view)
        </label>
      </div>
      <div v-if="pipeline === 'late'" class="mt-4 rounded-lg border border-[rgb(var(--border-default))] bg-[rgb(var(--surface))] p-3 text-xs">
        <p class="text-slate-300">
          Late fusion needs both slots selected:
          <span :class="latePairStatus?.cv ? 'text-success-300' : 'text-warning-300'">CV</span> +
          <span :class="latePairStatus?.sensor ? 'text-success-300' : 'text-warning-300'">Sensor</span>
        </p>
        <p class="mt-1" :class="latePairStatus?.isComplete ? 'text-success-300' : 'text-warning-300'">
          {{ latePairStatus?.isComplete ? 'Pair complete for late-fusion training.' : 'Pair incomplete: select both CV and Sensor datasets.' }}
        </p>
      </div>

      <p v-if="error" role="alert" class="text-danger-300 text-sm mt-4">{{ error }}</p>
    </BaseCard>

    <BaseCard>
      <div class="overflow-x-auto">
        <table class="data-table">
          <thead>
            <tr>
              <th>File</th>
              <th>Schema</th>
              <th>Rows</th>
              <th>Size</th>
              <th>Updated</th>
              <th>Validation</th>
              <th>Selected</th>
              <th>Compatibility</th>
              <th class="text-center">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="isLoading">
              <td colspan="9">
                <div class="flex items-center justify-center gap-2 py-8 text-sm text-slate-400">
                  <PhCircleNotch size="16" weight="bold" class="animate-spin" aria-hidden="true" />
                  Loading files…
                </div>
              </td>
            </tr>
            <tr v-else-if="filteredFiles.length === 0">
              <td colspan="9">
                <BaseEmptyState
                  :icon="PhFileCsv"
                  title="No CSV files found"
                  description="Files uploaded to the CSV library will show up here, filtered by the options above."
                />
              </td>
            </tr>
            <tr
              v-for="file in filteredFiles"
              :key="file.name"
              :class="isManualSort ? 'cursor-grab active:cursor-grabbing' : ''"
              :draggable="isManualSort && !isReordering"
              @dragstart="onRowDragStart(file.name)"
              @dragover="onRowDragOver($event, file.name)"
              @drop.prevent="onRowDrop(file.name)"
              @dragend="onRowDragEnd"
            >
              <td class="text-slate-200 font-medium">{{ isManualSort ? ':: ' : '' }}{{ file.name }}</td>
              <td>{{ file.schema_id }}</td>
              <td>{{ file.row_count }}</td>
              <td>{{ formatBytes(file.size_bytes) }}</td>
              <td>{{ formatDate(file.modified_at) }}</td>
              <td>
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
              <td>
                <span
                  v-if="isFileSelectedForActiveSlot(file)"
                  class="px-2 py-1 rounded text-xs font-semibold bg-brand-500/20 text-brand-300"
                >
                  Active {{ pipeline === 'late' ? schemaModality(file.schema_id).toUpperCase() : '' }}
                </span>
                <span v-else class="text-xs text-slate-500">-</span>
              </td>
              <td>
                <div v-if="compatibilityByName[file.name]?.checked">
                  <span
                    class="px-2 py-1 rounded text-xs font-semibold"
                    :class="compatibilityByName[file.name]?.isCompatible ? 'bg-success-500/20 text-success-300' : 'bg-danger-500/20 text-danger-300'"
                  >
                    {{ compatibilityByName[file.name]?.isCompatible ? 'Compatible' : 'Not Compatible' }}
                  </span>
                  <p class="text-[11px] text-slate-500 mt-1">{{ compatibilityByName[file.name]?.reason }}</p>
                </div>
                <span v-else class="text-xs text-slate-500">Not checked</span>
              </td>
              <td class="text-center">
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

    <BaseModal
      :model-value="previewModalOpen"
      title="CSV Preview"
      max-width="max-w-5xl"
      @update:model-value="(v) => !v && closePreviewModal()"
    >
      <p v-if="previewLoading" role="status" class="flex items-center gap-2 text-slate-400"><PhCircleNotch size="16" weight="bold" class="animate-spin" aria-hidden="true" />Loading preview…</p>
      <p v-else-if="previewError" role="alert" class="text-danger-300">{{ previewError }}</p>
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
    </BaseModal>

    <BaseModal
      :model-value="statsModalOpen"
      title="CSV Stats"
      max-width="max-w-3xl"
      @update:model-value="(v) => !v && closeStatsModal()"
    >
        <p v-if="statsLoading" role="status" class="flex items-center gap-2 text-slate-400"><PhCircleNotch size="16" weight="bold" class="animate-spin" aria-hidden="true" />Loading stats…</p>
        <p v-else-if="statsError" role="alert" class="text-danger-300">{{ statsError }}</p>
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
              <p v-else class="text-success-300">No health flags.</p>
            </div>
          </div>
          <div class="rounded border border-slate-800 p-3 bg-slate-950/40">
            <p class="text-slate-400 mb-1">Schema Mismatch Details</p>
            <p v-if="!(statsData.schema_mismatch_details?.missing_required_columns?.length || statsData.schema_mismatch_details?.notes?.length)" class="text-success-300">
              No mismatch details.
            </p>
            <div v-else class="space-y-2">
              <div v-if="statsData.schema_mismatch_details?.missing_required_columns?.length">
                <p class="text-danger-300 text-xs">Missing required columns</p>
                <p class="text-slate-200 text-xs">
                  {{ statsData.schema_mismatch_details.missing_required_columns.join(', ') }}
                </p>
              </div>
              <div v-if="statsData.schema_mismatch_details?.notes?.length">
                <p class="text-warning-300 text-xs">Notes</p>
                <p class="text-slate-200 text-xs">
                  {{ statsData.schema_mismatch_details.notes.join(' | ') }}
                </p>
              </div>
            </div>
          </div>
        </div>
    </BaseModal>

    <BaseModal
      :model-value="confirmDialogOpen"
      title="Confirm Permanent Delete"
      max-width="max-w-lg"
      @update:model-value="(v) => !v && closeConfirmDialog()"
    >
      <p class="mt-2 text-sm text-slate-300">
        Delete <span class="font-semibold text-slate-100">{{ confirmFileName }}</span> permanently. This cannot be undone.
      </p>
      <div class="mt-3">
        <label for="csv-confirm-delete-name" class="block text-xs text-slate-400 mb-1">Type exact file name to confirm</label>
        <input
          id="csv-confirm-delete-name"
          v-model="confirmTypedName"
          type="text"
          class="w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-slate-200"
          :placeholder="confirmFileName"
          autocomplete="off"
        />
      </div>

      <template #footer>
        <BaseBtn variant="secondary" @click="closeConfirmDialog">Cancel</BaseBtn>
        <BaseBtn variant="danger" :disabled="confirmTypedName !== confirmFileName" @click="confirmDialogSubmit">
          Delete Permanently
        </BaseBtn>
      </template>
    </BaseModal>

    <BaseModal
      :model-value="reviewDialogOpen"
      title="Save Review"
      max-width="max-w-lg"
      @update:model-value="(v) => !v && closeReviewDialog()"
    >
      <p class="mt-2 text-sm text-slate-300">
        Mark <span class="font-semibold text-slate-100">{{ reviewFileName }}</span> as
        <span class="font-semibold text-slate-100">{{ reviewLabel(reviewDecision) }}</span>.
      </p>
      <div class="mt-3">
        <label for="csv-review-notes" class="block text-xs text-slate-400 mb-1">Review notes (optional)</label>
        <textarea
          id="csv-review-notes"
          v-model="reviewNotes"
          rows="4"
          class="w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-slate-200"
          placeholder="Explain why this dataset was approved, flagged, or overridden."
        />
      </div>

      <template #footer>
        <BaseBtn variant="secondary" @click="closeReviewDialog">Cancel</BaseBtn>
        <BaseBtn variant="primary" :disabled="reviewingByName[reviewFileName]" @click="submitReviewDialog">
          {{ reviewingByName[reviewFileName] ? 'Saving...' : 'Save Review' }}
        </BaseBtn>
      </template>
    </BaseModal>
  </div>
</template>
