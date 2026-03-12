"""
Model inference logic for single-hand gesture prediction in the sign glove system.

When running inside the Docker runtime-split architecture the backend-api container
does NOT have TensorFlow installed.  In that case, predict_gesture() forwards
inference requests to the external ml-tensorflow service over HTTP.

When running locally with TensorFlow available, the original TFLite path is
preserved as a fallback.
"""

import numpy as np
import os
import logging
import httpx
from api.core.settings import settings

logger = logging.getLogger("signglove")

# ---------------------------------------------------------------------------
# Try importing TensorFlow, but it may not be available in the API-only image.
# ---------------------------------------------------------------------------
try:
    import tensorflow as tf  # type: ignore
except Exception as exc:  # pragma: no cover
    tf = None
    logger.info("TensorFlow unavailable in this container (expected for API-only image): %s", exc)


def load_model():
    """Loads the TFLite model and returns the interpreter (local fallback only)."""
    try:
        if tf is None:
            logger.info("Skipping local TFLite model load; will forward to ml-tensorflow service")
            return None
        if not os.path.exists(settings.LEGACY_TFLITE_MODEL_PATH):
            logger.error(f"Legacy TFLite fallback model not found at: {settings.LEGACY_TFLITE_MODEL_PATH}")
            return None
        interpreter = tf.lite.Interpreter(model_path=settings.LEGACY_TFLITE_MODEL_PATH)
        interpreter.allocate_tensors()
        logger.info(f"Legacy TFLite fallback loaded successfully from: {settings.LEGACY_TFLITE_MODEL_PATH}")
        return interpreter
    except Exception as e:
        logger.error(f"Error loading TFLite model: {e}")
        return None


# Load the model once at import time (will be None when TF is unavailable).
model = load_model()

LABEL_MAP = {0: "Hello", 1: "Yes", 2: "No", 3: "We", 4: "Are", 5: "Students", 6: "Rest"}


def _predict_remote(values: list) -> dict:
    """Forward inference to the external ml-tensorflow runtime service."""
    url = f"{str(settings.ML_TENSORFLOW_URL).rstrip('/')}/v1/predict-legacy"
    try:
        resp = httpx.post(url, json={"values": values}, timeout=5.0)
        data = resp.json()
        if resp.status_code >= 400 or data.get("status") == "error":
            return {"status": "error", "message": data.get("message", "Remote prediction failed")}
        return data
    except Exception as exc:
        logger.error("Remote prediction failed: %s", exc)
        return {"status": "error", "message": f"Remote prediction service unavailable: {exc}"}


def predict_gesture(values: list) -> dict:
    """
    Predicts gesture from single hand sensor data.
    Delegates to local TFLite interpreter or external ml-tensorflow service.
    """
    # Prefer remote service when runtime services are enabled or TF is not installed.
    if settings.USE_RUNTIME_SERVICES or model is None:
        return _predict_remote(values)

    # Local TFLite fallback (native dev without Docker)
    try:
        if len(values) != 11:
            return {"status": "error", "message": "Invalid sensor input (expected 11 values)"}

        input_data = np.array([values], dtype=np.float32)
        input_details = model.get_input_details()
        output_details = model.get_output_details()
        model.set_tensor(input_details[0]['index'], input_data)
        model.invoke()
        output = model.get_tensor(output_details[0]['index'])
        predicted_index = int(np.argmax(output))
        confidence = float(np.max(output))
        label = LABEL_MAP.get(predicted_index, f"Class {predicted_index}")
        return {"status": "success", "prediction": label, "confidence": confidence}
    except Exception as e:
        logger.error(f"Error during prediction: {e}")
        return {"status": "error", "message": f"An error occurred during prediction: {str(e)}"}
