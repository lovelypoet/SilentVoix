#!/usr/bin/env node
/*
 * Vendor the FER+ emotion classifier into public/models/emotion/.
 *
 * Emotion Studio falls back to the Hugging Face mirror of the ONNX Model Zoo
 * when the file is absent, so this script is optional — run it to work offline,
 * to avoid a ~35 MB download per cold cache, or to pin the exact weights a
 * deployment serves. The .onnx is gitignored; the weights are not ours to
 * commit and the repo does not need to carry them.
 */
import { createWriteStream } from 'node:fs'
import { mkdir, rename, stat, unlink } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { Readable } from 'node:stream'
import { pipeline } from 'node:stream/promises'

const MODEL_URL =
  process.env.EMOTION_MODEL_URL ||
  'https://huggingface.co/onnxmodelzoo/emotion-ferplus-8/resolve/main/emotion-ferplus-8.onnx'

// Sanity floor, not a checksum: the published model is ~35 MB, so anything
// this small is a redirect page or a truncated transfer.
const MIN_BYTES = 20 * 1024 * 1024

const here = dirname(fileURLToPath(import.meta.url))
const target = resolve(here, '..', 'public', 'models', 'emotion', 'emotion-ferplus-8.onnx')

const mib = (bytes) => `${(bytes / 1024 / 1024).toFixed(1)} MiB`

const existing = await stat(target).catch(() => null)
if (existing && existing.size >= MIN_BYTES && !process.argv.includes('--force')) {
  console.log(`Already present: ${target} (${mib(existing.size)})`)
  console.log('Pass --force to re-download.')
  process.exit(0)
}

console.log(`Fetching ${MODEL_URL}`)
const response = await fetch(MODEL_URL)
if (!response.ok || !response.body) {
  console.error(`Download failed: HTTP ${response.status} ${response.statusText}`)
  process.exit(1)
}

await mkdir(dirname(target), { recursive: true })

// Write to a sibling temp file first, so an interrupted run cannot leave a
// half-written model that then fails to parse in the browser.
const partial = `${target}.partial`
try {
  await pipeline(Readable.fromWeb(response.body), createWriteStream(partial))
  const { size } = await stat(partial)
  if (size < MIN_BYTES) throw new Error(`downloaded only ${mib(size)}`)
  await rename(partial, target)
  console.log(`Saved ${target} (${mib(size)})`)
  console.log('Served at /models/emotion/emotion-ferplus-8.onnx — Emotion Studio picks it up automatically.')
} catch (error) {
  await unlink(partial).catch(() => {})
  console.error(`Download failed: ${error.message}`)
  process.exit(1)
}
