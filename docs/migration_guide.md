# Migration Guide: From Training Platform to Model Testing Ground

This guide explains the architectural shift in SilentVoix and how to adapt your workflow to the new **Model Testing Ground** scope.

## 1. The Shift in Focus

Previously, SilentVoix aimed to be an all-in-one platform where you could collect data, train a model, and run inference all within the same application. 

**The New Vision:** SilentVoix is now a **Model Testing Ground**. We focus on providing a robust, multi-format environment for testing and evaluating models trained in specialized external environments (like Google Colab, local Jupyter notebooks, or dedicated ML pipelines).

## 2. What Changes for You?

### Training Models
- **OLD:** You used `/training/run` or the web UI to trigger a training script inside the backend.
- **NEW:** Train your models externally. Once you have a stable model artifact (`.tflite`, `.keras`, `.h5`, or `.pth`), use the **Playground Model Upload** feature.

### Data Collection
- **STAYS THE SAME:** Data collection features remain fully active. You can still use the SignGlove hardware and the `/data/collect` endpoints to gather datasets. 
- **RECOMMENDED:** Export your collected data from MongoDB to CSV and use it as training data for your external ML models.

### Inference & Playground
- **IMPROVED:** The Playground now supports multiple model versions. You can upload different iterations of your model, switch between them instantly, and compare their performance in real-time.

## 3. How to Migrate Your Models

To migrate a model to the new Playground, you need two files:
1. **Model Artifact**: The exported file (e.g., `my_model.pth`).
2. **Metadata JSON**: A small file describing your model.

### Metadata Schema Example (`metadata.json`)
```json
{
  "model_name": "LSTM Gesture Model v2",
  "model_family": "lstm",
  "input_spec": {
    "shape": [1, 126],
    "input_dim": 126
  },
  "labels": ["hello", "thank_you", "yes", "no"],
  "export_format": "pth",
  "version": "2.1.0",
  "precision": 0.94,
  "recall": 0.92,
  "f1": 0.93
}
```

## 4. Migration FAQ

**Q: Why was in-app training deprecated?**
A: In-app training was restricted by the backend environment's hardware and software dependencies. By shifting to an upload-based model, we allow researchers to use any training framework or hardware they prefer.

**Q: Can I still use my old `.tflite` models?**
A: Yes. `.tflite` remains a first-class supported format in the new testing ground.

**Q: Where do I find my training metrics now?**
A: Metrics (Precision, Recall, F1) are now part of the model metadata. When you upload a model, you should include the metrics calculated during your external training session. These will be displayed in the Playground UI for audit and comparison.

**Q: Is `.pth` (PyTorch) fully supported?**
A: Yes, `.pth` is now a curated format alongside the legacy TensorFlow/Keras formats.

## 5. Deprecated Endpoints Reference

| Category | Endpoints | Status | Alternative |
| :--- | :--- | :--- | :--- |
| **Training Runs** | `/training/run`, `/training/trigger` | Deprecated | External training + Playground Upload |
| **Late Fusion** | `/training/late-fusion/run` | Deprecated | External fusion + Playground Upload |
| **Metrics** | `/training/metrics/latest` | Deprecated | Metadata metrics in Upload package |
| **Analysis** | `/training/analyze-confusion-matrix` | Deprecated | External evaluation scripts |

---
For technical details on the backend migration, see [backend_cleanup_pth_migration.md](backend_cleanup_pth_migration.md).
