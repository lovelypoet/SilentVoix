# Refactor Plan — Realtime AI Playground

## Context

The file **`RealtimeAIPlayground.vue` (~1660 lines)** has grown into a *God Component* that currently handles too many responsibilities:

* **State management**

  * Model metadata
  * Fusion weights
  * Prediction outputs
  * Stream statuses

* **Logic**

  * Hand tracking
  * Coordinate normalization
  * Early fusion buffering
  * Weighted fusion math

* **I/O**

  * Camera stream
  * Sensor WebSocket stream
  * Integrated inference WebSocket
  * API calls

* **UI**

  * Canvas drawing
  * Feedback dialogs
  * Conditional rendering

This violates the **Single Responsibility Principle** and makes the code difficult to maintain, test, and extend.

The goal of this refactor is to **separate logic, state, and UI into a modular architecture**.

---

# Architecture Strategy

We will adopt a **Headless Logic + Orchestrator Pattern**.

The main view becomes a **lightweight orchestrator**, while logic moves into composables/services and UI into small components.

```
RealtimeAIPlayground.vue (Orchestrator)
        │
        ▼
Playground Engine / Composables
        │
        ▼
Pinia Store (shared state)
        │
        ▼
UI Components (render only)
```

This keeps **logic testable and UI simple**.

---

# Proposed Directory Structure

```
src/
│
├── views/
│   └── RealtimeAIPlayground.vue
│
├── components/playground/
│   ├── CameraStream.vue
│   ├── ModelSelector.vue
│   ├── PredictionOutput.vue
│   ├── FusionControls.vue
│   ├── FusionGraph.vue
│   └── SerialMonitor.vue
│
├── composables/
│   ├── ai/
│   │   ├── useFusionLogic.js
│   │   ├── useModelLoader.js
│   │   └── useInferencePipeline.js
│   │
│   └── playground/
│       ├── useSensorStream.js
│       ├── useIntegratedInference.js
│       └── useWebsocketManager.js
│
├── engine/
│   └── playgroundEngine.js
│
├── stores/
│   └── playgroundStore.js
│
├── renderers/
│   ├── skeletonRenderer.js
│   └── bboxRenderer.js
│
└── tests/
    ├── fusion.test.js
    ├── sensorParser.test.js
    └── predictionNormalizer.test.js
```

---

# Responsibilities

## 1. `RealtimeAIPlayground.vue`

Acts as the **orchestrator page**.

Responsibilities:

* Layout
* Connecting components
* Calling the engine

Example:

```vue
<script setup>
import { usePlaygroundEngine } from "@/engine/playgroundEngine"

import CameraStream from "@/components/playground/CameraStream.vue"
import PredictionOutput from "@/components/playground/PredictionOutput.vue"
import SerialMonitor from "@/components/playground/SerialMonitor.vue"

const engine = usePlaygroundEngine()
</script>

<template>
  <CameraStream />

  <PredictionOutput :prediction="engine.fusedPrediction" />

  <SerialMonitor :sensor="engine.sensorData" />
</template>
```

Target size: **~200–300 lines**

---

# Playground Engine

`engine/playgroundEngine.js`

Acts as the **frontend AI pipeline orchestrator**.

Responsibilities:

* Connecting streams
* Running fusion
* Coordinating inference modules

Example:

```js
import { useSensorStream } from "@/composables/playground/useSensorStream"
import { useFusionLogic } from "@/composables/ai/useFusionLogic"
import { useInferencePipeline } from "@/composables/ai/useInferencePipeline"

export function usePlaygroundEngine() {
  const { sensorData } = useSensorStream()
  const { cvPrediction } = useInferencePipeline()
  const { fuse } = useFusionLogic()

  const fusedPrediction = computed(() =>
    fuse(sensorData.value, cvPrediction.value)
  )

  return {
    sensorData,
    cvPrediction,
    fusedPrediction
  }
}
```

---

# Composables

### `useSensorStream.js`

Handles:

* WebSocket connection
* Parsing sensor packets
* Maintaining reactive sensor state

### `useIntegratedInference.js`

Handles:

* YOLO / landmark inference
* Streaming prediction data
* Buffer management

### `useFusionLogic.js`

Handles:

* Weighted fusion
* Winner selection
* Early fusion math

These should contain **pure logic**, making them easy to test.

---

# Renderers

Canvas drawing logic should be removed from components.

```
renderers/
   skeletonRenderer.js
   bboxRenderer.js
```

Example:

```js
export function drawSkeleton(ctx, landmarks) {
  // drawing logic
}
```

Components only call these helpers.

---

# State Management

`stores/playgroundStore.js`

Global state includes:

```
activeModel
cvPrediction
sensorPrediction
fusedPrediction

isLive
isFusionMode
isEarlyFusionMode
```

Pinia prevents **prop drilling across multiple components**.

---

# Testing Strategy

We will use **lightweight unit tests for core logic only**.

Focus areas:

* Fusion calculations
* Sensor packet parsing
* Prediction normalization

Example:

```
tests/
   fusion.test.js
   sensorParser.test.js
   predictionNormalizer.test.js
```

UI components will be tested **manually**, since most logic is externalized.

---

# Refactor Plan (Incremental)

### Step 1

Extract **sensor WebSocket logic**

```
useSensorStream.js
```

This should immediately shrink the main file.

---

### Step 2

Extract **fusion logic**

```
useFusionLogic.js
```

Add unit tests for fusion math.

---

### Step 3

Move **canvas drawing**

```
renderers/
```

---

### Step 4

Create **playgroundEngine.js**

Centralize AI pipeline orchestration.

---

### Step 5

Split UI into smaller components

```
CameraStream
PredictionOutput
FusionControls
SerialMonitor
```

---

# Expected Result

Before:

```
RealtimeAIPlayground.vue
≈ 1660 lines
```

After:

```
RealtimeAIPlayground.vue
≈ 200–300 lines
playgroundEngine.js
≈ 200 lines
composables/
≈ 100–200 lines each
```

Benefits:

* easier maintenance
* easier debugging
* testable logic
* reusable components
* cleaner architecture

---

# Long-Term Benefit

This structure turns the playground into a **modular AI experimentation platform** where we can:

* swap models easily
* test new fusion strategies
* monitor sensor pipelines
* extend the system without creating another God component
