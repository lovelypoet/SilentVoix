#!/usr/bin/env python3
"""
Vendor the ASL sign recognizer into public/models/asl/ as ONNX.

Source: https://huggingface.co/namratha2412/asl-improved-recognition (MIT).
The repo ships only a PyTorch `state_dict` (best_model.pth) and no model
class, so the architecture below is reconstructed from the checkpoint's
parameter names and shapes. It loads with strict=True, so every weight is
accounted for. The browser runs the exported graph with onnxruntime-web
(src/composables/ai/useAslRecognizer.js), just as Emotion Studio runs FER+.

Input contract (see src/composables/ai/aslModel.js):
  landmarks: float32 [batch, frames, 126] = 2 hands x 21 MediaPipe landmarks
  x (x, y, z), raw normalized image coordinates, a missing hand = zeros.
  The frames axis is dynamic. Output: logits [batch, 77].

Usage (needs torch, numpy and onnx; onnxruntime optional, for the parity check):
  python scripts/export_asl_model.py            # skips if already exported
  python scripts/export_asl_model.py --force
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

REPO = "https://huggingface.co/namratha2412/asl-improved-recognition/resolve/main"
HERE = Path(__file__).resolve().parent
OUT_DIR = HERE.parent / "public" / "models" / "asl"
ONNX_PATH = OUT_DIR / "asl-improved.onnx"
LABELS_PATH = OUT_DIR / "labels.json"


class ImprovedASLModel(nn.Module):
    """Conv1d x2 -> 2-layer BiLSTM -> additive attention pooling -> MLP."""

    def __init__(self, input_dim=126, num_classes=77, hidden=256, drop=0.3):
        super().__init__()
        self.conv_layers = nn.Sequential(
            nn.Conv1d(input_dim, 128, 3, padding=1), nn.BatchNorm1d(128), nn.ReLU(), nn.Dropout(drop),
            nn.Conv1d(128, 256, 3, padding=1), nn.BatchNorm1d(256), nn.ReLU(), nn.Dropout(drop),
        )
        self.lstm = nn.LSTM(256, hidden, num_layers=2, batch_first=True, bidirectional=True, dropout=drop)
        self.attention = nn.Sequential(nn.Linear(2 * hidden, 128), nn.Tanh(), nn.Linear(128, 1))
        self.classifier = nn.Sequential(
            nn.Linear(2 * hidden, 512), nn.BatchNorm1d(512), nn.ReLU(), nn.Dropout(drop),
            nn.Linear(512, 256), nn.BatchNorm1d(256), nn.ReLU(), nn.Dropout(drop),
            nn.Linear(256, num_classes),
        )

    def forward(self, landmarks):
        x = self.conv_layers(landmarks.transpose(1, 2)).transpose(1, 2)
        out, _ = self.lstm(x)
        weights = torch.softmax(self.attention(out), dim=1)
        return self.classifier((weights * out).sum(dim=1))


def download(name, dest):
    print(f"Fetching {REPO}/{name}")
    urllib.request.urlretrieve(f"{REPO}/{name}", dest)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if ONNX_PATH.exists() and LABELS_PATH.exists() and not args.force:
        print(f"Already present: {ONNX_PATH}\nPass --force to re-export.")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ckpt_path = OUT_DIR / "best_model.pth"
    config_path = OUT_DIR / "model_config.json"
    download("best_model.pth", ckpt_path)
    download("model_config.json", config_path)

    labels = json.loads(config_path.read_text())["classes"]
    # weights_only=False: the checkpoint also pickles optimizer state and numpy
    # scalars, which the torch>=2.6 weights_only default refuses to load.
    checkpoint = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    model = ImprovedASLModel(num_classes=len(labels))
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.eval()

    sample = torch.rand(1, 30, 126)
    torch.onnx.export(
        model, sample, str(ONNX_PATH),
        input_names=["landmarks"], output_names=["logits"],
        dynamic_axes={"landmarks": {0: "batch", 1: "frames"}, "logits": {0: "batch"}},
        opset_version=17,
    )
    LABELS_PATH.write_text(json.dumps(labels))
    ckpt_path.unlink()
    config_path.unlink()

    # Parity check against PyTorch when onnxruntime is available.
    try:
        import onnxruntime as ort
    except ImportError:
        print("onnxruntime not installed; skipped parity check.")
    else:
        sess = ort.InferenceSession(str(ONNX_PATH))
        for frames in (8, 30, 45):
            x = torch.rand(1, frames, 126)
            with torch.no_grad():
                ref = model(x).numpy()
            got = sess.run(None, {"landmarks": x.numpy()})[0]
            diff = float(np.abs(ref - got).max())
            print(f"parity frames={frames}: max |diff| = {diff:.2e}")
            if diff > 1e-3:
                sys.exit("ONNX output diverges from PyTorch")

    print(f"Wrote {ONNX_PATH} ({ONNX_PATH.stat().st_size / 1e6:.1f} MB) and {LABELS_PATH}")


if __name__ == "__main__":
    main()
