import numpy as np
import os
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix, classification_report
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, Input
from tensorflow.keras.callbacks import EarlyStopping

# ==============================
# 1. CONFIG
# ==============================
DATA_PATH = "/content/drive/MyDrive/SignLanguage_Data"
ACTIONS = ['rest', 'hello', 'thank_you', 'yes', 'no', 'bye']
SEQUENCE_LENGTH = 30
FEATURE_DIM = 74  # 63 Vision + 11 Sensor

# ==============================
# 2. LOAD DATASET
# ==============================
X, y = [], []
label_map = {label: num for num, label in enumerate(ACTIONS)}

print("--- Đang tải dữ liệu... ---")
for action in ACTIONS:
    action_path = os.path.join(DATA_PATH, action)
    if not os.path.exists(action_path):
        print(f"Cảnh báo: Thư mục {action} không tồn tại!")
        continue

    for file in os.listdir(action_path):
        if file.endswith(".npz"):
            data = np.load(os.path.join(action_path, file))['data']
            if data.shape == (SEQUENCE_LENGTH, FEATURE_DIM):
                X.append(data)
                y.append(label_map[action])

X = np.array(X)
y = to_categorical(y).astype(int)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

print(f"Tổng số mẫu: {len(X)}")
print(f"X_train shape: {X_train.shape}")

# ==============================
# 3. KIẾN TRÚC MODEL LSTM
# ==============================
model = Sequential([
    Input(shape=(SEQUENCE_LENGTH, FEATURE_DIM)),
    LSTM(64, return_sequences=True),
    Dropout(0.3),
    LSTM(64),
    Dropout(0.3),
    Dense(64, activation='relu'),
    Dense(len(ACTIONS), activation='softmax')
])

model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])

# ==============================
# 4. TRAINING VỚI EARLY STOPPING
# ==============================
# Model sẽ tự dừng nếu val_loss không giảm sau 15 epochs để tránh Overfitting
early_stop = EarlyStopping(monitor='val_loss', patience=15, restore_best_weights=True)

print("\n--- Bắt đầu huấn luyện... ---")
history = model.fit(
    X_train, y_train,
    epochs=100, # Để 100 vì đã có EarlyStopping lo phần dừng
    batch_size=16,
    validation_data=(X_test, y_test),
    callbacks=[early_stop]
)

# ==============================
# 5. LƯU MODEL & ĐÁNH GIÁ
# ==============================
model.save_weights("sign_lstm_weights.keras") # change the format to save here
print("\n--- Model đã được lưu: sign_lstm_model.keras ---")

# --- VẼ BIỂU ĐỒ ACCURACY & LOSS ---
plt.figure(figsize=(12, 4))

plt.subplot(1, 2, 1)
plt.plot(history.history['accuracy'], label='Train Accuracy')
plt.plot(history.history['val_accuracy'], label='Val Accuracy')
plt.title('Độ chính xác (Accuracy)')
plt.legend()

plt.subplot(1, 2, 2)
plt.plot(history.history['loss'], label='Train Loss')
plt.plot(history.history['val_loss'], label='Val Loss')
plt.title('Độ mất mát (Loss)')
plt.legend()
plt.show()

#

# --- VẼ CONFUSION MATRIX (MA TRẬN NHẦM LẪN) ---
y_pred = model.predict(X_test)
y_pred_classes = np.argmax(y_pred, axis=1)
y_true_classes = np.argmax(y_test, axis=1)

cm = confusion_matrix(y_true_classes, y_pred_classes)

plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt='d', xticklabels=ACTIONS, yticklabels=ACTIONS, cmap='Blues')
plt.xlabel('Dự đoán (Predicted)')
plt.ylabel('Thực tế (True)')
plt.title('Confusion Matrix')
plt.show()
