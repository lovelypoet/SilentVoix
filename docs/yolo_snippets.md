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

Here is the code to export

import json
import torch
import torch.nn as nn
import os
from google.colab import files

# --- 1. DEFINE THE ARCHITECTURE ---
class HandLSTMClassifier(nn.Module):
    def __init__(self, feature_dim=63, hidden=256, num_layers=2, num_classes=5, dropout=0.3):
        super().__init__()
        self.lstm = nn.LSTM(feature_dim, hidden, num_layers=num_layers, batch_first=True)
        self.dropout = nn.Dropout(dropout)
        self.ln = nn.LayerNorm(hidden)
        self.classifier = nn.Linear(hidden, num_classes)

    def forward(self, x):
        if x.dim() == 2 and x.size(1) == 1008:
            x = x.view(-1, 16, 63)
        _, (h, _) = self.lstm(x)
        h = h[-1]
        h = self.dropout(h)
        h = self.ln(h)
        return self.classifier(h)

# --- 2. SET YOUR METRICS (MANUAL ENTRY FOR REPORT ACCURACY) ---
# Check your previous training logs and update these numbers:
my_precision = 0.9584
my_recall = 0.9521
my_f1 = 0.9552

# --- 3. EXPORT LOGIC ---
target_weights = '/content/best_model.pth'

if os.path.exists(target_weights):
    # Load and re-save as model.pth
    model = HandLSTMClassifier()
    model.load_state_dict(torch.load(target_weights, map_location='cpu'))
    torch.save(model.state_dict(), 'model.pth')
    print("✅ Created model.pth")

    # Create metadata.json
    metadata = {
        "model_name": "SilentVoix-V2-LSTM",
        "model_family": "lstm",
        "export_format": "pytorch",
        "modality": "cv",
        "version": "2.0",
        "labels": ['Goodbye', 'Hello', 'No', 'Thank you', 'Yes'],
        "precision": float(my_precision),
        "recall": float(my_recall),
        "f1": float(my_f1),
        "input_spec": {
            "input_dim": 1008,
            "feature_dim": 63,
            "sequence_length": 16,
            "preprocess_profile": "cv_wrist_center_v1_scaled"
        }
    }
    with open('metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    print("✅ Created metadata.json")

    # Create model_def.py (The part that was missing!)
    model_def_content = """import torch
import torch.nn as nn

class HandLSTMClassifier(nn.Module):
    def __init__(self, feature_dim=63, hidden=256, num_layers=2, num_classes=5, dropout=0.3):
        super().__init__()
        self.lstm = nn.LSTM(feature_dim, hidden, num_layers=num_layers, batch_first=True)
        self.dropout = nn.Dropout(dropout)
        self.ln = nn.LayerNorm(hidden)
        self.classifier = nn.Linear(hidden, num_classes)

    def forward(self, x):
        if x.dim() == 2 and x.size(1) == 1008:
            x = x.view(-1, 16, 63)
        _, (h, _) = self.lstm(x)
        h = h[-1]
        h = self.dropout(h)
        h = self.ln(h)
        return self.classifier(h)
"""
    with open('model_def.py', 'w') as f:
        f.write(model_def_content)
    print("✅ Created model_def.py")

    # --- 4. DOWNLOAD EVERYTHING ---
    print("📦 Downloading SilentVoix Bundle...")
    for f in ['model.pth', 'metadata.json', 'model_def.py']:
        files.download(f)
else:
    print(f"❌ Error: {target_weights} not found. Ensure your training finished successfully!")
    