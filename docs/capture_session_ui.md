# Capture Session Sync Graph

This document explains what the sync graph shows, how to read it, and how to use it during data matching.

## What You See

- **Green line**: Sensor acceleration magnitude (from collector log).
- **Pink line**: CV velocity magnitude (from MediaPipe landmarks).
- **Amber dashed line**: Sensor spike threshold `mean + 6σ`.
- **Pink dashed line**: CV spike threshold `mean + 5σ`.
- **Green dot**: Peak value of the sensor series in the current window.
- **Pink dot**: Peak value of the CV series in the current window.
- **Amber dot**: Sensor spike detected (requires 2 consecutive samples above threshold).
- **Pink spike dot**: CV spike detected (requires 2 consecutive samples above threshold).
- **Status text**:
  - `live` means no spike detected.
  - `spike` means at least one stream crossed its threshold.
- **ws:on / ws:off**:
  - `ws:on` means the backend WebSocket is connected.
  - `ws:off` means the backend WebSocket is not connected.
- **Expected sync time**: The time the system expects the tap/spike (from the sync cue).

## How To Use It (Quick Workflow)

1. **Start Capture Session** so the camera feed and WS stream are active.
2. **Perform the sync cue**: tap/sharp motion at the countdown end.
3. **Watch for spike**:
   - Amber dot should appear near the tap.
   - Pink spike dot should appear at roughly the same time.
4. **Proceed with the gesture** after the spike is detected.

## How To Analyze It

- **Good sync**:
  - Both sensor and CV spikes appear close together.
  - Only one clear spike per stream.
  - Threshold lines are not too close to baseline (avoids false positives).

- **Bad sync**:
  - Only one stream spikes (sensor only or CV only).
  - Multiple spikes appear (ambiguous).
  - Thresholds are too low (noise triggers spikes) or too high (no spikes).

## Troubleshooting

- **No WS**:
  - Check backend is running.
  - Confirm `/ws/sync` is reachable and `ws:on` appears.

- **No CV line**:
  - Camera not active.
  - MediaPipe not detecting the hand.

- **No sensor line**:
  - Collector not running.
  - Sensor not connected or log not updating.

- **Spikes too noisy**:
  - Reduce motion before the tap.
  - Ensure a single sharp tap only.

## Notes

- The graph shows a short rolling window (last ~60 samples).
- Sensor threshold uses `mean + 6σ`.
- CV threshold uses `mean + 5σ`.
