"""
Model inference logic for single-hand gesture prediction in the sign glove system.

- predict_gesture: Loads a TFLite model and predicts gesture from single hand sensor data.
"""
# core/model.py

import numpy as np
import tensorflow as tf
import os
import logging
from core.settings import settings

# Initialize logger
logger = logging.getLogger("signglove")

def load_model():
    """Loads the TFLite model and returns the interpreter."""
    try:
        if not os.path.exists(settings.MODEL_PATH):
            logger.error(f"Model file not found at: {settings.MODEL_PATH}")
            return None
        
        interpreter = tf.lite.Interpreter(model_path=settings.MODEL_PATH)
        interpreter.allocate_tensors()
        logger.info(f"TFLite model loaded successfully from: {settings.MODEL_PATH}")
        return interpreter
    except Exception as e:
        logger.error(f"Error loading TFLite model: {e}")
        return None

# Load the model once when the module is imported
model = load_model()

def predict_gesture(values: list) -> dict:
    """
    Predicts gesture from single hand sensor data using the pre-loaded TFLite model.
    Args:
        values (list): List of 11 sensor values.
    Returns:
        dict: Prediction result with status, prediction, and confidence.
    """
    if model is None:
        return {
            "status": "error",
            "message": "Model is not loaded. Check logs for details."
        }
        
    try:
        if len(values) != 11:
            return {
                "status": "error",
                "message": "Invalid sensor input (expected 11 values)"
            }

        # Prepare input data
        input_data = np.array([values], dtype=np.float32)

        input_details = model.get_input_details()
        output_details = model.get_output_details()

        model.set_tensor(input_details[0]['index'], input_data)
        model.invoke()

        output = model.get_tensor(output_details[0]['index'])
        predicted_index = int(np.argmax(output))
        confidence = float(np.max(output))

        label_map = {0: "Hello", 1: "Yes", 2: "No", 3: "We", 4: "Are", 5: "Students", 6: "Rest"}
        label = label_map.get(predicted_index, f"Class {predicted_index}")

        return {
            "status": "success",
            "prediction": label,
            "confidence": confidence
        }

    except Exception as e:
        logger.error(f"Error during prediction: {e}")
        return {
            "status": "error",
            "message": f"An error occurred during prediction: {str(e)}"
        }
