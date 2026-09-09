# Face Emotion Recognition (Emotion Studio)

Live facial-emotion recognition at `/emotion`, in the frontend nav under
**Workspace → Emotion Studio**. Two models cooperate, both client-side.

## Models

| Role | Model | Where it runs |
|---|---|---|
| Face detection + geometry | MediaPipe `face_landmarker` (478 landmarks, 52 blendshapes) | `@mediapipe/tasks-vision`, GPU delegate |
| Emotion classification | `emotion-ferplus-8` (ONNX Model Zoo) | `onnxruntime-web`, WASM |

`emotion-ferplus-8` is a VGG-style CNN trained on the **FER+** re-annotation of
FER2013. Contract, as encoded in `vue-next/src/composables/ai/emotionModel.js`:

```
input   'Input3'            float32 [1, 1, 64, 64]   raw 0-255 luminance
output  'Plus692_Output_0'  float32 [1, 8]           logits -> softmax
classes neutral, happiness, surprise, sadness, anger, disgust, fear, contempt
```

Two things are easy to get wrong:

- **Do not normalise the input.** The ONNX graph starts with its own
  subtract/divide, so feed BT.601 luma on the 0-255 scale.
- **The class order above is load-bearing.** The model emits a bare 8-vector;
  that order is the only thing giving those numbers meaning. It is asserted in
  `emotionModel.spec.js`.

## Why this runs in the browser

Unlike the gesture path, emotion inference does **not** go through the API or a
runtime sidecar. A real-time emotion CNN needs pixels, not landmarks, and
streaming face crops to the backend at 12/s would cost more than it buys. The
model is 35 MB and the input is 64x64, so WASM handles it comfortably in-tab —
and the page therefore works against a dev server with no TensorFlow or PyTorch
service running, and uploads nothing.

Consequently there is no `api/` or `backend/` counterpart to mirror, and no
`registry.json` entry: `AI/model_library/` covers models the backend serves.

## Weights

The `.onnx` is gitignored (`vue-next/.gitignore`). It is resolved at load time,
first hit wins:

1. `VITE_EMOTION_MODEL_URL`, when a deployment pins one
2. `/models/emotion/emotion-ferplus-8.onnx` — vendored locally
3. the ONNX Model Zoo mirror on Hugging Face

So the page works with no setup, and vendoring is a one-liner:

```bash
cd vue-next
npm run model:emotion            # -> public/models/emotion/, ~35 MB
npm run model:emotion -- --force # re-download
```

Vendor the weights for offline work, to avoid a 35 MB fetch per cold cache, or
to pin exactly what a deployment serves. `EMOTION_MODEL_URL` overrides the
download source. Note that `public/` is copied verbatim into `dist/`, so a build
made after vendoring carries the weights.

The onnxruntime WASM binary needs no such handling: `onnxruntime-web/wasm`
resolves it through `import.meta.url`, so Vite emits it as a normal asset and no
CDN is involved at runtime.

**But it must be excluded from dep pre-bundling**, which `vite.config.js` does:

```js
optimizeDeps: { exclude: ['onnxruntime-web', 'onnxruntime-web/wasm'] }
```

Without it, esbuild rewrites `import.meta.url` to `node_modules/.vite/deps/`
without copying the 14 MB `.wasm` there. The dev server answers that path with
`index.html`, ORT tries to compile HTML as WebAssembly, and you get:

```
no available backend found. ERR: [wasm] RuntimeError: Aborted(CompileError:
wasm validation error: at offset 4: failed to match magic number)
```

`vite build` was never affected — it emits the binary correctly — so this
reproduces only under `npm run dev`. After changing the exclusion, delete
`node_modules/.vite` or Vite will keep serving its stale pre-bundle.

## Diagnosing a load failure

`useFaceEmotion` tags failures with the stage that produced them, and the page
prints advice per stage, because the three modes need three different fixes:

| `loadErrorStage` | Meaning | Fix |
|---|---|---|
| `weights` | the `.onnx` could not be fetched | vendor it, or set `VITE_EMOTION_MODEL_URL` |
| `runtime` | weights arrived, WASM backend would not start | the `optimizeDeps` trap above, or a browser without WASM SIMD |
| `detector` | MediaPipe assets unreachable | network access — the `.task` and vision runtime come from Google's CDN |

## Code layout

| File | Responsibility |
|---|---|
| `src/composables/ai/emotionModel.js` | Labels, softmax, crop geometry, grayscale conversion, EMA smoothing, CSV. Pure — no camera, no WASM. |
| `src/composables/ai/useFaceEmotion.js` | Runtime wiring: FaceLandmarker + ORT session, the rAF loop, overlay drawing, recording. |
| `src/views/EmotionStudio.vue` | The page: preview, distribution, blendshape signals, history strip, controls. |
| `scripts/fetch-emotion-model.js` | Vendors the weights into `public/`. |

`useFaceEmotion.js` follows `useHandTracking.js`: an unmirrored working canvas
feeds the detector, a second canvas draws the optionally-mirrored overlay.

## Runtime behaviour worth knowing

- **Two independent rate gates.** Landmarks track at 30 fps; the CNN runs at a
  configurable 2-30/s (default 12) with an in-flight guard, so a slow
  classification never stalls the preview. The crop is taken synchronously
  before the first `await`, since the working canvas is overwritten by the next
  detect tick.
- **Smoothing is not cosmetic.** Per-frame FER+ output is jittery enough that a
  blink flips the argmax. The default EMA inertia is 0.6.
- **Below the confidence floor the page says "Uncertain"** rather than naming a
  low-probability argmax. Default 35%.
- **A face lost for under 350 ms is held**, so one dropped frame does not blank
  the readout. Past that, smoothing state is discarded so the next face starts
  clean.
- **Recording** writes one CSV row per classification —
  `timestamp_ms,dominant,confidence` plus all eight probabilities.
- **"Speak the emotion"** posts to the same `/utils/tts/test` route the gesture
  pipeline speaks through, but only after a label has held for 1.2 s, and at
  most once every 3 s. Failures are logged, never fatal.

## Accuracy expectations

FER2013/FER+ is a small, low-resolution, in-the-wild dataset; published FER+
accuracy is in the mid-80s on its own test split and noticeably lower on faces
that differ in lighting, pose or demographics. `happiness`, `neutral` and
`surprise` are reliable; `contempt`, `disgust` and `fear` are weak — they are
the rarest classes in the training data. Treat the output as a signal, not a
verdict, and do not build anything consequential on a single frame.
