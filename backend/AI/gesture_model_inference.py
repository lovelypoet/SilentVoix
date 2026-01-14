# gesture_model_inference.py
import numpy as np
import pickle
import tensorflow as tf
from collections import deque
from scipy.stats import mode
from core.settings import settings
import os

# ==================== SETTINGS ====================
RESULTS_DIR = settings.RESULTS_DIR

# Paths
MODEL_PATH = settings.MODEL_PATH       # default first fold
SCALER_PATH = settings.SCALER_PATH
ENCODER_PATH = settings.ENCODER_PATH

TIMESTEPS = 50   # must match training
ROLLING_WINDOW = 5   # number of recent predictions to smooth
SKIP_GESTURES = ["Rest"]   # gestures to ignore

# ==================== LOAD MODEL & PREPROCESSORS ====================
# Load TFLite model and allocate tensors
tflite_interpreter = None
input_details = None
output_details = None

if os.path.exists(MODEL_PATH):
    try:
        tflite_interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
        tflite_interpreter.allocate_tensors()
        input_details = tflite_interpreter.get_input_details()
        output_details = tflite_interpreter.get_output_details()
        print(f"H5 model loaded successfully from: {MODEL_PATH}")
    except Exception as e:
        print(f"[Warning] Could not load TFLite model from {MODEL_PATH}: {e}")
        tflite_interpreter = None
else:
    print(f"[Warning] Model file not found at {MODEL_PATH}. Model will not be loaded.")

# Load scaler
if os.path.exists(SCALER_PATH):
    with open(SCALER_PATH, "rb") as f:
        scaler = pickle.load(f)
else:
    print(f"[Warning] Scaler file not found at {SCALER_PATH}.")
    scaler = None

# Load label encoder
if os.path.exists(ENCODER_PATH):
    with open(ENCODER_PATH, "rb") as f:
        label_encoder = pickle.load(f)
else:
    print(f"[Warning] Label encoder file not found at {ENCODER_PATH}.")
    label_encoder = None

# ==================== BUFFERS ====================
sequence_buffer = []  # stores recent frames for LSTM input
prediction_buffer = deque(maxlen=ROLLING_WINDOW)  # stores recent predictions for smoothing

# ==================== PREPROCESS FRAME ====================
def preprocess_frame(frame):
    """
    Add new sensor frame to the buffer and prepare input for prediction.
    frame: 1D numpy array of shape (NUM_FEATURES,)
    Returns: input tensor of shape (1, TIMESTEPS, NUM_FEATURES) or None if buffer not full
    """
    if scaler is None:
        raise ValueError("Scaler not loaded. Cannot preprocess frame.")

    global sequence_buffer
    frame_scaled = scaler.transform(frame.reshape(1, -1))
    sequence_buffer.append(frame_scaled[0])

    if len(sequence_buffer) > TIMESTEPS:
        sequence_buffer.pop(0)

    if len(sequence_buffer) == TIMESTEPS:
        X_input = np.array(sequence_buffer).astype(input_details[0]['dtype'])
        return X_input
    return None

# ==================== PREDICTION WITH SMOOTHING ====================
def predict_gesture(X_input):
    """
    Predict gesture from input tensor and apply rolling window smoothing.
    Returns gesture label as string or None if skipped.
    """
    if tflite_interpreter is None or label_encoder is None:
        raise ValueError("Model or label encoder not loaded. Cannot predict gesture.")
    
    tflite_interpreter.set_tensor(input_details[0]['index'], X_input)
    tflite_interpreter.invoke()
    output_data = tflite_interpreter.get_tensor(output_details[0]['index'])
    
    pred_class = np.argmax(output_data, axis=1)[0]
    prediction_buffer.append(pred_class)

    # Apply mode over rolling window
    smoothed_class = mode(list(prediction_buffer))[0][0]
    gesture_name = label_encoder.inverse_transform([smoothed_class])[0]

    if gesture_name in SKIP_GESTURES:
        return None
    return gesture_name

# ==================== RESET BUFFERS ====================
def reset_buffers():
    global sequence_buffer, prediction_buffer
    sequence_buffer = []
    prediction_buffer.clear()