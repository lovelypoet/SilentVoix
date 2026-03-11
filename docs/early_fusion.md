##demo
import cv2
import mediapipe as mp
import numpy as np
import serial
import threading
import time
from tensorflow.keras.models import load_model

# ==============================
# CONFIG
# ==============================
ACTIONS = ['rest','hello','thank_you','yes','no','bye']

SEQUENCE_LENGTH = 30
FEATURE_DIM = 74

SERIAL_PORT = '/dev/ttyACM0'
BAUD = 115200

CONF_THRESHOLD = 0.8
SMOOTHING_WINDOW = 10
GESTURE_COOLDOWN = 1.0

# ==============================
# LOAD MODEL
# ==============================
model = load_model("sign_lstm_model.keras")

# ==============================
# SENSOR THREAD
# ==============================
latest_sensor = np.zeros(11)
sensor_lock = threading.Lock()

def serial_worker():

    global latest_sensor

    try:
        ser = serial.Serial(SERIAL_PORT, BAUD, timeout=0.1)
        print("Sensor connected")

        while True:

            line = ser.readline().decode('utf-8','ignore').strip()

            if not line:
                continue

            parts = line.split(',')

            if len(parts) == 12:

                try:

                    data = np.array([float(x) for x in parts[1:]])

                    with sensor_lock:
                        latest_sensor = data

                except:
                    pass

    except Exception as e:
        print("Serial error:", e)

threading.Thread(target=serial_worker, daemon=True).start()

# ==============================
# MEDIAPIPE
# ==============================
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

# ==============================
# STATE
# ==============================
sequence = []
predictions = []

last_vision = np.zeros(63)

last_gesture_time = 0
current_gesture = "rest"

# ==============================
# CAMERA
# ==============================
cap = cv2.VideoCapture(0)

with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5) as hands:

    while True:

        ret, frame = cap.read()

        if not ret:
            continue

        frame = cv2.flip(frame,1)

        rgb = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)

        results = hands.process(rgb)

        # ==============================
        # VISION
        # ==============================
        if results.multi_hand_landmarks:

            hand_landmarks = results.multi_hand_landmarks[0]

            mp_draw.draw_landmarks(
                frame,
                hand_landmarks,
                mp_hands.HAND_CONNECTIONS
            )

            lm = hand_landmarks.landmark

            vals = []

            for i in range(21):

                vals.extend([
                    lm[i].x - lm[0].x,
                    lm[i].y - lm[0].y,
                    lm[i].z - lm[0].z
                ])

            vision_vals = np.array(vals)

            last_vision = vision_vals

        else:

            vision_vals = last_vision

            cv2.putText(frame,"VISION LOST",
                        (20,80),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,(0,0,255),2)

        # ==============================
        # SENSOR
        # ==============================
        with sensor_lock:
            sensor_vals = latest_sensor.copy()

        # ==============================
        # FEATURE FUSION
        # ==============================
        feature = np.concatenate([vision_vals, sensor_vals])

        sequence.append(feature)

        if len(sequence) > SEQUENCE_LENGTH:
            sequence.pop(0)

        # ==============================
        # PREDICTION
        # ==============================
        if len(sequence) == SEQUENCE_LENGTH:

            input_data = np.expand_dims(sequence,axis=0)

            probs = model.predict(input_data,verbose=0)[0]

            pred = np.argmax(probs)

            predictions.append(pred)

            if len(predictions) > SMOOTHING_WINDOW:
                predictions.pop(0)

            smooth_pred = max(set(predictions), key=predictions.count)

            confidence = probs[smooth_pred]

            if confidence > CONF_THRESHOLD:

                gesture = ACTIONS[smooth_pred]

                now = time.time()

                if now - last_gesture_time > GESTURE_COOLDOWN:

                    current_gesture = gesture
                    last_gesture_time = now

        # ==============================
        # DISPLAY
        # ==============================
        cv2.putText(frame,
                    f"Gesture: {current_gesture}",
                    (20,40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,(0,255,0),2)

        cv2.imshow("Sign Recognition",frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()

###Collectdata
import cv2
import mediapipe as mp
import serial
import numpy as np
import os
import threading
import time
#no timestamps

# ==============================
# CONFIG
# ==============================
ACTIONS = ['rest','hello','thank_you','yes','no','bye']
NO_SEQUENCES = 30
SEQUENCE_LENGTH = 30
DATA_PATH = 'SignLanguage_Data'

TARGET_FPS = 30
FRAME_INTERVAL = 1.0 / TARGET_FPS

SERIAL_PORT = '/dev/ttyACM0'
BAUD = 115200

# ==============================
# SENSOR THREAD
# ==============================
latest_sensor = np.zeros(11, dtype=np.float32)
sensor_ready = False
sensor_lock = threading.Lock()

def serial_worker():
    global latest_sensor, sensor_ready

    try:
        ser = serial.Serial(SERIAL_PORT, BAUD, timeout=0.1)
        print("Connected to", SERIAL_PORT)

        while True:

            line = ser.readline().decode('utf-8','ignore').strip()

            if not line:
                continue

            parts = line.split(',')

            if len(parts) == 12:
                try:

                    data = np.array(
                        [float(x) for x in parts[1:]],
                        dtype=np.float32
                    )

                    with sensor_lock:
                        latest_sensor = data
                        sensor_ready = True

                except:
                    pass

    except Exception as e:
        print("Serial error:", e)

threading.Thread(target=serial_worker, daemon=True).start()

# ==============================
# MEDIAPIPE
# ==============================
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_styles = mp.solutions.drawing_styles

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_BUFFERSIZE,1)

last_vision = np.zeros(63, dtype=np.float32)

# ==============================
# MAIN
# ==============================
with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        model_complexity=1,
        min_detection_confidence=0.4,
        min_tracking_confidence=0.4) as hands:

    for action in ACTIONS:

        os.makedirs(os.path.join(DATA_PATH, action), exist_ok=True)

        for seq in range(NO_SEQUENCES):

            sequence_data = []

            # WAIT SENSOR READY
            while not sensor_ready:
                print("Waiting for sensor data...")
                time.sleep(0.5)

            # ==================
            # COUNTDOWN
            # ==================
            for i in range(3,0,-1):

                ret, frame = cap.read()
                if not ret:
                    continue

                frame = cv2.flip(frame,1)

                cv2.putText(frame,
                            f'PREPARE {action}',
                            (80,200),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1,(0,255,255),2)

                cv2.putText(frame,
                            str(i),
                            (300,300),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            3,(0,0,255),4)

                cv2.imshow("Collect Data",frame)

                if cv2.waitKey(1000) & 0xFF == ord('q'):
                    exit()

            # ==================
            # RECORD SEQUENCE
            # ==================
            while len(sequence_data) < SEQUENCE_LENGTH:

                start_time = time.time()

                ret, frame = cap.read()
                if not ret:
                    continue

                frame = cv2.flip(frame,1)

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = hands.process(rgb)

                # ==================
                # VISION
                # ==================
                if results.multi_hand_landmarks:

                    hand_landmarks = results.multi_hand_landmarks[0]

                    mp_drawing.draw_landmarks(
                        frame,
                        hand_landmarks,
                        mp_hands.HAND_CONNECTIONS,
                        mp_styles.get_default_hand_landmarks_style(),
                        mp_styles.get_default_hand_connections_style()
                    )

                    lm = hand_landmarks.landmark

                    vision_vals = []

                    for i in range(21):

                        vision_vals.extend([
                            lm[i].x - lm[0].x,
                            lm[i].y - lm[0].y,
                            lm[i].z - lm[0].z
                        ])

                    vision_vals = np.array(vision_vals, dtype=np.float32)

                    last_vision = vision_vals

                else:

                    vision_vals = last_vision

                    cv2.putText(frame,
                                "VISION LOST",
                                (50,50),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                1,(0,0,255),2)

                # ==================
                # SENSOR
                # ==================
                with sensor_lock:
                    sensor_vals = latest_sensor.copy()

                # ==================
                # FUSION
                # ==================
                full_feature = np.concatenate([
                    vision_vals,
                    sensor_vals
                ]).astype(np.float32)

                sequence_data.append(full_feature)

                # ==================
                # DISPLAY
                # ==================
                cv2.putText(frame,
                            f'{action} seq{seq} frame{len(sequence_data)}',
                            (10,30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,(0,255,0),2)

                cv2.imshow("Collect Data",frame)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    exit()

                # ==================
                # FPS CONTROL
                # ==================
                elapsed = time.time() - start_time

                if elapsed < FRAME_INTERVAL:
                    time.sleep(FRAME_INTERVAL - elapsed)

            # ==================
            # SAVE DATA
            # ==================
            save_path = os.path.join(DATA_PATH, action, f'{seq}.npz')

            np.savez_compressed(
                save_path,
                data=np.array(sequence_data, dtype=np.float32)
            )

            print("Saved:", save_path)

cap.release()
cv2.destroyAllWindows()

##training code
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

