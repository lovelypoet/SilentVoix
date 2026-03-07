<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import BaseCard from '../components/base/BaseCard.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import BaseEllipsisMenu from '../components/base/BaseEllipsisMenu.vue'
import { useToast } from 'primevue/usetoast'
import api from '../services/api'

const models = ref([])
const activeModelId = ref(null)
const isLoading = ref(false)
const error = ref('')
const actionLoading = ref({})
const runtimeCheckState = ref({})
const deleteConfirmOpen = ref(false)
const deleteConfirmModelId = ref('')
const deleteConfirmModelName = ref('')
const deleteConfirmTypedName = ref('')
const toast = useToast()
const searchQuery = ref('')
const familyFilter = ref('all')
const formatFilter = ref('all')
const statusFilter = ref('all')
const sortKey = ref('manual')
const sortDir = ref('desc')
const pageSize = ref(10)
const currentPage = ref(1)
const dragModelId = ref(null)
const isReordering = ref(false)

const families = computed(() => {
  const values = new Set(models.value.map((m) => m?.metadata?.model_family).filter(Boolean))
  return [...values].sort((a, b) => a.localeCompare(b))
})

const formats = computed(() => {
  const values = new Set(models.value.map((m) => m?.metadata?.export_format).filter(Boolean))
  return [...values].sort((a, b) => a.localeCompare(b))
})

const metricAsNumber = (value) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : -1
}

const inputDimAsNumber = (value) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : -1
}

const filteredModels = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return models.value.filter((model) => {
    const name = String(model?.display_name || model?.id || '').toLowerCase()
    const file = String(model?.model_file_name || '').toLowerCase()
    const family = String(model?.metadata?.model_family || '')
    const format = String(model?.metadata?.export_format || '')
    const matchesQuery = !q || name.includes(q) || file.includes(q)
    const matchesFamily = familyFilter.value === 'all' || family === familyFilter.value
    const matchesFormat = formatFilter.value === 'all' || format === formatFilter.value
    const matchesStatus = statusFilter.value === 'all'
      || (statusFilter.value === 'active' && isActive(model.id))
      || (statusFilter.value === 'inactive' && !isActive(model.id))
    return matchesQuery && matchesFamily && matchesFormat && matchesStatus
  })
})

const isManualSort = computed(() => sortKey.value === 'manual')

const sortedModels = computed(() => {
  if (isManualSort.value) {
    return filteredModels.value
  }
  const dir = sortDir.value === 'asc' ? 1 : -1
  const withIndex = filteredModels.value.map((model, idx) => ({ model, idx }))
  withIndex.sort((a, b) => {
    const ma = a.model
    const mb = b.model
    let delta = 0
    if (sortKey.value === 'created_at') {
      delta = new Date(ma?.created_at || 0).getTime() - new Date(mb?.created_at || 0).getTime()
    } else if (sortKey.value === 'name') {
      delta = String(ma?.display_name || ma?.id || '').localeCompare(String(mb?.display_name || mb?.id || ''))
    } else if (sortKey.value === 'family') {
      delta = String(ma?.metadata?.model_family || '').localeCompare(String(mb?.metadata?.model_family || ''))
    } else if (sortKey.value === 'format') {
      delta = String(ma?.metadata?.export_format || '').localeCompare(String(mb?.metadata?.export_format || ''))
    } else if (sortKey.value === 'input_dim') {
      delta = inputDimAsNumber(ma?.input_dim) - inputDimAsNumber(mb?.input_dim)
    } else if (sortKey.value === 'precision') {
      delta = metricAsNumber(ma?.metadata?.precision) - metricAsNumber(mb?.metadata?.precision)
    } else if (sortKey.value === 'recall') {
      delta = metricAsNumber(ma?.metadata?.recall) - metricAsNumber(mb?.metadata?.recall)
    } else if (sortKey.value === 'f1') {
      delta = metricAsNumber(ma?.metadata?.f1) - metricAsNumber(mb?.metadata?.f1)
    }
    if (delta === 0) {
      return a.idx - b.idx
    }
    return delta * dir
  })
  return withIndex.map((entry) => entry.model)
})

const totalPages = computed(() => Math.max(1, Math.ceil(sortedModels.value.length / pageSize.value)))

const pagedModels = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return sortedModels.value.slice(start, start + pageSize.value)
})

const formatDate = (value) => {
  if (!value) return '--'
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? '--' : d.toLocaleString()
}

const displayModelName = (model) => String(model?.display_name || model?.id || '')

const setActionLoading = (modelId, loading) => {
  actionLoading.value = { ...actionLoading.value, [modelId]: loading }
}

const isActionLoading = (modelId) => Boolean(actionLoading.value?.[modelId])
const runtimeCheckFor = (modelId) => runtimeCheckState.value?.[modelId] || null
const runtimeStatusFor = (modelId) => {
  const check = runtimeCheckFor(modelId)
  if (!check) return 'untested'
  return check.ok ? 'pass' : 'fail'
}

const hydrateRuntimeChecks = (rows) => {
  const next = {}
  for (const model of rows) {
    const status = model?.runtime_status
    if (!status) continue
    const state = String(status.state || '').toLowerCase()
    if (state === 'pass') {
      next[model.id] = {
        ok: true,
        message: status.message || `OK: in ${status.input_dim ?? '--'} -> out ${status.output_dim ?? '--'}`
      }
    } else if (state === 'fail') {
      next[model.id] = {
        ok: false,
        message: status.message || 'Runtime check failed.'
      }
    }
  }
  runtimeCheckState.value = next
}

const showRuntimeStatusToast = (model) => {
  const check = runtimeCheckFor(model.id)
  if (!check) {
    toast.add({ severity: 'warn', summary: 'Untested Model', detail: 'This model has not been evaluated by the runtime check yet. Run it from the actions menu.', life: 4000 })
  } else if (check.ok) {
    toast.add({ severity: 'success', summary: 'Runtime Check Passed', detail: check.message, life: 4000 })
  } else {
    toast.add({ severity: 'error', summary: 'Runtime Check Failed', detail: check.message, life: 6000 })
  }
}

const isActive = (modelId) => activeModelId.value === modelId

const fetchModels = async () => {
  isLoading.value = true
  error.value = ''
  try {
    const res = await api.playground.listModels()
    const rows = Array.isArray(res?.models) ? res.models : []
    models.value = rows
    activeModelId.value = res?.active_model_id || null
    hydrateRuntimeChecks(rows)
  } catch (e) {
    error.value = e?.response?.data?.detail || 'Failed to load model library.'
  } finally {
    isLoading.value = false
  }
}

const activateModel = async (modelId) => {
  setActionLoading(modelId, true)
  error.value = ''
  try {
    const res = await api.playground.activateModel(modelId)
    activeModelId.value = res?.active_model_id || modelId
  } catch (e) {
    error.value = e?.response?.data?.detail || 'Failed to activate model.'
  } finally {
    setActionLoading(modelId, false)
  }
}

const runtimeCheckModel = async (modelId) => {
  setActionLoading(modelId, true)
  error.value = ''
  runtimeCheckState.value = { ...runtimeCheckState.value, [modelId]: null }
  try {
    const res = await api.playground.runtimeCheckModel(modelId)
    runtimeCheckState.value = {
      ...runtimeCheckState.value,
      [modelId]: {
        ok: true,
        message: `OK: in ${res?.input_dim ?? '--'} -> out ${res?.output_dim ?? '--'}`
      }
    }
    toast.add({ severity: 'success', summary: 'Runtime Check Passed', detail: `Checked successfully: in ${res?.input_dim ?? '--'} -> out ${res?.output_dim ?? '--'}`, life: 3000 })
  } catch (e) {
    const errDetail = e?.response?.data?.detail || 'Runtime check failed.'
    runtimeCheckState.value = {
      ...runtimeCheckState.value,
      [modelId]: {
        ok: false,
        message: errDetail
      }
    }
    toast.add({ severity: 'error', summary: 'Runtime Check Failed', detail: errDetail, life: 5000 })
  } finally {
    setActionLoading(modelId, false)
  }
}

const downloadArtifact = async (model, kind) => {
  const modelId = model?.id
  if (!modelId) return
  setActionLoading(modelId, true)
  error.value = ''
  try {
    const blob = await api.playground.downloadModelArtifact(modelId, kind)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const baseName = (model.display_name || modelId).replace(/\s+/g, '_')
    const ext = kind === 'metadata' ? 'json' : (model.model_file_name?.split('.').pop() || 'bin')
    a.download = `${baseName}.${ext}`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    error.value = e?.response?.data?.detail || `Failed to download ${kind}.`
  } finally {
    setActionLoading(modelId, false)
  }
}

const openDeleteConfirm = (model) => {
  deleteConfirmModelId.value = String(model?.id || '')
  deleteConfirmModelName.value = displayModelName(model)
  deleteConfirmTypedName.value = ''
  deleteConfirmOpen.value = true
}

const closeDeleteConfirm = () => {
  deleteConfirmOpen.value = false
  deleteConfirmModelId.value = ''
  deleteConfirmModelName.value = ''
  deleteConfirmTypedName.value = ''
}

const deleteModel = async (modelId) => {
  setActionLoading(modelId, true)
  error.value = ''
  try {
    const res = await api.playground.deleteModel(modelId)
    models.value = models.value.filter((m) => m.id !== modelId)
    activeModelId.value = res?.active_model_id || null
    toast.add({ severity: 'info', summary: 'Deleted', detail: 'Model deleted successfully.', life: 3000 })
  } catch (e) {
    error.value = e?.response?.data?.detail || 'Failed to delete model.'
    toast.add({ severity: 'error', summary: 'Delete Failed', detail: error.value, life: 4000 })
  } finally {
    setActionLoading(modelId, false)
  }
}

const goToPage = (value) => {
  currentPage.value = Math.min(Math.max(1, value), totalPages.value)
}

const reorderSubset = (allIds, visibleIds, nextVisibleIds) => {
  const visibleSet = new Set(visibleIds)
  const queue = [...nextVisibleIds]
  return allIds.map((id) => (visibleSet.has(id) ? queue.shift() : id))
}

const persistModelOrder = async (orderedIds) => {
  isReordering.value = true
  error.value = ''
  try {
    const res = await api.playground.reorderModels(orderedIds)
    const rows = Array.isArray(res?.models) ? res.models : []
    if (rows.length) {
      models.value = rows
      activeModelId.value = res?.active_model_id || activeModelId.value
      hydrateRuntimeChecks(rows)
    }
  } catch (e) {
    error.value = e?.response?.data?.detail || 'Failed to reorder models.'
    await fetchModels()
  } finally {
    isReordering.value = false
  }
}

const onRowDragStart = (modelId) => {
  if (!isManualSort.value || isReordering.value) return
  dragModelId.value = modelId
}

const onRowDragOver = (event, modelId) => {
  if (!isManualSort.value || isReordering.value || !dragModelId.value || dragModelId.value === modelId) return
  event.preventDefault()
}

const onRowDrop = async (modelId) => {
  if (!isManualSort.value || isReordering.value || !dragModelId.value || dragModelId.value === modelId) {
    dragModelId.value = null
    return
  }

  const visibleIds = pagedModels.value.map((model) => model.id)
  const fromIndex = visibleIds.indexOf(dragModelId.value)
  const toIndex = visibleIds.indexOf(modelId)
  if (fromIndex < 0 || toIndex < 0) {
    dragModelId.value = null
    return
  }

  const nextVisibleIds = [...visibleIds]
  const [moved] = nextVisibleIds.splice(fromIndex, 1)
  nextVisibleIds.splice(toIndex, 0, moved)

  const allIds = models.value.map((model) => model.id)
  const mergedIds = reorderSubset(allIds, visibleIds, nextVisibleIds)
  const byId = Object.fromEntries(models.value.map((model) => [model.id, model]))
  models.value = mergedIds.map((id) => byId[id]).filter(Boolean)
  dragModelId.value = null
  await persistModelOrder(mergedIds)
}

const onRowDragEnd = () => {
  dragModelId.value = null
}

const activateFromMenu = async (modelId, close) => {
  await activateModel(modelId)
  close()
}

const downloadFromMenu = async (model, kind, close) => {
  await downloadArtifact(model, kind)
  close()
}

const runtimeCheckFromMenu = async (modelId, close) => {
  await runtimeCheckModel(modelId)
  close()
}

const requestDeleteFromMenu = (modelId, close) => {
  const model = models.value.find((item) => item.id === modelId)
  if (!model) return
  openDeleteConfirm(model)
  close()
}

const submitDeleteConfirm = async () => {
  const modelId = deleteConfirmModelId.value
  const modelName = deleteConfirmModelName.value
  if (!modelId || !modelName) {
    closeDeleteConfirm()
    return
  }
  if (deleteConfirmTypedName.value !== modelName) {
    toast.add({
      severity: 'warn',
      summary: 'Name Mismatch',
      detail: 'Type the exact model name to confirm delete.',
      life: 3200
    })
    return
  }
  closeDeleteConfirm()
  await deleteModel(modelId)
}

watch([searchQuery, familyFilter, formatFilter, statusFilter, sortKey, sortDir, pageSize], () => {
  currentPage.value = 1
})

watch(sortedModels, () => {
  if (currentPage.value > totalPages.value) {
    currentPage.value = totalPages.value
  }
})

onMounted(() => {
  void fetchModels()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
      <div>
        <h1 class="text-3xl font-bold text-white">Model Library</h1>
        <p class="text-slate-400 text-sm">Manage uploaded inference models for Realtime AI Playground.</p>
      </div>
      <div class="flex gap-2">
        <BaseBtn variant="secondary" :disabled="isLoading" @click="fetchModels">
          {{ isLoading ? 'Refreshing...' : 'Refresh' }}
        </BaseBtn>
      </div>
    </div>

    <BaseCard>
      <p v-if="error" class="text-red-300 text-sm">{{ error }}</p>
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3 mb-4">
        <label class="block">
          <span class="text-xs text-slate-400">Search</span>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Name or filename..."
            class="mt-1 w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white"
          >
        </label>
        <label class="block">
          <span class="text-xs text-slate-400">Family</span>
          <select v-model="familyFilter" class="mt-1 w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white">
            <option value="all">All</option>
            <option v-for="family in families" :key="family" :value="family">{{ family }}</option>
          </select>
        </label>
        <label class="block">
          <span class="text-xs text-slate-400">Format</span>
          <select v-model="formatFilter" class="mt-1 w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white">
            <option value="all">All</option>
            <option v-for="format in formats" :key="format" :value="format">{{ format }}</option>
          </select>
        </label>
        <label class="block">
          <span class="text-xs text-slate-400">Status</span>
          <select v-model="statusFilter" class="mt-1 w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white">
            <option value="all">All</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </label>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3 mb-4">
        <label class="block">
          <span class="text-xs text-slate-400">Sort by</span>
          <select v-model="sortKey" class="mt-1 w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white">
            <option value="manual">Manual Order</option>
            <option value="created_at">Created Date</option>
            <option value="name">Name</option>
            <option value="family">Family</option>
            <option value="format">Format</option>
            <option value="input_dim">Input Dim</option>
            <option value="precision">Precision</option>
            <option value="recall">Recall</option>
            <option value="f1">F1</option>
          </select>
        </label>
        <label class="block">
          <span class="text-xs text-slate-400">Direction</span>
          <select v-model="sortDir" :disabled="isManualSort" class="mt-1 w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white disabled:opacity-50">
            <option value="desc">Descending</option>
            <option value="asc">Ascending</option>
          </select>
        </label>
        <label class="block">
          <span class="text-xs text-slate-400">Rows per page</span>
          <select v-model.number="pageSize" class="mt-1 w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white">
            <option :value="5">5</option>
            <option :value="10">10</option>
            <option :value="20">20</option>
            <option :value="50">50</option>
          </select>
        </label>
        <div class="flex items-end">
          <p class="text-slate-400 text-sm">
            Showing {{ pagedModels.length }} of {{ sortedModels.length }} filtered model(s)
          </p>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-slate-400 border-b border-slate-800">
              <th class="py-2 pr-3">Model</th>
              <th class="py-2 pr-3">Family</th>
              <th class="py-2 pr-3">Format</th>
              <th class="py-2 pr-3">Input Dim</th>
              <th class="py-2 pr-3">P / R / F1</th>
              <th class="py-2 pr-3">Created</th>
              <th class="py-2 pr-3">Status</th>
              <th class="py-2 px-3 text-center">Runtime</th>
              <th class="py-2 px-3 text-center">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="isLoading">
              <td colspan="9" class="py-4 text-slate-400">Loading models...</td>
            </tr>
            <tr v-else-if="sortedModels.length === 0">
              <td colspan="9" class="py-4 text-slate-400">No models found. Upload one in Realtime AI Playground.</td>
            </tr>
            <tr
              v-for="model in pagedModels"
              :key="model.id"
              class="border-b border-slate-900/70"
              :class="isManualSort ? 'cursor-grab active:cursor-grabbing' : ''"
              :draggable="isManualSort && !isReordering"
              @dragstart="onRowDragStart(model.id)"
              @dragover="onRowDragOver($event, model.id)"
              @drop.prevent="onRowDrop(model.id)"
              @dragend="onRowDragEnd"
            >
              <td class="py-2 pr-3 text-slate-200">
                <p class="font-medium">{{ isManualSort ? ':: ' : '' }}{{ model.display_name || model.id }}</p>
                <p class="text-xs text-slate-500">{{ model.model_file_name }}</p>
              </td>
              <td class="py-2 pr-3 text-slate-300">{{ model.metadata?.model_family || '--' }}</td>
              <td class="py-2 pr-3 text-slate-300">{{ model.metadata?.export_format || '--' }}</td>
              <td class="py-2 pr-3 text-slate-300">{{ model.input_dim || '--' }}</td>
              <td class="py-2 pr-3 text-slate-300">
                {{ model.metadata?.precision ?? '--' }} / {{ model.metadata?.recall ?? '--' }} / {{ model.metadata?.f1 ?? '--' }}
              </td>
              <td class="py-2 pr-3 text-slate-300">{{ formatDate(model.created_at) }}</td>
              <td class="py-2 pr-3">
                <span
                  class="px-2 py-1 rounded text-xs font-semibold"
                  :class="isActive(model.id) ? 'bg-cyan-500/20 text-cyan-300' : 'bg-slate-700/40 text-slate-300'"
                >
                  {{ isActive(model.id) ? 'Active' : 'Inactive' }}
                </span>
              </td>
              <td class="py-2 px-3 align-middle text-center">
                <button
                  type="button"
                  class="mx-auto w-3.5 h-3.5 rounded-full shrink-0 transition-colors shadow-sm outline-none ring-2 ring-transparent focus-visible:ring-slate-400"
                  :class="
                    runtimeStatusFor(model.id) === 'pass'
                      ? 'bg-emerald-500 hover:bg-emerald-400 shadow-emerald-500/20'
                      : runtimeStatusFor(model.id) === 'fail'
                        ? 'bg-rose-500 hover:bg-rose-400 shadow-rose-500/20'
                        : 'bg-amber-400 hover:bg-amber-300 shadow-amber-400/20'
                  "
                  title="Click to view runtime status details"
                  @click="showRuntimeStatusToast(model)"
                ></button>
              </td>
              <td class="py-2 px-3 text-center">
                <BaseEllipsisMenu :disabled="isActionLoading(model.id)">
                  <template #menu="{ close }">
                    <button
                      class="w-full text-left px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50"
                      :disabled="isActionLoading(model.id) || isActive(model.id)"
                      @click="activateFromMenu(model.id, close)"
                    >
                      Activate
                    </button>
                    <button
                      class="w-full text-left px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50"
                      :disabled="isActionLoading(model.id)"
                      @click="downloadFromMenu(model, 'model', close)"
                    >
                      Download Model
                    </button>
                    <button
                      class="w-full text-left px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50"
                      :disabled="isActionLoading(model.id)"
                      @click="downloadFromMenu(model, 'metadata', close)"
                    >
                      Download Metadata
                    </button>
                    <button
                      class="w-full text-left px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50"
                      :disabled="isActionLoading(model.id)"
                      @click="runtimeCheckFromMenu(model.id, close)"
                    >
                      Runtime Check
                    </button>
                    <button
                      class="w-full text-left px-3 py-2 text-sm text-red-300 hover:bg-red-500/10 disabled:opacity-50"
                      :disabled="isActionLoading(model.id)"
                      @click="requestDeleteFromMenu(model.id, close)"
                    >
                      Delete
                    </button>
                  </template>
                </BaseEllipsisMenu>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="flex items-center justify-between gap-3 mt-4">
        <p class="text-xs text-slate-500">Page {{ currentPage }} / {{ totalPages }}</p>
        <div class="flex gap-2">
          <BaseBtn variant="secondary" class="!px-3 !py-1.5 text-xs" :disabled="currentPage <= 1" @click="goToPage(currentPage - 1)">
            Prev
          </BaseBtn>
          <BaseBtn variant="secondary" class="!px-3 !py-1.5 text-xs" :disabled="currentPage >= totalPages" @click="goToPage(currentPage + 1)">
            Next
          </BaseBtn>
        </div>
      </div>
    </BaseCard>

    <div v-if="deleteConfirmOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4" @click.self="closeDeleteConfirm">
      <div class="w-full max-w-lg rounded-xl border border-slate-700 bg-slate-950 p-5 shadow-2xl">
        <h3 class="text-lg font-semibold text-white">Confirm Permanent Delete</h3>
        <p class="mt-2 text-sm text-slate-300">
          Delete <span class="font-semibold text-white">{{ deleteConfirmModelName }}</span> permanently. This cannot be undone.
        </p>
        <div class="mt-3">
          <label class="block text-xs text-slate-400 mb-1">Type exact model name to confirm</label>
          <input
            v-model="deleteConfirmTypedName"
            type="text"
            class="w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-slate-200"
            :placeholder="deleteConfirmModelName"
          >
        </div>
        <div class="mt-5 flex justify-end gap-2">
          <BaseBtn variant="secondary" @click="closeDeleteConfirm">Cancel</BaseBtn>
          <BaseBtn
            variant="danger"
            :disabled="isActionLoading(deleteConfirmModelId)"
            @click="submitDeleteConfirm"
          >
            {{ isActionLoading(deleteConfirmModelId) ? 'Deleting...' : 'Delete Permanently' }}
          </BaseBtn>
        </div>
      </div>
    </div>
  </div>
</template>
