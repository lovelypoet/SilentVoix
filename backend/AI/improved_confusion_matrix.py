import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import confusion_matrix, classification_report, roc_curve, auc
from sklearn.preprocessing import label_binarize
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense
from tensorflow.keras.utils import to_categorical
import tensorflow as tf
import os
import json
import matplotlib.pyplot as plt
import seaborn as sns
from itertools import cycle
import sys
from datetime import datetime
from uuid import uuid4
import asyncio

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Optional DB modules
try:
    from core.database import model_collection
    from models.model_result import ModelResult
except ImportError as e:
    print(f"Warning: Could not import database modules: {e}")
    model_collection = None
    ModelResult = None

# Settings fallback
try:
    from core.settings import settings
except ImportError:
    class Settings:
        GESTURE_DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'gesture_data.csv')
        MODEL_PATH = os.path.join(os.path.dirname(__file__), 'gesture_model.tflite')
        METRICS_PATH = os.path.join(os.path.dirname(__file__), 'training_metrics.json')
        RESULTS_DIR = os.path.join(os.path.dirname(__file__), 'results')
    settings = Settings()

gesture_data_path = os.environ.get('GESTURE_DATA_FILE', settings.GESTURE_DATA_PATH)
model_output_path = settings.MODEL_PATH
metrics_output_path = settings.METRICS_PATH
results_dir = settings.RESULTS_DIR
os.makedirs(results_dir, exist_ok=True)

# ==================== Load CSV ====================
df = pd.read_csv(gesture_data_path)

if 'session_id' in df.columns:
    df = df.drop('session_id', axis=1)
    print("Removed session_id column from features")

feature_columns = [col for col in df.columns if col != 'label']
X_raw = df[feature_columns].values
y = df['label'].values

print(f"Feature columns: {feature_columns}")
print(f"Label values: {np.unique(y)}")

num_features = X_raw.shape[1]
if num_features != 11:
    raise ValueError(f"Expected 11 features for single-hand glove, got {num_features}")

# ==================== Preprocessing Functions ====================
def compute_imu_angles(ax, ay, az):
    """Convert raw accelerometer to roll/pitch angles in degrees"""
    roll = np.arctan2(ay, az) * 180 / np.pi
    pitch = np.arctan2(-ax, np.sqrt(ay**2 + az**2)) * 180 / np.pi
    return roll, pitch

def ema_smooth(current, previous, alpha=0.2):
    return alpha * current + (1 - alpha) * previous

# ==================== Build 11-feature dataset ====================
X_processed = []

ema_roll_prev = 0.0
ema_pitch_prev = 0.0
ema_yaw_prev = 0.0

flex_min = X_raw[:, :5].min(axis=0)
flex_max = X_raw[:, :5].max(axis=0)

for row in X_raw:
    features = []

    # Flex sensors (0-4)
    for i in range(5):
        norm_flex = (row[i] - flex_min[i]) / (flex_max[i] - flex_min[i] + 1e-6)
        features.append(norm_flex)

    # IMU accel -> roll/pitch (5-7)
    ax, ay, az = row[5], row[6], row[7]
    roll, pitch = compute_imu_angles(ax, ay, az)
    roll = ema_smooth(roll, ema_roll_prev)
    pitch = ema_smooth(pitch, ema_pitch_prev)
    ema_roll_prev = roll
    ema_pitch_prev = pitch
    features.append(roll / 180.0)
    features.append(pitch / 180.0)

    # Gyroscope -> yaw (8), plus Gx/Gy/Gz raw (9-11)
    gx, gy, gz = row[8], row[9], row[10]
    yaw = gz  # or integrate if you have delta time
    yaw = ema_smooth(yaw, ema_yaw_prev)
    ema_yaw_prev = yaw
    features.append(yaw / 180.0)

    X_processed.append(features)

X_processed = np.array(X_processed)
print(f"Processed feature shape: {X_processed.shape}")  # Should be (num_samples, 11)

# ==================== Encode labels ====================
label_encoder = LabelEncoder()
y_encoded = label_encoder.fit_transform(y)
num_classes = len(np.unique(y_encoded))
y_cat = to_categorical(y_encoded, num_classes=num_classes)
print(f"Number of classes: {num_classes}")

# ==================== Train/Test Split ====================
X_train, X_test, y_train, y_test = train_test_split(X_processed, y_cat, test_size=0.2, random_state=42)

# ==================== Model Architecture ====================
model = Sequential([
    Dense(32, activation='relu', input_shape=(11,)),
    Dense(16, activation='relu'),
    Dense(num_classes, activation='softmax')
])
print("Model architecture optimized for 11-feature single-hand input")
model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
model.summary()

# ==================== Train Model ====================
history = model.fit(X_train, y_train, epochs=100, batch_size=16, validation_split=0.1)

# ==================== Evaluate Model ====================
loss, acc = model.evaluate(X_test, y_test)
print(f"\nTest accuracy: {acc:.3f}")

y_pred_proba = model.predict(X_test)
y_pred_classes = np.argmax(y_pred_proba, axis=1)
y_true_classes = np.argmax(y_test, axis=1)

cm = confusion_matrix(y_true_classes, y_pred_classes)
class_report = classification_report(y_true_classes, y_pred_classes, output_dict=True)

# ==================== ROC Curves ====================
fpr = dict()
tpr = dict()
roc_auc = dict()

if num_classes == 2:
    fpr[1], tpr[1], _ = roc_curve(y_true_classes, y_pred_proba[:,1])
    roc_auc[1] = auc(fpr[1], tpr[1])
    fpr[0], tpr[0], _ = roc_curve(1 - y_true_classes, 1 - y_pred_proba[:,0])
    roc_auc[0] = auc(fpr[0], tpr[0])
    fpr["micro"], tpr["micro"], _ = roc_curve(y_true_classes, y_pred_proba[:,1])
    roc_auc["micro"] = auc(fpr["micro"], tpr["micro"])
else:
    y_test_bin = label_binarize(y_true_classes, classes=range(num_classes))
    for i in range(num_classes):
        fpr[i], tpr[i], _ = roc_curve(y_test_bin[:,i], y_pred_proba[:,i])
        roc_auc[i] = auc(fpr[i], tpr[i])
    fpr["micro"], tpr["micro"], _ = roc_curve(y_test_bin.ravel(), y_pred_proba.ravel())
    roc_auc["micro"] = auc(fpr["micro"], tpr["micro"])

# ==================== Save Metrics ====================
def safe_float(value):
    if np.isnan(value) or np.isinf(value):
        return None
    return float(value)

def safe_list(arr):
    return [safe_float(x) if isinstance(x,(int,float,np.number)) else x for x in arr]

metrics_data = {
    "accuracy": float(acc),
    "loss": float(loss),
    "confusion_matrix": cm.tolist(),
    "classification_report": class_report,
    "roc_curves": {
        "fpr": {str(k): safe_list(v) for k,v in fpr.items()},
        "tpr": {str(k): safe_list(v) for k,v in tpr.items()},
        "auc": {str(k): safe_float(v) for k,v in roc_auc.items()}
    },
    "labels": label_encoder.classes_.tolist(),
    "training_history": {
        "accuracy": [float(x) for x in history.history['accuracy']],
        "val_accuracy": [float(x) for x in history.history['val_accuracy']],
        "loss": [float(x) for x in history.history['loss']],
        "val_loss": [float(x) for x in history.history['val_loss']]
    }
}

with open(metrics_output_path,'w') as f:
    json.dump(metrics_data, f, indent=2)
print(f"Metrics saved to {metrics_output_path}")

# ==================== Convert to TFLite ====================
converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
tflite_model = converter.convert()
with open(model_output_path, 'wb') as f:
    f.write(tflite_model)
print(f"TFLite model saved to {model_output_path}")
