# MediaPipe Hands: Speed Demon Checklist 🏎️

Since you are running a **Temporal LSTM**, frame rate stability is critical. If tracking drops to 10 FPS, your 2-second gesture only contains 20 frames, which will break your 60-frame interpolation and tank accuracy.

## 1. The "Static Image Mode" Myth
Ensure `static_image_mode` is set to `False` (the default).

*   **Why**: When `False`, MediaPipe doesn't re-run the heavy "Hand Detection" model on every frame. It only does it once, then uses a lightweight "Tracking" model for subsequent frames as long as it doesn't lose your hand. This is the single biggest performance boost.

## 2. Lower Your Resolution (The 640x480 Rule)
Processing a 1080p or 4K frame is overkill for landmarks.

*   **The Fix**: Force your camera to 640x480 or even 320x240. The landmarks will still be accurate, but the math becomes 4x to 10x faster.

```python
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
```

## 3. Model Complexity: Use "Lite" (Complexity 0)
MediaPipe Hands has two models: 0 (Lite) and 1 (Full).

*   **The Trade-off**: Level 0 is significantly faster on CPUs and mobile devices with very little loss in landmark precision for sign language.

```python
with mp_hands.Hands(
    model_complexity=0, # Use 0 instead of 1
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
) as hands:
```

## 4. Implement Threaded Video Capture
By default, Python's `cap.read()` is blocking—your code stops and waits for the camera.

*   **The Fix**: Use a separate Python thread to constantly pull frames from the camera into a variable. This grab-and-go approach can boost FPS by 30-50%.

## 5. Disable "Image Writeable"
A small but effective trick in the MediaPipe Python API:

```python
image.flags.writeable = False # Tells Python not to make a copy of the image
results = hands.process(image)
image.flags.writeable = True
```

---

## 📊 Performance Impact

| Optimization | Est. FPS Gain | Impact on Accuracy |
| :--- | :--- | :--- |
| **Resolution to 640x480** | +15 FPS | Minimal |
| **Model Complexity 0** | +10 FPS | Slight (low light) |
| **Multi-threading** | +10 FPS | None |
| **Static Mode: False** | +20 FPS | None |