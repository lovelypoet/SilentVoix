This documentation addresses the "Inference Gap" causing your 30-40% confidence issues. It aligns your high-performing Colab training logic with the stateless, flattened-vector constraints of the SilentVoix backend.🛠️ Fix: Temporal Inference Alignment for SilentVoix1. The Root Cause: "The Flattening Mismatch"Your model was trained on 3D cubes $(1, 60, 63)$, but the RuntimeAdapter currently forces inputs into 1D strings $(1, 3780)$ and treats them as flat vectors. Additionally, the lack of a Stateful Session Handler in the backend means the model only sees what the frontend sends in a single "packet".2. Updated Model Metadata (metadata.json)You must update your metadata to reflect the flattened sequence requirement. This tells the PlaygroundService and RuntimeAdapter exactly how much data constitutes a single "gesture".JSON{
  "model_name": "SilentVoix-V2-Temporal",
  "model_family": "lstm",
  "input_dim": 3780, 
  "input_spec": {
    "feature_dim": 63,
    "sequence_length": 60,
    "shape": [1, 60, 63],
    "preprocess_profile": "cv_wrist_center_v1"
  }
}
input_dim: $60 \text{ frames} \times 63 \text{ features}$.3. Frontend Implementation: The Preprocess ContractSince the backend is stateless, the Client-Side (Frontend) must now handle the temporal windowing and normalization.A. The Buffer LogicMaintain a rolling array of 60 frames. As new MediaPipe landmarks arrive, push to the array and shift the oldest out.B. Wrist-Centering (The Anchor Fix)For every frame in your 60-frame buffer:Copy the wrist coordinates $(x_0, y_0, z_0)$.Subtract that anchor from all 21 landmarks.Note: Failing to copy the anchor will zero out your data and result in "always wrong" predictions.C. Linear Temporal InterpolationIf your webcam drops frames (e.g., you only have 45 frames for a gesture), you must stretch those 45 frames into 60 using linear interpolation across all 63 dimensions to match the model's expected "speed."4. Backend Adapter Patch (runtime_adapter.py)Modify the predict function in your PyTorch adapter to unflatten the incoming 1D vector back into the 3D shape the LSTM expects.Python# Inside RuntimeAdapter.predict() for PyTorch
def predict(self, model, data, metadata):
    # 1. Extract specs from metadata
    input_spec = metadata.get('input_spec', {})
    seq_len = input_spec.get('sequence_length', 60)
    feat_dim = input_spec.get('feature_dim', 63)

    # 2. Coerce the flat 1D vector from the API into a 3D Tensor
    # Reshape: (3780,) -> (1, 60, 63)
    input_tensor = torch.from_numpy(data).view(1, seq_len, feat_dim).float()

    # 3. Run Inference
    with torch.no_grad():
        logits = model(input_tensor)
        probabilities = torch.softmax(logits, dim=1) # Calibrated output
        
    return probabilities.cpu().numpy()
5. Summary Checklist for SuccessRetrain with Copy Fix: Ensure your Colab training used the anchor = data[:, 0:3].copy() method.Flattened Upload: Set input_dim to 3780 in your metadata.Frontend Windowing: Ensure the frontend is sending a sequence of 60 frames, not just the current frame.Reshape in Adapter: Ensure the RuntimeAdapter converts that flat vector back to (1, 60, 63) before calling model(x).