"""
# --- Convert sang TensorFlow Lite (quantization float16 hoặc int8) ---
converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.optimizations = [tf.lite.Optimize.DEFAULT]  # enable quantization

# Với dữ liệu float chuẩn hóa → để TensorFlow tự chọn cách tốt nhất
tflite_model = converter.convert()

# --- Lưu file .tflite ---
with open("gesture_model.tflite", "wb") as f:
    f.write(tflite_model)

print(" Đã lưu model thành gesture_model.tflite")
"""