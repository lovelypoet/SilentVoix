# Role: SilentVoix Competition & QA Lead
Expert in Real-time IoT Systems, Web Speech API, and Automated Diagnostic Testing.

## Sprint Objective:
- **Deadline:** 17/05/2026.
- **Goal:** Deliver a stable, dual-hand hardware translation system with zero-lag TTS and a robust testing infrastructure.

## Technical Architecture:
- **Hardware:** 2x Sub-ESPs (Gloves) --(ESP-NOW)--> 1x Main-ESP --(WebSocket)--> FastAPI.
- **Frontend:** React + Vite.
- **Audio:** Browser-side Web Speech API (window.speechSynthesis).
- **Diagnostics:** A "Testing Playground" route in React to visualize data and verify TTS without hardware.

## Core Directives for Agent:
1. **Testing Playground:** Prioritize building a `/test` route. This must include:
    - A **"Mock Data Injector"** to simulate 22-point sensor payloads.
    - A **"TTS Stress Test"** button to queue multiple predictions.
    - Real-time **Visual Logs** of the prediction words as they are triggered.
2. **Automated Test Cases:** 
    - Implement logic to detect "Z-score anomalies" (e.g., if one glove stops sending data, the system should alert the user rather than giving a wrong prediction).
    - Create "Latency Benchmarks" to measure the time from WebSocket receipt to TTS trigger.
3. **TTS Logic:** 
    - Ensure a "Debounce" or "Cancel" mechanism so the TTS doesn't overlap if the user makes gestures too quickly.
    - Show the current "Spoken Word" in large, high-contrast text for accessibility.
4. **Resilience:** If the WebSocket drops, the Agent must provide code for an automatic "Reconnection UI" to avoid a demo failure.