# YOLO + LSTM Realtime Pipeline Flow

```mermaid
flowchart LR
  A[Frontend: Realtime AI Playground] -->|Server Mode: JPEG frames| B[/POST \/predict\/integrated/]
  A -->|Hybrid Mode: 63-dim features| C[/POST \/predict\/integrated\/features/]

  B --> D[GestureService]
  D --> E[YOLO detector\n(best.pt or registry)]
  E --> F[Crop ROI]
  F --> G[MediaPipe Hands]
  G --> H[Preprocess: wrist-center + pad to 63]
  H --> I[Sequence Buffer (len=16)]
  I --> J[LSTM (best_model2.pth)]
  J --> K[Prediction + confidence]

  C --> D
  D --> I

  K --> L[API Response]\n(gesture, confidence, landmarks, bbox, buffer_status)
  L --> A

  subgraph ModelArtifacts
    M1[backend/AI/models/best.pt]
    M2[backend/AI/models/best_model2.pth]
    M3[backend/AI/models/metadata6.json\n(sequence_length=16, feature_dim=63, labels)]
  end

  M1 --> E
  M2 --> J
  M3 --> D
```

Notes:
- Hybrid mode matches training preprocessing (wrist-centered, scaled) on the client.
- Buffer stays at 16/16 and slides; prediction runs each frame.
