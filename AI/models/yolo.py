import os, glob, math, json, time, collections, random
import numpy as np
import cv2
from pathlib import Path
import torch, torch.nn as nn, torch.optim as optim
from ultralytics import YOLO
import mediapipe as mp  # MediaPipe 0.10+ Tasks API
from tqdm import tqdm
from torch.utils.data import Dataset, DataLoader
from torchvision import models, transforms
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt

def make_dirs(d):
    os.makedirs(d, exist_ok=True)

def timestamp():
    return time.strftime('%Y%m%d_%H%M%S')

# Bước 2: Keyframe - lấy mẫu đều suốt video (không chỉ 16 frame đầu)
class AdaptiveKeyframeExtractor:
    def __init__(self, target_frames=16):
        self.target_frames = target_frames

    def extract_frame_indices(self, video_path):
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()

        if total_frames <= 0:
            return []

        if total_frames >= self.target_frames:
            # Lấy đều từ đầu đến cuối video (cử chỉ có thể ở giữa/cuối)
            indices = np.linspace(0, total_frames - 1, self.target_frames, dtype=int)
            return indices.tolist()
        # Video ngắn: repeat frames
        repeat_factor = self.target_frames / total_frames
        new_indices = []
        for i in range(total_frames):
            n_repeats = max(1, int(np.ceil(repeat_factor)))
            new_indices.extend([i] * n_repeats)
        return new_indices[:self.target_frames]


import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# HAND KEYPOINT EXTRACTOR - YOLO (crop tay) + MediaPipe (keypoints)
class HandKeypointExtractor:
    def __init__(self, yolo_model_path=None, device='cpu'):
        self.feature_dim = 63  # 21 keypoints × 3 (x, y, z)
        self.device = device
        # YOLO: detect hand → crop → MediaPipe trên crop (chính xác hơn)
        self.yolo = None
        candidates = ([yolo_model_path] if yolo_model_path else []) + ["best.pt", "best (1).pt"]
        yolo_path = None
        for p in candidates:
            if p and Path(p).exists():
                yolo_path = Path(p)
                break
        if yolo_path:
            print(f"Loading YOLO hand detector: {yolo_path}")
            self.yolo = YOLO(str(yolo_path))
            self.yolo.to(device)
        else:
            print("YOLO model not found - dùng MediaPipe trên full frame (đặt best.pt trong project để dùng YOLO)")
        # MediaPipe HandLandmarker
        print("Loading MediaPipe HandLandmarker...")
        mp_path = Path("hand_landmarker.task")
        if not mp_path.exists():
            mp_path = Path(os.getcwd()) / "hand_landmarker.task"
        if not mp_path.exists():
            raise FileNotFoundError("hand_landmarker.task not found. Chạy cell tải model trước.")
        with open(mp_path, "rb") as f:
            model_bytes = f.read()
        base_options = python.BaseOptions(model_asset_buffer=model_bytes)
        options = vision.HandLandmarkerOptions(base_options=base_options, num_hands=2)
        self.landmarker = vision.HandLandmarker.create_from_options(options)

    def _crop_hand_roi(self, frame, padding=0.2, min_size=64, conf_thresh=0.3):
        """YOLO detect hand, crop ROI với padding. Return crop or full frame."""
        if self.yolo is None:
            return frame
        try:
            results = self.yolo(frame, verbose=False, conf=conf_thresh)[0]
            if results.boxes is None or len(results.boxes) == 0:
                return frame
            boxes = results.boxes
            confs = boxes.conf.cpu().numpy()
            best_idx = np.argmax(confs)
            x1, y1, x2, y2 = boxes.xyxy[best_idx].cpu().numpy()
            h, w = frame.shape[:2]
            # Thêm padding
            bw, bh = x2 - x1, y2 - y1
            pad_w = max(min_size, int(bw * padding))
            pad_h = max(min_size, int(bh * padding))
            x1 = max(0, int(x1) - pad_w)
            y1 = max(0, int(y1) - pad_h)
            x2 = min(w, int(x2) + pad_w)
            y2 = min(h, int(y2) + pad_h)
            crop = frame[y1:y2, x1:x2]
            if crop.size > 0:
                return crop
        except Exception:
            pass
        return frame

    def extract(self, frame):
        """Extract hand keypoints: YOLO crop (nếu có) → MediaPipe."""
        try:
            roi = self._crop_hand_roi(frame)
            frame_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
            frame_rgb = np.ascontiguousarray(frame_rgb)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            result = self.landmarker.detect(mp_image)
            if result.hand_landmarks and len(result.hand_landmarks) > 0:
                landmarks = result.hand_landmarks[0]
                kp = np.array([[l.x, l.y, l.z] for l in landmarks], dtype=np.float32)
                # Bước 3: Chuẩn hóa - center tại cổ tay (0), scale theo khoảng cách
                kp = kp - kp[0]
                scale = np.linalg.norm(kp[9] - kp[0]) + 1e-6  # wrist -> middle MCP
                kp = kp / scale
                return kp.flatten().astype(np.float32)
            return np.zeros(self.feature_dim, dtype=np.float32)
        except Exception as e:
            print(f"Hand keypoint extraction failed: {e}")
            return np.zeros(self.feature_dim, dtype=np.float32)

    def __del__(self):
        try:
            if hasattr(self, 'landmarker') and self.landmarker is not None and hasattr(self.landmarker, 'close'):
                self.landmarker.close()
        except Exception:
            pass


# FEATURE CACHE
class VideoFeatureCache:
    def __init__(self, cache_dir):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def cache_path(self, video_path):
        # Thêm parent (tên class) để tránh trùng khi 2 class có file cùng tên
        p = Path(video_path)
        fname = f"{p.parent.name}_{p.stem}.npy"
        return self.cache_dir / fname

    def exists(self, video_path):
        return self.cache_path(video_path).exists()

    def save(self, video_path, arr):
        try:
            np.save(str(self.cache_path(video_path)), arr)
        except Exception as e:
            print(f"Warning: Failed to save cache for {video_path}: {e}")

    def load(self, video_path):
        try:
            return np.load(str(self.cache_path(video_path)))
        except Exception as e:
            print(f"Warning: Failed to load cache for {video_path}: {e}")
            return None

# FEATURE EXTRACTION
def precompute_keypoint_features_adaptive(videos, extractor, cache, seq_length=16):
    """Pre-extract hand keypoint features using MediaPipe pipeline"""

    print("\n" + "="*60)
    print("KEYFRAME EXTRACTION + HAND FEATURE (YOLO crop + MediaPipe)")
    print("="*60)

    keyframe_extractor = AdaptiveKeyframeExtractor(target_frames=seq_length)
    feature_dim = extractor.feature_dim
    videos_to_process = [v for v in videos if not cache.exists(v)]

    if len(videos_to_process) == 0:
        print("All features already cached!")
        return

    print(f"Processing {len(videos_to_process)} videos...\n")

    for video_path in tqdm(videos_to_process, desc="Extracting features"):
        try:
            # Get frame indices
            frame_indices = keyframe_extractor.extract_frame_indices(video_path)

            # Extract features from selected frames
            cap = cv2.VideoCapture(video_path)
            feats = []

            for frame_idx in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ok, frame = cap.read()

                if not ok:
                    break

                # Extract hand keypoints using MediaPipe
                feat = extractor.extract(frame)
                feats.append(feat)

            cap.release()

            # Pad if needed
            if len(feats) < seq_length:
                if len(feats) == 0:
                    feats = [np.zeros(feature_dim, dtype=np.float32)] * seq_length
                else:
                    last = feats[-1]
                    while len(feats) < seq_length:
                        feats.append(last.copy())

            arr = np.stack(feats[:seq_length], axis=0).astype(np.float32)
            cache.save(video_path, arr)

        except Exception as e:
            print(f"\nError: {video_path}: {e}")
            zero_features = np.zeros((seq_length, feature_dim), dtype=np.float32)
            cache.save(video_path, zero_features)

    print("\nFeature extraction complete")


class HandDataset(Dataset):
    def __init__(self, videos, labels, cache, seq_length=16,
                 augment=False, feature_dim=63):
        self.videos = videos
        self.labels = labels
        self.cache = cache
        self.seq_length = seq_length
        self.augment = augment
        self.feature_dim = feature_dim

    def __len__(self):
        return len(self.videos)

    # RANDOM MASKING AUGMENTATION for hand keypoints
    def random_keypoint_masking(self, features, mask_prob=0.15, mask_strategy='random'):
        """
        Randomly mask hand keypoints to simulate occlusion and improve robustness.

        Args:
            features: (seq_len, 63) array of hand keypoint features
            mask_prob: Probability of masking each keypoint (0.0-1.0)
            mask_strategy: 'random', 'finger', 'temporal', or 'mixed'

        Returns:
            Masked features
        """
        features = features.copy()
        seq_len = features.shape[0]

        if mask_strategy == 'random':
            # Random individual keypoint masking
            for t in range(seq_len):
                frame = features[t].reshape(21, 3)  # 21 keypoints × 3 values

                for kp_idx in range(21):
                    if random.random() < mask_prob:
                        frame[kp_idx] = [0, 0, 0]

                features[t] = frame.flatten()

        elif mask_strategy == 'finger':
            # Mask entire fingers (groups of keypoints)
            # MediaPipe hand structure: 0=wrist, 1-4=thumb, 5-8=index, 9-12=middle, 13-16=ring, 17-20=pinky
            finger_groups = {
                'thumb': [1, 2, 3, 4],
                'index': [5, 6, 7, 8],
                'middle': [9, 10, 11, 12],
                'ring': [13, 14, 15, 16],
                'pinky': [17, 18, 19, 20]
            }

            for t in range(seq_len):
                frame = features[t].reshape(21, 3)

                # Randomly mask 0-2 fingers per frame
                n_fingers_to_mask = random.randint(0, 2)
                fingers_to_mask = random.sample(list(finger_groups.keys()), n_fingers_to_mask)

                for finger_name in fingers_to_mask:
                    for kp_idx in finger_groups[finger_name]:
                        frame[kp_idx] = [0, 0, 0]

                features[t] = frame.flatten()

        elif mask_strategy == 'temporal':
            # Choose 1-3 keypoints to mask temporally
            n_keypoints = random.randint(1, 3)
            keypoints_to_mask = random.sample(range(21), n_keypoints)

            for kp_idx in keypoints_to_mask:
                # Mask for 2-5 consecutive frames
                mask_duration = random.randint(2, 5)
                start_frame = random.randint(0, max(0, seq_len - mask_duration))

                for t in range(start_frame, min(start_frame + mask_duration, seq_len)):
                    frame = features[t].reshape(21, 3)
                    frame[kp_idx] = [0, 0, 0]
                    features[t] = frame.flatten()

        elif mask_strategy == 'mixed':
            # Combine all strategies with random selection
            strategy = random.choice(['random', 'finger', 'temporal'])
            return self.random_keypoint_masking(features, mask_prob, strategy)

        return features

    def temporal_augmentation(self, features):
        """Apply temporal augmentation to feature sequence."""
        seq_len = features.shape[0]

        # Random temporal shift (±20% of sequence)
        if random.random() < 0.5:
            shift = random.randint(-seq_len // 5, seq_len // 5)
            if shift > 0:
                features = np.concatenate([
                    np.repeat(features[0:1], shift, axis=0),
                    features[:-shift]
                ], axis=0)
            elif shift < 0:
                features = np.concatenate([
                    features[-shift:],
                    np.repeat(features[-1:], -shift, axis=0)
                ], axis=0)

        # Random temporal dropout (drop 1-2 frames, duplicate neighbors)
        if random.random() < 0.3:
            num_drops = random.randint(1, 2)
            for _ in range(num_drops):
                drop_idx = random.randint(1, seq_len - 2)
                features[drop_idx] = (features[drop_idx-1] + features[drop_idx+1]) / 2

        # Random temporal reverse (for symmetric actions)
        if random.random() < 0.2:
            features = features[::-1].copy()

        return features

    def add_feature_noise(self, x, std=0.01):
        noise = np.random.normal(0, std, x.shape).astype(np.float32)
        return x + noise

    def frame_dropout(self, x, max_drops=3):
        L = x.shape[0]
        drops = random.randint(1, max_drops)
        idxs = np.random.choice(L, drops, replace=False)
        x[idxs] = 0
        return x

    def __getitem__(self, idx):
        v = self.videos[idx]

        # Load from cache
        x = self.cache.load(v)

        if x is None:
            print(f"Warning: Cache missing for {v}, using zeros")
            x = np.zeros((self.seq_length, self.feature_dim), dtype=np.float32)

        # Apply augmentation during training
        if self.augment:
            if random.random() < 0.5:
                mask_strategy = random.choice(['random', 'finger', 'temporal', 'mixed'])
                mask_prob = random.uniform(0.1, 0.2)
                x = self.random_keypoint_masking(x, mask_prob, mask_strategy)

            x = self.temporal_augmentation(x)

            if random.random() < 0.5:
                x = self.add_feature_noise(x, std=0.02)

            if random.random() < 0.3:
                x = self.frame_dropout(x)

        y = int(self.labels[idx])
        return torch.tensor(x, dtype=torch.float32), torch.tensor(y, dtype=torch.long)

# FEATURE CACHE
class VideoFeatureCache:
    def __init__(self, cache_dir):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def cache_path(self, video_path):
        p = Path(video_path)
        fname = f"{p.parent.name}_{p.stem}.npy"
        return self.cache_dir / fname

    def exists(self, video_path):
        return self.cache_path(video_path).exists()

    def save(self, video_path, arr):
        try:
            np.save(str(self.cache_path(video_path)), arr)
        except Exception as e:
            print(f"Warning: Failed to save cache for {video_path}: {e}")

    def load(self, video_path):
        try:
            return np.load(str(self.cache_path(video_path)))
        except Exception as e:
            print(f"Warning: Failed to load cache for {video_path}: {e}")
            return None

# FEATURE EXTRACTION
def precompute_keypoint_features_adaptive(videos, extractor, cache, seq_length=16):
    """Pre-extract hand keypoint features using MediaPipe pipeline"""

    print("\n" + "="*60)
    print("KEYFRAME EXTRACTION + HAND FEATURE (YOLO crop + MediaPipe)")
    print("="*60)

    keyframe_extractor = AdaptiveKeyframeExtractor(target_frames=seq_length)
    feature_dim = extractor.feature_dim
    videos_to_process = [v for v in videos if not cache.exists(v)]

    if len(videos_to_process) == 0:
        print("All features already cached!")
        return

    print(f"Processing {len(videos_to_process)} videos...\n")

    for video_path in tqdm(videos_to_process, desc="Extracting features"):
        try:
            # Get frame indices
            frame_indices = keyframe_extractor.extract_frame_indices(video_path)

            # Extract features from selected frames
            cap = cv2.VideoCapture(video_path)
            feats = []

            for frame_idx in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ok, frame = cap.read()

                if not ok:
                    break

                # Extract hand keypoints using MediaPipe
                feat = extractor.extract(frame)
                feats.append(feat)

            cap.release()

            # Pad if needed
            if len(feats) < seq_length:
                if len(feats) == 0:
                    feats = [np.zeros(feature_dim, dtype=np.float32)] * seq_length
                else:
                    last = feats[-1]
                    while len(feats) < seq_length:
                        feats.append(last.copy())

            arr = np.stack(feats[:seq_length], axis=0).astype(np.float32)
            cache.save(video_path, arr)

        except Exception as e:
            print(f"\nError: {video_path}: {e}")
            zero_features = np.zeros((seq_length, feature_dim), dtype=np.float32)
            cache.save(video_path, zero_features)

    print("\nFeature extraction complete")

class HandDataset(Dataset):
    def __init__(self, videos, labels, cache, seq_length=16,
                 augment=False, feature_dim=63):
        self.videos = videos
        self.labels = labels
        self.cache = cache
        self.seq_length = seq_length
        self.augment = augment
        self.feature_dim = feature_dim

    def __len__(self):
        return len(self.videos)

    # RANDOM MASKING AUGMENTATION for hand keypoints
    def random_keypoint_masking(self, features, mask_prob=0.15, mask_strategy='random'):
        """
        Randomly mask hand keypoints to simulate occlusion and improve robustness.

        Args:
            features: (seq_len, 63) array of hand keypoint features
            mask_prob: Probability of masking each keypoint (0.0-1.0)
            mask_strategy: 'random', 'finger', 'temporal', or 'mixed'

        Returns:
            Masked features
        """
        features = features.copy()
        seq_len = features.shape[0]

        if mask_strategy == 'random':
            # Random individual keypoint masking
            for t in range(seq_len):
                frame = features[t].reshape(21, 3)  # 21 keypoints × 3 values

                for kp_idx in range(21):
                    if random.random() < mask_prob:
                        frame[kp_idx] = [0, 0, 0]

                features[t] = frame.flatten()

        elif mask_strategy == 'finger':
            # Mask entire fingers (groups of keypoints)
            # MediaPipe hand structure: 0=wrist, 1-4=thumb, 5-8=index, 9-12=middle, 13-16=ring, 17-20=pinky
            finger_groups = {
                'thumb': [1, 2, 3, 4],
                'index': [5, 6, 7, 8],
                'middle': [9, 10, 11, 12],
                'ring': [13, 14, 15, 16],
                'pinky': [17, 18, 19, 20]
            }

            for t in range(seq_len):
                frame = features[t].reshape(21, 3)

                # Randomly mask 0-2 fingers per frame
                n_fingers_to_mask = random.randint(0, 2)
                fingers_to_mask = random.sample(list(finger_groups.keys()), n_fingers_to_mask)

                for finger_name in fingers_to_mask:
                    for kp_idx in finger_groups[finger_name]:
                        frame[kp_idx] = [0, 0, 0]

                features[t] = frame.flatten()

        elif mask_strategy == 'temporal':
            # Choose 1-3 keypoints to mask temporally
            n_keypoints = random.randint(1, 3)
            keypoints_to_mask = random.sample(range(21), n_keypoints)

            for kp_idx in keypoints_to_mask:
                # Mask for 2-5 consecutive frames
                mask_duration = random.randint(2, 5)
                start_frame = random.randint(0, max(0, seq_len - mask_duration))

                for t in range(start_frame, min(start_frame + mask_duration, seq_len)):
                    frame = features[t].reshape(21, 3)
                    frame[kp_idx] = [0, 0, 0]
                    features[t] = frame.flatten()

        elif mask_strategy == 'mixed':
            # Combine all strategies with random selection
            strategy = random.choice(['random', 'finger', 'temporal'])
            return self.random_keypoint_masking(features, mask_prob, strategy)

        return features

    def temporal_augmentation(self, features):
        """Apply temporal augmentation to feature sequence."""
        seq_len = features.shape[0]

        # Random temporal shift (±20% of sequence)
        if random.random() < 0.5:
            shift = random.randint(-seq_len // 5, seq_len // 5)
            if shift > 0:
                features = np.concatenate([
                    np.repeat(features[0:1], shift, axis=0),
                    features[:-shift]
                ], axis=0)
            elif shift < 0:
                features = np.concatenate([
                    features[-shift:],
                    np.repeat(features[-1:], -shift, axis=0)
                ], axis=0)

        # Random temporal dropout (drop 1-2 frames, duplicate neighbors)
        if random.random() < 0.3:
            num_drops = random.randint(1, 2)
            for _ in range(num_drops):
                drop_idx = random.randint(1, seq_len - 2)
                features[drop_idx] = (features[drop_idx-1] + features[drop_idx+1]) / 2

        # Random temporal reverse (for symmetric actions)
        if random.random() < 0.2:
            features = features[::-1].copy()

        return features

    def add_feature_noise(self, x, std=0.01):
        noise = np.random.normal(0, std, x.shape).astype(np.float32)
        return x + noise

    def frame_dropout(self, x, max_drops=3):
        L = x.shape[0]
        drops = random.randint(1, max_drops)
        idxs = np.random.choice(L, drops, replace=False)
        x[idxs] = 0
        return x

    def __getitem__(self, idx):
        v = self.videos[idx]

        # Load from cache
        x = self.cache.load(v)

        if x is None:
            print(f"Warning: Cache missing for {v}, using zeros")
            x = np.zeros((self.seq_length, self.feature_dim), dtype=np.float32)

        # Apply augmentation during training
        if self.augment:
            if random.random() < 0.5:
                mask_strategy = random.choice(['random', 'finger', 'temporal', 'mixed'])
                mask_prob = random.uniform(0.1, 0.2)
                x = self.random_keypoint_masking(x, mask_prob, mask_strategy)

            x = self.temporal_augmentation(x)

            if random.random() < 0.5:
                x = self.add_feature_noise(x, std=0.02)

            if random.random() < 0.3:
                x = self.frame_dropout(x)

        y = int(self.labels[idx])
        return torch.tensor(x, dtype=torch.float32), torch.tensor(y, dtype=torch.long)

    # LSTM

import os, glob, math, json, time, collections, random
import numpy as np
import cv2
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from tqdm import tqdm
from sklearn.metrics import classification_report, confusion_matrix, precision_recall_fscore_support, balanced_accuracy_score, roc_auc_score, log_loss, roc_curve

# UTILS
def make_dirs(d):
    os.makedirs(d, exist_ok=True)

def timestamp():
    return time.strftime('%Y%m%d_%H%M%S')

# FIX RANDOM SEED
def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

# LSTM MODEL
class HandLSTMClassifier(nn.Module):
    def __init__(self, feature_dim=63, hidden=128, num_layers=1,
                 num_classes=5, dropout=0.3):
        super().__init__()

        self.lstm = nn.LSTM(
            feature_dim,
            hidden,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0
        )

        self.dropout = nn.Dropout(dropout)
        self.ln = nn.LayerNorm(hidden)
        self.classifier = nn.Linear(hidden, num_classes)

    def forward(self, x):
        _, (h, _) = self.lstm(x)
        h = h[-1]  # Get hidden state of last layer
        h = self.dropout(h)
        h = self.ln(h)
        return self.classifier(h)

# EARLY STOPPING
class EarlyStopping:
    def __init__(self, patience=20, min_delta=0.0, mode='min'):
        self.patience = patience
        self.min_delta = min_delta
        self.mode = mode
        self.best_score = None
        self.counter = 0
        self.early_stop = False

    def __call__(self, score):
        if self.best_score is None:
            self.best_score = score
            return False

        improved = (
            score < self.best_score - self.min_delta
            if self.mode == 'min'
            else score > self.best_score + self.min_delta
        )

        if improved:
            self.best_score = score
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.early_stop = True

        return self.early_stop

# DATA LOADING
def list_videos(root, classes):
    vids, labels, counts = [], [], {}
    for ci, cname in enumerate(classes):
        p = Path(root) / cname
        if not p.exists():
            print(f"Warning: {p} does not exist")
            counts[cname] = 0
            continue
        files = (
            list(p.glob('*.mp4')) +
            list(p.glob('*.avi')) +
            list(p.glob('*.MOV'))
        )
        vids.extend([str(f) for f in files])
        labels.extend([ci] * len(files))
        counts[cname] = len(files)
    return vids, labels, counts

# PLOTTING
def plot_training_history(history):
    for key in ['train_loss', 'val_loss', 'train_acc', 'val_acc', 'val_bal_acc', 'val_f1_macro', 'val_f1_weighted', 'val_entropy']:
        plt.figure(figsize=(8, 4))
        plt.plot(history[key], linewidth=2)
        plt.title(key.replace('_', ' ').title())
        plt.xlabel("Epoch")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

def plot_confusion_matrix(cm, classes):
    import seaborn as sns
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=classes, yticklabels=classes,
                cbar_kws={'label': 'Count'}, ax=ax)
    ax.set_xlabel('Predicted Label', fontsize=12, fontweight='bold')
    ax.set_ylabel('True Label', fontsize=12, fontweight='bold')
    ax.set_title('Confusion Matrix', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.show()

def plot_roc_curve(labels, probs, class_names):
    # For multi-class, plot one-vs-rest ROC for each class
    from sklearn.preprocessing import label_binarize
    n_classes = len(class_names)
    labels_bin = label_binarize(labels, classes=range(n_classes))

    plt.figure(figsize=(10, 8))
    for i in range(n_classes):
        fpr, tpr, _ = roc_curve(labels_bin[:, i], probs[:, i])
        auc_score = roc_auc_score(labels_bin[:, i], probs[:, i])
        plt.plot(fpr, tpr, linewidth=2, label=f"{class_names[i]} (AUC = {auc_score:.4f})")

    plt.plot([0, 1], [0, 1], linestyle='--', linewidth=1, label="Random")
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title("ROC Curve (One-vs-Rest)")
    plt.legend(loc="lower right")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

# TRAINING FUNCTION
def train_adaptive_model(params):
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"\nUsing device: {device}")

    # LOAD DATA
    print("\nLoading TRAIN data...")
    train_vids, train_labels, train_counts = list_videos(
        params['train_data_root'], params['classes']
    )
    print("Train:", train_counts)

    print("\nLoading VALIDATION data...")
    val_vids, val_labels, val_counts = list_videos(
        params['val_data_root'], params['classes']
    )
    print("Validation:", val_counts)

    print("\nLoading TEST data...")
    test_vids, test_labels, test_counts = list_videos(
        params['test_data_root'], params['classes']
    )
    print("Test:", test_counts)

    # Nếu Test quá ít mẫu (<20) → split từ Train (80/10/10), dùng chung cache
    n_test = sum(test_counts.values())
    use_split_cache = False
    if n_test < 20 and len(train_vids) > 0:
        print(f"\n⚠ Test chỉ có {n_test} mẫu. Split từ Train (80/10/10)...")
        from sklearn.model_selection import train_test_split
        tv, tl = train_vids, train_labels
        tr_v, rest_v, tr_l, rest_l = train_test_split(tv, tl, test_size=0.2, stratify=tl, random_state=42)
        val_v, test_v, val_l, test_l = train_test_split(rest_v, rest_l, test_size=0.5, stratify=rest_l, random_state=42)
        train_vids, train_labels = tr_v, tr_l
        val_vids, val_labels = val_v, val_l
        test_vids, test_labels = test_v, test_l
        use_split_cache = True
        print(f"  Train: {len(train_vids)}, Val: {len(val_vids)}, Test: {len(test_vids)}")

    # FEATURE EXTRACTION (CACHED)
    extractor = HandKeypointExtractor(
        yolo_model_path=params['yolo_model_path'],
        device=device
    )
    train_cache = VideoFeatureCache(params['train_cache_dir'])
    val_cache   = VideoFeatureCache(params['train_cache_dir'] if use_split_cache else params['val_cache_dir'])
    test_cache  = VideoFeatureCache(params['train_cache_dir'] if use_split_cache else params['test_cache_dir'])

    precompute_keypoint_features_adaptive(
        train_vids, extractor, train_cache,
        seq_length=params['seq_length']
    )

    precompute_keypoint_features_adaptive(
        val_vids, extractor, val_cache,
        seq_length=params['seq_length']
    )

    precompute_keypoint_features_adaptive(
        test_vids, extractor, test_cache,
        seq_length=params['seq_length']
    )

    del extractor
    if device == 'cuda':
        torch.cuda.empty_cache()

    # DATASETS & LOADERS
    train_ds = HandDataset(
        train_vids, train_labels, train_cache,
        seq_length=params['seq_length'],
        augment=True, feature_dim=63
    )

    val_ds = HandDataset(
        val_vids, val_labels, val_cache,
        seq_length=params['seq_length'],
        augment=False, feature_dim=63
    )

    test_ds = HandDataset(
        test_vids, test_labels, test_cache,
        seq_length=params['seq_length'],
        augment=False, feature_dim=63
    )

    # Revert: class weights + sampler làm tệ hơn. Dùng shuffle thường.
    train_loader = DataLoader(train_ds, batch_size=params['batch_size'], shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=params['batch_size'], shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=params['batch_size'], shuffle=False)

    # MODEL
    model = HandLSTMClassifier(
        feature_dim=63,
        hidden=params['hidden_size'],
        num_layers=params['num_layers'],
        num_classes=len(params['classes']),
        dropout=params['dropout_rate']
    ).to(device)

    optimizer = optim.AdamW(model.parameters(), lr=params['lr'], weight_decay=0.01)
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=15)

    history = {
        'train_loss': [], 'val_loss': [], 'train_acc': [], 'val_acc': [],
        'val_bal_acc': [], 'val_f1_macro': [], 'val_f1_weighted': [], 'val_entropy': []
    }
    best_val_loss = float('inf')
    best_train_acc, best_val_acc = 0.0, 0.0

    # TRAIN LOOP
    for epoch in range(params['epochs']):
        print(f"\nEpoch {epoch+1}/{params['epochs']}")

        model.train()
        total_loss, correct, total = 0, 0, 0

        for X, y in tqdm(train_loader, desc="Training", leave=False):
            X, y = X.to(device), y.to(device)
            optimizer.zero_grad()

            out = model(X)
            loss = criterion(out, y)
            loss.backward()
            optimizer.step()

            total_loss += loss.item()
            correct += (out.argmax(1) == y).sum().item()
            total += y.size(0)

        train_loss = total_loss / len(train_loader)
        train_acc = correct / total
        best_train_acc = max(best_train_acc, train_acc)

        model.eval()
        val_loss, v_correct, v_total = 0, 0, 0
        val_preds, val_labels_list, val_probs = [], [], []

        with torch.no_grad():
            for X, y in val_loader:
                X, y = X.to(device), y.to(device)
                out = model(X)
                prob = torch.softmax(out, dim=1)

                loss = criterion(out, y)
                val_loss += loss.item()
                v_correct += (out.argmax(1) == y).sum().item()
                v_total += y.size(0)

                val_preds.extend(out.argmax(1).cpu().numpy())
                val_labels_list.extend(y.cpu().numpy())
                val_probs.extend(prob.cpu().numpy())

        val_loss /= len(val_loader)
        val_acc = v_correct / v_total
        best_val_acc = max(best_val_acc, val_acc)

        # Metrics
        val_preds = np.array(val_preds)
        val_labels_list = np.array(val_labels_list)
        val_probs = np.array(val_probs)

        val_bal_acc = balanced_accuracy_score(val_labels_list, val_preds)
        _, _, val_f1_macro, _ = precision_recall_fscore_support(
            val_labels_list, val_preds, average='macro'
        )
        _, _, val_f1_weighted, _ = precision_recall_fscore_support(
            val_labels_list, val_preds, average='weighted'
        )
        val_entropy = (-np.sum(val_probs * np.log(val_probs + 1e-8), axis=1)).mean()

        history['train_loss'].append(train_loss)
        history['val_loss'].append(val_loss)
        history['train_acc'].append(train_acc)
        history['val_acc'].append(val_acc)
        history['val_bal_acc'].append(val_bal_acc)
        history['val_f1_macro'].append(val_f1_macro)
        history['val_f1_weighted'].append(val_f1_weighted)
        history['val_entropy'].append(val_entropy)

        print(f"Train Loss: {train_loss:.4f} | Acc: {train_acc*100:.2f}%")
        print(f"Val   Loss: {val_loss:.4f} | Acc: {val_acc*100:.2f}%")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), params['out_dir'] + '/best_model.pth')
            print(" Saved best model")

        scheduler.step(val_loss)

    # TEST
    model.load_state_dict(torch.load(params['out_dir'] + '/best_model.pth'))
    model.eval()

    test_preds, test_labels_list, test_probs = [], [], []

    with torch.no_grad():
        for X, y in test_loader:
            X, y = X.to(device), y.to(device)
            out = model(X)
            prob = torch.softmax(out, dim=1)

            test_preds.extend(out.argmax(1).cpu().numpy())
            test_labels_list.extend(y.cpu().numpy())
            test_probs.extend(prob.cpu().numpy())

    labels = np.array(test_labels_list)
    preds  = np.array(test_preds)
    probs  = np.array(test_probs)

    test_acc = (preds == labels).mean()

    print("\nTEST RESULT")
    n_classes = len(params['classes'])
    class_labels = list(range(n_classes))
    print(classification_report(labels, preds, labels=class_labels, target_names=params['classes']))
    print("\nBEST ACCURACY SUMMARY")
    print(f"Best Train Accuracy      : {best_train_acc * 100:.2f}%")
    print(f"Best Validation Accuracy : {best_val_acc * 100:.2f}%")
    print(f"Test Accuracy            : {test_acc * 100:.2f}%")

    # More metrics
    precision_macro, recall_macro, f1_macro, _ = precision_recall_fscore_support(
        labels, preds, average='macro'
    )
    precision_weighted, recall_weighted, f1_weighted, _ = precision_recall_fscore_support(
        labels, preds, average='weighted'
    )

    # ROC-AUC (multi-class)
    from sklearn.preprocessing import label_binarize
    labels_bin = label_binarize(labels, classes=range(len(params['classes'])))
    roc_auc = roc_auc_score(labels_bin, probs, average='macro', multi_class='ovr')

    test_log_loss = log_loss(labels, probs, labels=class_labels)
    entropy = -np.sum(probs * np.log(probs + 1e-8), axis=1)
    mean_entropy = entropy.mean()

    print(f"\nAdditional Metrics:")
    print(f"Precision (macro)    : {precision_macro:.4f}")
    print(f"Recall (macro)      : {recall_macro:.4f}")
    print(f"F1 (macro)          : {f1_macro:.4f}")
    print(f"F1 (weighted)       : {f1_weighted:.4f}")
    print(f"ROC-AUC (macro)     : {roc_auc:.4f}")
    print(f"Log Loss            : {test_log_loss:.4f}")
    print(f"Mean Entropy        : {mean_entropy:.4f}")

    cm = confusion_matrix(labels, preds)
    print("\nConfusion Matrix:\n", cm)
    plot_confusion_matrix(cm, params['classes'])
    plot_roc_curve(labels, probs, params['classes'])
    plot_training_history(history)

    return model, history

if __name__ == '__main__':
    set_seed(42)

    params = {
        'lr': 0.001,
        'batch_size': 32,
        'hidden_size': 256,
        'dropout_rate': 0.3,  # 0.6 quá cao -> khó học
        'num_layers': 2,
        'epochs': 150,
        'seq_length': 16,
        'classes': ['Goodbye', 'Hello', 'No', 'Thank you', 'Yes'],
        'train_data_root': 'DatasetVidSign',  # Colab: /content/drive/MyDrive/DatasetVidSign
        'val_data_root': r'DatasetVidSign/Validation',
        'test_data_root': r'DatasetVidSign/Test',
        'yolo_model_path': 'best.pt',  # Đặt best.pt trong project. Nếu mới thêm: xóa cache_train/val/test rồi chạy lại
        'out_dir': 'keypoint_experiments',
        'train_cache_dir': 'cache_train',
        'val_cache_dir': 'cache_val',
        'test_cache_dir': 'cache_test',
    }

    make_dirs(params['out_dir'])
    make_dirs(params['train_cache_dir'])
    make_dirs(params['val_cache_dir'])
    make_dirs(params['test_cache_dir'])

    model, history = train_adaptive_model(params)