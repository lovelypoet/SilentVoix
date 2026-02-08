Research Proposal: Event-Based Temporal Synchronization for Multimodal CV–Sensor Sign Language Data
1. Introduction & Problem Statement
Multimodal sign-language recognition systems often combine computer vision (CV) data (e.g., hand landmarks from MediaPipe) with wearable sensor data (e.g., IMU and flex sensors from a smart glove). While this fusion improves robustness and expressiveness, it introduces a fundamental challenge:
 CV data is captured as short, finite frame sequences, whereas sensor data is streamed continuously at higher and variable sampling rates.
This temporal mismatch makes direct alignment difficult. Naive solutions based on fixed frame rates or manual trimming are fragile under real-world conditions such as dropped frames, variable FPS, serial latency, and user inconsistency.

2. Objective
The objective of this research is to design a robust, low-cost, and scalable temporal synchronization method that enables reliable fusion of CV and sensor data without requiring embedded machine learning inference on the ESP32 during early system stages.

3. Proposed Method
We propose an event-based synchronization pipeline using timestamps and a shared, observable sync gesture.

3.1 Data Acquisition
Computer Vision (CV):
MediaPipe hand landmark extraction


Each frame includes:


frame_id


landmark coordinates


timestamp_ms (via performance.now() or Date.now())


Sensor (Glove):
Continuous streaming from ESP32


Each sensor packet includes:


IMU / flex values


timestamp_ms (via millis())


Sensor streaming remains always-on, independent of CV capture.

3.2 Sync Gesture Indicator
Before performing the sign, the user executes a single, sharp tap gesture (e.g., tapping the hand on a surface).
This gesture:
Produces a strong acceleration spike in IMU data


Produces a sudden displacement/velocity spike in CV landmarks


Acts as a shared temporal anchor across modalities



3.3 Offline Sync Detection & Alignment
In preprocessing (Google Colab):
Sync Event Detection


Sensor: detect acceleration magnitude peak


CV: detect wrist/hand velocity peak


Offset Computation

 offset = t_sensor_sync − t_cv_sync


Temporal Alignment


Shift one modality by the computed offset


Align both streams to a shared time axis


Trimming


Crop sensor data to the CV capture window


Discard excess samples outside the event window


Resampling


Both modalities are resampled to a fixed temporal length T


Enables consistent CV-only, sensor-only, and fusion training



4. Data Architecture
Raw data remains immutable and timestamped


Processed data is versioned and reproducible


Fusion data is derived exclusively from aligned, processed modalities


Dataset splits are modality-agnostic and sample-key based



5. Failure Handling
The pipeline explicitly detects and flags failure cases:
Missing sync event in CV or sensor


Multiple ambiguous sync peaks


Unreasonable temporal offsets


Samples with unreliable synchronization are excluded from fusion training but may remain usable for single-modality experiments.

Acceptance Rules (Offset Thresholds)
Hard rejection threshold (invalid sample). Discard or flag if any are true:
abs(offset_ms) > 2000 ms (user didn’t sync correctly)
No detectable spike in CV (no anchor)
Multiple ambiguous spikes (unreliable alignment)
CV frames < expected minimum (incomplete capture)

Soft warning threshold (manual review). Keep but mark:
500 ms < abs(offset_ms) <= 2000 ms (flag for review)
Spike detected but low confidence (keep but mark)
Sensor jitter > threshold (keep, lower trust)

Acceptable range (auto-approve):
abs(offset_ms) <= 500 ms

At 30 FPS, 1 frame ~= 33 ms, so 500 ms ~= 15 frames.

Fusion Metadata Example
{
  "cv_sync_frame": 12,
  "cv_sync_timestamp_ms": 1700001234567,
  "sensor_sync_timestamp_ms": 1700001234890,
  "offset_ms": 323,
  "frame_limit": 100,
  "sync_confidence": "high",
  "status": "accepted"
}

6. Expected Outcomes
Robust temporal alignment between CV and sensor streams


Elimination of FPS- and frame-count–dependent assumptions


Scalable multimodal dataset suitable for fusion modeling


A clean upgrade path toward heuristic or learned auto-segmentation on embedded hardware



7. Future Work
Heuristic motion-based segmentation on ESP32


Lightweight learned onset/offset detection


Fully autonomous multimodal capture


Real-time fusion inference



8. Conclusion
By reframing synchronization as an event-based temporal alignment problem, this research provides a practical and extensible solution for multimodal sign-language data capture. The proposed approach balances engineering simplicity, robustness, and scalability, making it suitable for both MVP development and future research extensions.
