<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import BaseBtn from '../components/base/BaseBtn.vue'
import BaseCard from '../components/base/BaseCard.vue'
import BaseInput from '../components/base/BaseInput.vue'
import api from '../services/api'

const router = useRouter()

const selectedFile = ref(null)
const selectedVideoFile = ref(null)
const rawCsvText = ref('')
const header = ref([])
const rows = ref([])
const parseError = ref('')
const loadStatus = ref('')
const analysisLoading = ref(false)
const analysisError = ref('')
const analysisJob = ref(null)
const processedCsvText = ref('')
const processedRowsPreview = ref([])
const workerMetadata = ref(null)
const saveLoading = ref(false)
const saveError = ref('')
const saveResult = ref(null)

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

const validationSummary = computed(() => workerMetadata.value?.validation || null)
const opencvSummary = computed(() => workerMetadata.value?.opencv_summary || null)
const effectiveProcessedStats = computed(() => workerMetadata.value?.processed_summary || filteredStats.value)
const effectiveSourceStats = computed(() => workerMetadata.value?.source_summary || sourceStats.value)
const effectivePreviewRows = computed(() => processedRowsPreview.value.length ? processedRowsPreview.value : filteredRows.value.slice(0, 20))
const metadataPayload = computed(() => workerMetadata.value || ({
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

function clearAnalysisResult() {
  analysisError.value = ''
  analysisJob.value = null
  processedCsvText.value = ''
  processedRowsPreview.value = []
  workerMetadata.value = null
  saveLoading.value = false
  saveError.value = ''
  saveResult.value = null
}

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
  rawCsvText.value = ''
  header.value = []
  rows.value = []
  clearAnalysisResult()

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

    rawCsvText.value = text
    header.value = parsedHeader
    rows.value = dataRows
    exportLabel.value = exportLabel.value || 'processed'
    initializeCropBounds(dataRows)
    loadStatus.value = `Loaded ${file.name} with ${dataRows.length} rows.`
  } catch (error) {
    parseError.value = error instanceof Error ? error.message : 'Failed to parse CSV.'
  }
}

function handleVideoFileChange(event) {
  const file = event.target.files?.[0]
  selectedVideoFile.value = file || null
  if (analysisJob.value) clearAnalysisResult()
}

async function runWorkerAnalysis() {
  if (!selectedFile.value || !rawCsvText.value) return
  analysisLoading.value = true
  analysisError.value = ''
  saveError.value = ''
  saveResult.value = null
  const options = {
    trim_start_ms: trimStartMs.value === '' ? null : Number(trimStartMs.value),
    trim_end_ms: trimEndMs.value === '' ? null : Number(trimEndMs.value),
    max_abs_sensor_delta_ms: maxDeltaMs.value === '' ? null : Number(maxDeltaMs.value),
    require_sensor_match: requireSensorMatch.value,
    export_label: exportLabel.value || 'processed',
    notes: exportNotes.value || ''
  }
  try {
    const result = selectedVideoFile.value
      ? await api.fusionPreprocess.analyzeUpload({
        source_file: selectedFile.value.name,
        csv_file: selectedFile.value,
        video_file: selectedVideoFile.value,
        options
      })
      : await api.fusionPreprocess.analyzeCsv({
        source_file: selectedFile.value.name,
        csv_text: rawCsvText.value,
        options
      })
    analysisJob.value = result
    processedCsvText.value = result?.result?.processed_csv_text || ''
    processedRowsPreview.value = Array.isArray(result?.result?.processed_rows_preview) ? result.result.processed_rows_preview : []
    workerMetadata.value = result?.result?.metadata || null
  } catch (error) {
    analysisError.value = error?.response?.data?.detail || 'Fusion preprocess worker analysis failed.'
  } finally {
    analysisLoading.value = false
  }
}

async function saveToCsvLibrary() {
  if (!analysisJob.value?.job_id) return
  saveLoading.value = true
  saveError.value = ''
  try {
    const result = await api.fusionPreprocess.saveJobOutput(analysisJob.value.job_id, {
      file_name: suggestedExportName.value
    })
    saveResult.value = result
  } catch (error) {
    saveError.value = error?.response?.data?.detail || 'Failed to save processed dataset to CSV Library.'
  } finally {
    saveLoading.value = false
  }
}

function exportProcessedCsv() {
  if (processedCsvText.value) {
    downloadBlob(suggestedExportName.value, processedCsvText.value, 'text/csv')
    return
  }
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
  selectedVideoFile.value = null
  rawCsvText.value = ''
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
  clearAnalysisResult()
}

function goBack() {
  router.push({ path: '/fusion', query: { tab: 'early' } })
}

watch([trimStartMs, trimEndMs, maxDeltaMs, requireSensorMatch, exportNotes, exportLabel], () => {
  if (analysisJob.value) clearAnalysisResult()
})
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
            <p class="text-sm text-slate-400 mt-1">Load a `cv_sensor_*.csv` export from the early-fusion capture flow. Optionally add the matching capture video so the worker can run OpenCV motion analysis.</p>
          </div>
          <input
            type="file"
            accept=".csv,text/csv"
            class="block w-full rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-slate-200 file:mr-4 file:rounded-md file:border-0 file:bg-teal-500 file:px-4 file:py-2 file:text-white"
            @change="handleFileChange"
          />
          <input
            type="file"
            accept="video/*,.webm,.mp4,.mov,.mkv"
            class="block w-full rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-slate-200 file:mr-4 file:rounded-md file:border-0 file:bg-slate-700 file:px-4 file:py-2 file:text-white"
            @change="handleVideoFileChange"
          />
          <p v-if="loadStatus" class="text-sm text-emerald-300">{{ loadStatus }}</p>
          <p v-if="selectedVideoFile" class="text-sm text-cyan-300">Video loaded: {{ selectedVideoFile.name }}</p>
          <p v-if="parseError" class="text-sm text-rose-300">{{ parseError }}</p>
          <p v-if="analysisError" class="text-sm text-rose-300">{{ analysisError }}</p>
          <p v-if="saveError" class="text-sm text-rose-300">{{ saveError }}</p>
          <p v-if="saveResult?.csv_path" class="text-sm text-emerald-300">Saved to CSV Library: {{ saveResult.csv_path }}</p>
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
            <p class="mt-2 text-lg font-semibold text-white">{{ effectiveSourceStats.row_count ?? sourceStats.rowCount }}</p>
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

        <div class="flex flex-wrap gap-3">
          <BaseBtn variant="primary" :disabled="!selectedFile || analysisLoading" @click="runWorkerAnalysis">
            {{ analysisLoading ? 'Analyzing...' : 'Run Worker Validation' }}
          </BaseBtn>
          <span v-if="analysisJob?.job_id" class="rounded-lg border border-slate-800 bg-slate-950/60 px-4 py-2 text-sm text-slate-300">
            Job: {{ analysisJob.job_id }}
          </span>
        </div>
      </div>
    </BaseCard>

    <div class="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
      <BaseCard>
        <div class="space-y-4">
          <div>
            <p class="text-sm uppercase tracking-[0.2em] text-teal-300">Processed Summary</p>
            <p class="text-sm text-slate-400 mt-1">Use this as the acceptance gate before sending the dataset to CSV Library or external training. Worker-backed validation is authoritative when present.</p>
          </div>

          <div
            v-if="validationSummary"
            class="rounded-xl border px-4 py-4"
            :class="{
              'border-emerald-500/30 bg-emerald-500/10': validationSummary.status === 'pass',
              'border-amber-500/30 bg-amber-500/10': validationSummary.status === 'warning',
              'border-rose-500/30 bg-rose-500/10': validationSummary.status === 'reject'
            }"
          >
            <div class="flex items-center justify-between gap-3">
              <div>
                <p class="text-xs uppercase tracking-[0.2em] text-slate-400">Validation</p>
                <p class="mt-2 text-lg font-semibold text-white">{{ validationSummary.status }}</p>
              </div>
              <div class="text-sm text-slate-200">
                offset: {{ formatMs(validationSummary.offset_ms) }}
              </div>
            </div>
            <p class="mt-3 text-sm text-slate-200">
              {{ Array.isArray(validationSummary.reasons) ? validationSummary.reasons.join(' | ') : '' }}
            </p>
          </div>

          <div v-if="opencvSummary" class="rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-4 text-sm text-slate-200">
            <p class="text-xs uppercase tracking-[0.2em] text-cyan-300">OpenCV Video Summary</p>
            <div class="mt-3 grid gap-3 sm:grid-cols-2">
              <p>frames: <span class="text-white">{{ opencvSummary.frame_count ?? '--' }}</span></p>
              <p>fps: <span class="text-white">{{ opencvSummary.fps ?? '--' }}</span></p>
              <p>duration: <span class="text-white">{{ formatMs(opencvSummary.duration_ms) }}</span></p>
              <p>peak motion time: <span class="text-white">{{ formatMs(opencvSummary.peak_time_ms) }}</span></p>
              <p>motion peak: <span class="text-white">{{ opencvSummary.motion_peak ?? '--' }}</span></p>
              <p>spike detected: <span class="text-white">{{ opencvSummary.spike_detected ? 'yes' : 'no' }}</span></p>
            </div>
            <p class="mt-3 text-xs text-slate-300">
              {{ Array.isArray(opencvSummary.reasons) ? opencvSummary.reasons.join(' | ') : '' }}
            </p>
          </div>

          <div class="grid gap-3 sm:grid-cols-2">
            <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
              <p class="text-xs uppercase tracking-[0.2em] text-slate-500">Kept Rows</p>
              <p class="mt-2 text-lg font-semibold text-white">{{ effectiveProcessedStats.row_count ?? filteredStats.rowCount }}</p>
            </div>
            <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
              <p class="text-xs uppercase tracking-[0.2em] text-slate-500">Dropped Rows</p>
              <p class="mt-2 text-lg font-semibold text-white">{{ effectiveProcessedStats.dropped_rows ?? filteredStats.droppedRows }}</p>
            </div>
            <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
              <p class="text-xs uppercase tracking-[0.2em] text-slate-500">Avg |Delta|</p>
              <p class="mt-2 text-lg font-semibold text-white">{{ formatMs(effectiveProcessedStats.avg_abs_sensor_match_delta_ms ?? filteredStats.avgDeltaMs) }}</p>
            </div>
            <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
              <p class="text-xs uppercase tracking-[0.2em] text-slate-500">Max |Delta|</p>
              <p class="mt-2 text-lg font-semibold text-white">{{ formatMs(effectiveProcessedStats.max_abs_sensor_match_delta_ms ?? filteredStats.maxDeltaMs) }}</p>
            </div>
          </div>

          <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-sm text-slate-300">
            <p>Processed window: {{ formatMs(effectiveProcessedStats.start_ms ?? filteredStats.startMs) }} -> {{ formatMs(effectiveProcessedStats.end_ms ?? filteredStats.endMs) }}</p>
            <p class="mt-2">Gesture column: <span class="text-white">{{ gestureColumn || '--' }}</span></p>
            <p class="mt-2">Timestamp column: <span class="text-white">{{ timestampColumn || '--' }}</span></p>
            <p class="mt-2">Delta column: <span class="text-white">{{ deltaColumn || '--' }}</span></p>
            <p class="mt-2">OpenCV source: <span class="text-white">{{ selectedVideoFile ? selectedVideoFile.name : 'CSV-only analysis' }}</span></p>
            <p v-if="validationSummary" class="mt-2">Sensor match ratio: <span class="text-white">{{ validationSummary.sensor_match_ratio }}</span></p>
            <p v-if="validationSummary" class="mt-2">Missing frame ratio: <span class="text-white">{{ validationSummary.missing_frame_ratio }}</span></p>
          </div>

          <div class="flex flex-wrap gap-3">
            <BaseBtn variant="primary" :disabled="!(processedCsvText || filteredRows.length)" @click="exportProcessedCsv">Download Processed CSV</BaseBtn>
            <BaseBtn variant="secondary" :disabled="!(processedCsvText || filteredRows.length)" @click="exportMetadata">Download Metadata</BaseBtn>
            <BaseBtn variant="secondary" :disabled="!analysisJob?.job_id || saveLoading" @click="saveToCsvLibrary">
              {{ saveLoading ? 'Saving...' : 'Save to CSV Library' }}
            </BaseBtn>
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

          <div v-if="!effectivePreviewRows.length" class="rounded-xl border border-dashed border-slate-800 bg-slate-950/40 p-8 text-center text-slate-500">
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
                  v-for="(row, index) in effectivePreviewRows.slice(0, 12)"
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
