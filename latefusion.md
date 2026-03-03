# Technical Specification: Late Fusion Multimodal Pipeline (v1.1)

**Role:** Senior Software Engineer / System Architect  
**Project:** SilentVoix Hybrid Recognition  
**Methodology:** Decision-Level Fusion (Weighted Soft Voting)

## 1. System Architecture
Unlike Early Fusion, Late Fusion treats Glove and Vision as independent experts.
Each modality runs its own model and outputs class probabilities.
A fusion rule combines those probabilities into the final class decision.

## 2. Independent Expert Models
| Expert | Input Vector | Input Dim | Example Model |
| :--- | :--- | :--- | :--- |
| Glove Expert | `[f1..f5, ax..gz]` | 11 | Random Forest |
| Vision Expert | `[21 landmarks * (x,y,z)]` | 63 | SVM / NN |

Dual-hand mode extends both experts to left/right streams:
- 2 Glove experts (left/right)
- 2 Vision experts (left/right)

## 3. Fusion Rule: Weighted Soft Voting
For each class `c`:

`P_final(c) = (w_g * P_glove(c)) + (w_v * P_vision(c))`

with `w_g + w_v = 1`.

Example static weights from your report context:
- `w_g = 0.8`
- `w_v = 0.2`

## 4. Engineering Trade-offs
### Strengths
- Graceful degradation when one modality fails.
- Modality-specific model optimization.
- Easier debugging of expert disagreement.

### Challenges
- Temporal alignment between independently processed streams.
- Weight tuning across environments and hardware setups.

## 5. Data Policy (Critical)
Late Fusion training should use **modality-separated datasets**, not fused-row datasets.

- Single-hand late fusion uses:
  - `cv_single` + `sensor_single`
- Dual-hand late fusion uses:
  - `cv_dual` + `sensor_dual`

`fusion_single` / `fusion_dual` belong to Early Fusion workflows and are not primary late-fusion training inputs.

## 6. Data Controller Selection Contract (Implemented)
CSV Library uses slot-based selection for late fusion:

- `late:single:cv`
- `late:single:sensor`
- `late:dual:cv`
- `late:dual:sensor`

A late-fusion training run is considered valid only when both required slots are selected for the chosen mode.

### Compatibility rules
- `pipeline=late, mode=single` => allowed schemas: `cv_single`, `sensor_single`
- `pipeline=late, mode=dual` => allowed schemas: `cv_dual`, `sensor_dual`

### Selection enforcement
- If selecting a late `cv` slot, schema must match `cv_{mode}`.
- If selecting a late `sensor` slot, schema must match `sensor_{mode}`.

## 7. Implementation Note
Early and Late are intentionally asymmetric:
- Early: one fused dataset slot per mode (`early:single`, `early:dual`)
- Late: two expert slots per mode (`cv` + `sensor`)

This asymmetry is expected and required by the model design.
