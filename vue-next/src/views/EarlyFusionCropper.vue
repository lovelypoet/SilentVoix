<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import BaseBtn from '../components/base/BaseBtn.vue'
import BaseCard from '../components/base/BaseCard.vue'
import BaseInput from '../components/base/BaseInput.vue'

const router = useRouter()

const selectedFile = ref(null)
const header = ref([])
const rows = ref([])
const parseError = ref('')
const loadStatus = ref('')

const trimStartMs = ref('')
const trimEndMs = ref('')
const maxDeltaMs = ref('500')
const requireSensorMatch = ref(true)
const exportLabel = ref('')
const exportNotes = ref('')

const timestampColumn = computed(() => {
  if (header.value.includes('timestamp_ms')) return 'timestamp_ms'
  return header.value.find((key) => key.toLowerCase().includes('timestamp')) || ''
})

const deltaColumn = computed(() => {
  if (header.value.includes('sensor_match_delta_ms')) return 'sensor_match_delta_ms'
  return ''
})

const gestureColumn = computed(() => {
  if (header.value.includes('gesture')) return 'gesture'
  if (header.value.includes('label')) return 'label'
  return ''
})

const sensorColumns = computed(() => header.value.filter((key) => key.startsWith('sensor_')))
const hasRightHandColumns = computed(() => header.value.some((key) => /^R_[xyz]/.test(key)))

const sourceStats = computed(() => {
  const tsKey = timestampColumn.value
  const deltaKey = deltaColumn.value
  if (!rows.value.length || !tsKey) {
    return {
      rowCount: 0,
      startMs: null,
      endMs: null,
      durationMs: 0,
      deltaWarnings: 0
    }
  }

  const timestamps = rows.value
    .map((row) => Number(row[tsKey]))
    .filter((value) => Number.isFinite(value))

  const deltas = deltaKey
    ? rows.value
      .map((row) => Math.abs(Number(row[deltaKey])))
      .filter((value) => Number.isFinite(value))
    : []

  const startMs = timestamps.length ? Math.min(...timestamps) : null
  const endMs = timestamps.length ? Math.max(...timestamps) : null
  const threshold = Number(maxDeltaMs.value)

  return {
    rowCount: rows.value.length,
    startMs,
    endMs,
    durationMs: startMs !== null && endMs !== null ? Math.max(0, endMs - startMs) : 0,
    deltaWarnings: Number.isFinite(threshold)
      ? deltas.filter((value) => value > threshold).length
      : 0
  }
})

const filteredRows = computed(() => {
  const tsKey = timestampColumn.value
  const deltaKey = deltaColumn.value
  const start = Number(trimStartMs.value)
  const end = Number(trimEndMs.value)
  const maxDelta = Number(maxDeltaMs.value)

  return rows.value.filter((row) => {
    const ts = Number(row[tsKey])
    if (!Number.isFinite(ts)) return false
    if (Number.isFinite(start) && ts < start) return false
    if (Number.isFinite(end) && ts > end) return false

    if (requireSensorMatch.value) {
      const source = String(row.capture_sensor_source || '').toLowerCase()
      if (!source || source === 'none') return false
    }

    if (deltaKey && Number.isFinite(maxDelta)) {
      const delta = Math.abs(Number(row[deltaKey]))
      if (!Number.isFinite(delta) || delta > maxDelta) return false
    }

    return true
  })
})

const filteredStats = computed(() => {
  const tsKey = timestampColumn.value
  const deltaKey = deltaColumn.value
  const timestamps = filteredRows.value
    .map((row) => Number(row[tsKey]))
    .filter((value) => Number.isFinite(value))
  const deltas = deltaKey
    ? filteredRows.value
      .map((row) => Math.abs(Number(row[deltaKey])))
      .filter((value) => Number.isFinite(value))
    : []

  return {
    rowCount: filteredRows.value.length,
    droppedRows: Math.max(0, rows.value.length - filteredRows.value.length),
    startMs: timestamps.length ? Math.min(...timestamps) : null,
    endMs: timestamps.length ? Math.max(...timestamps) : null,
    avgDeltaMs: deltas.length ? Number((deltas.reduce((sum, value) => sum + value, 0) / deltas.length).toFixed(2)) : null,
    maxDeltaMs: deltas.length ? Math.max(...deltas) : null
  }
})

const inferredSchemaId = computed(() => {
  if (!rows.value.length) return '--'
  return hasRightHandColumns.value ? 'fusion_dual' : 'fusion_single'
})

const suggestedExportName = computed(() => {
  if (!selectedFile.value) return 'fusion_processed.csv'
  const base = selectedFile.value.name.replace(/\.csv$/i, '')
  const label = (exportLabel.value || 'cropped').trim().replace(/\s+/g, '_')
  return `${base}_${label}.csv`
})

const metadataPayload = computed(() => ({
  source_file: selectedFile.value?.name || null,
  schema_id: inferredSchemaId.value,
  timestamp_column: timestampColumn.value || null,
  sensor_columns: sensorColumns.value,
  crop_rules: {
    trim_start_ms: trimStartMs.value === '' ? null : Number(trimStartMs.value),
    trim_end_ms: trimEndMs.value === '' ? null : Number(trimEndMs.value),
    max_abs_sensor_delta_ms: maxDeltaMs.value === '' ? null : Number(maxDeltaMs.value),
    require_sensor_match: requireSensorMatch.value
  },
  source_summary: sourceStats.value,
  processed_summary: filteredStats.value,
  notes: exportNotes.value || ''
}))

function parseCsv(text) {
  const result = []
  let row = []
  let cell = ''
  let inQuotes = false

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i]
    const next = text[i + 1]

    if (char === '"') {
      if (inQuotes && next === '"') {
        cell += '"'
        i += 1
      } else {
        inQuotes = !inQuotes
      }
      continue
    }

    if (char === ',' && !inQuotes) {
      row.push(cell)
      cell = ''
      continue
    }

    if ((char === '\n' || char === '\r') && !inQuotes) {
      if (char === '\r' && next === '\n') i += 1
      row.push(cell)
      if (row.some((value) => value !== '')) result.push(row)
      row = []
      cell = ''
      continue
    }

    cell += char
  }

  if (cell.length > 0 || row.length > 0) {
    row.push(cell)
    if (row.some((value) => value !== '')) result.push(row)
  }

  return result
}

function csvEscape(value) {
  const text = value === null || value === undefined ? '' : String(value)
  if (text.includes(',') || text.includes('"') || text.includes('\n')) {
    return `"${text.replace(/"/g, '""')}"`
  }
  return text
}

function formatMs(value) {
  return Number.isFinite(value) ? `${value.toLocaleString()} ms` : '--'
}

function downloadBlob(filename, content, type) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

function initializeCropBounds(parsedRows) {
  const tsKey = header.value.includes('timestamp_ms')
    ? 'timestamp_ms'
    : header.value.find((key) => key.toLowerCase().includes('timestamp'))

  if (!tsKey) return

  const timestamps = parsedRows
    .map((row) => Number(row[tsKey]))
    .filter((value) => Number.isFinite(value))

  if (!timestamps.length) return

  trimStartMs.value = String(Math.min(...timestamps))
  trimEndMs.value = String(Math.max(...timestamps))
}

async function handleFileChange(event) {
  const file = event.target.files?.[0]
  selectedFile.value = file || null
  parseError.value = ''
  loadStatus.value = ''
  header.value = []
  rows.value = []

  if (!file) return

  try {
    const text = await file.text()
    const matrix = parseCsv(text)
    if (matrix.length < 2) {
      throw new Error('CSV is empty or missing data rows.')
    }

    const parsedHeader = matrix[0].map((value) => value.trim())
    const dataRows = matrix.slice(1).map((values) => {
      const record = {}
      parsedHeader.forEach((key, index) => {
        record[key] = values[index] ?? ''
      })
      return record
    })

    header.value = parsedHeader
    rows.value = dataRows
    exportLabel.value = exportLabel.value || 'processed'
    initializeCropBounds(dataRows)
    loadStatus.value = `Loaded ${file.name} with ${dataRows.length} rows.`
  } catch (error) {
    parseError.value = error instanceof Error ? error.message : 'Failed to parse CSV.'
  }
}

function exportProcessedCsv() {
  if (!header.value.length || !filteredRows.value.length) return
  const csvRows = [
    header.value.map(csvEscape).join(','),
    ...filteredRows.value.map((row) => header.value.map((key) => csvEscape(row[key])).join(','))
  ]
  downloadBlob(suggestedExportName.value, `${csvRows.join('\n')}\n`, 'text/csv')
}

function exportMetadata() {
  downloadBlob(
    suggestedExportName.value.replace(/\.csv$/i, '_metadata.json'),
    `${JSON.stringify(metadataPayload.value, null, 2)}\n`,
    'application/json'
  )
}

function resetAll() {
  selectedFile.value = null
  header.value = []
  rows.value = []
  parseError.value = ''
  loadStatus.value = ''
  trimStartMs.value = ''
  trimEndMs.value = ''
  maxDeltaMs.value = '500'
  requireSensorMatch.value = true
  exportLabel.value = ''
  exportNotes.value = ''
}

function goBack() {
  router.push({ path: '/fusion', query: { tab: 'early' } })
}
</script>

<template>
  <div class="max-w-7xl mx-auto space-y-6">
    <section class="mb-2 grid grid-cols-[auto_1fr] md:grid-cols-3 items-center gap-3">
      <div class="flex justify-start">
        <BaseBtn variant="secondary" title="Return to fusion workspace" class="px-3" @click="goBack">
          &larr;
        </BaseBtn>
      </div>
      <div class="text-left md:text-center">
        <h1 class="text-2xl md:text-3xl font-bold text-white mb-2">Early Fusion Cropper</h1>
        <p class="text-slate-400">Review a captured fusion CSV, trim noisy rows, and export a processed dataset plus crop metadata.</p>
      </div>
      <div class="hidden md:block"></div>
    </section>

    <BaseCard>
      <div class="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <div class="space-y-4">
          <div>
            <p class="text-sm uppercase tracking-[0.2em] text-teal-300">Source File</p>
            <p class="text-sm text-slate-400 mt-1">Load a `cv_sensor_*.csv` export from the early-fusion capture flow.</p>
          </div>
          <input
            type="file"
            accept=".csv,text/csv"
            class="block w-full rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-slate-200 file:mr-4 file:rounded-md file:border-0 file:bg-teal-500 file:px-4 file:py-2 file:text-white"
            @change="handleFileChange"
          />
          <p v-if="loadStatus" class="text-sm text-emerald-300">{{ loadStatus }}</p>
          <p v-if="parseError" class="text-sm text-rose-300">{{ parseError }}</p>
        </div>

        <div class="grid gap-3 sm:grid-cols-2">
          <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
            <p class="text-xs uppercase tracking-[0.2em] text-slate-500">Schema</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ inferredSchemaId }}</p>
          </div>
          <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
            <p class="text-xs uppercase tracking-[0.2em] text-slate-500">Sensor Columns</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ sensorColumns.length }}</p>
          </div>
          <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
            <p class="text-xs uppercase tracking-[0.2em] text-slate-500">Raw Rows</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ sourceStats.rowCount }}</p>
          </div>
          <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
            <p class="text-xs uppercase tracking-[0.2em] text-slate-500">Delta Warnings</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ sourceStats.deltaWarnings }}</p>
          </div>
        </div>
      </div>
    </BaseCard>

    <BaseCard>
      <div class="flex flex-col gap-5">
        <div>
          <p class="text-sm uppercase tracking-[0.2em] text-teal-300">Crop Rules</p>
          <p class="text-sm text-slate-400 mt-1">This first pass trims by timestamp window and sensor-match quality. It is designed to separate raw capture from processed fusion data.</p>
        </div>

        <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <BaseInput v-model="trimStartMs" type="number" label="Trim Start (ms)" placeholder="Start timestamp" />
          <BaseInput v-model="trimEndMs" type="number" label="Trim End (ms)" placeholder="End timestamp" />
          <BaseInput v-model="maxDeltaMs" type="number" label="Max |Sensor Delta| (ms)" placeholder="500" />
          <BaseInput v-model="exportLabel" label="Export Label" placeholder="processed" />
        </div>

        <div class="flex flex-wrap items-center gap-3 text-sm text-slate-300">
          <label class="inline-flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-950/60 px-4 py-2">
            <input v-model="requireSensorMatch" type="checkbox" class="accent-teal-400" />
            Require `capture_sensor_source !== none`
          </label>
          <span class="rounded-lg border border-slate-800 bg-slate-950/60 px-4 py-2">
            Source window: {{ formatMs(sourceStats.startMs) }} -> {{ formatMs(sourceStats.endMs) }}
          </span>
          <span class="rounded-lg border border-slate-800 bg-slate-950/60 px-4 py-2">
            Duration: {{ formatMs(sourceStats.durationMs) }}
          </span>
        </div>

        <BaseInput v-model="exportNotes" label="Processing Notes" placeholder="Optional notes about sync quality, rejection reasons, or review decisions" />
      </div>
    </BaseCard>

    <div class="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
      <BaseCard>
        <div class="space-y-4">
          <div>
            <p class="text-sm uppercase tracking-[0.2em] text-teal-300">Processed Summary</p>
            <p class="text-sm text-slate-400 mt-1">Use this as the acceptance gate before sending the dataset to CSV Library or external training.</p>
          </div>

          <div class="grid gap-3 sm:grid-cols-2">
            <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
              <p class="text-xs uppercase tracking-[0.2em] text-slate-500">Kept Rows</p>
              <p class="mt-2 text-lg font-semibold text-white">{{ filteredStats.rowCount }}</p>
            </div>
            <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
              <p class="text-xs uppercase tracking-[0.2em] text-slate-500">Dropped Rows</p>
              <p class="mt-2 text-lg font-semibold text-white">{{ filteredStats.droppedRows }}</p>
            </div>
            <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
              <p class="text-xs uppercase tracking-[0.2em] text-slate-500">Avg |Delta|</p>
              <p class="mt-2 text-lg font-semibold text-white">{{ formatMs(filteredStats.avgDeltaMs) }}</p>
            </div>
            <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
              <p class="text-xs uppercase tracking-[0.2em] text-slate-500">Max |Delta|</p>
              <p class="mt-2 text-lg font-semibold text-white">{{ formatMs(filteredStats.maxDeltaMs) }}</p>
            </div>
          </div>

          <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-sm text-slate-300">
            <p>Processed window: {{ formatMs(filteredStats.startMs) }} -> {{ formatMs(filteredStats.endMs) }}</p>
            <p class="mt-2">Gesture column: <span class="text-white">{{ gestureColumn || '--' }}</span></p>
            <p class="mt-2">Timestamp column: <span class="text-white">{{ timestampColumn || '--' }}</span></p>
            <p class="mt-2">Delta column: <span class="text-white">{{ deltaColumn || '--' }}</span></p>
          </div>

          <div class="flex flex-wrap gap-3">
            <BaseBtn variant="primary" :disabled="!filteredRows.length" @click="exportProcessedCsv">Download Processed CSV</BaseBtn>
            <BaseBtn variant="secondary" :disabled="!filteredRows.length" @click="exportMetadata">Download Metadata</BaseBtn>
            <BaseBtn variant="danger" @click="resetAll">Reset</BaseBtn>
          </div>
        </div>
      </BaseCard>

      <BaseCard>
        <div class="space-y-4">
          <div>
            <p class="text-sm uppercase tracking-[0.2em] text-teal-300">Preview</p>
            <p class="text-sm text-slate-400 mt-1">First 12 processed rows after cropping. This is intentionally lightweight; the next step would be a timeline graph.</p>
          </div>

          <div v-if="!filteredRows.length" class="rounded-xl border border-dashed border-slate-800 bg-slate-950/40 p-8 text-center text-slate-500">
            No processed rows yet. Load a file and adjust crop rules.
          </div>

          <div v-else class="overflow-x-auto rounded-xl border border-slate-800">
            <table class="min-w-full text-sm">
              <thead class="bg-slate-950/80 text-slate-300">
                <tr>
                  <th v-for="key in header.slice(0, 10)" :key="`head-${key}`" class="px-3 py-2 text-left font-medium">{{ key }}</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(row, index) in filteredRows.slice(0, 12)"
                  :key="`row-${index}`"
                  class="border-t border-slate-900 bg-slate-950/30 text-slate-300"
                >
                  <td v-for="key in header.slice(0, 10)" :key="`cell-${index}-${key}`" class="px-3 py-2">
                    {{ row[key] }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </BaseCard>
    </div>
  </div>
</template>
