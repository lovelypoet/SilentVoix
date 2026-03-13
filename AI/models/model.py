import torch
import torch.nn as nn


class HandLSTMClassifier(nn.Module):
    """
    Runtime copy of the LSTM architecture used in training (see yolo.py).

    IMPORTANT: defaults must match the training hyperparameters used when
    saving best_model2.pth, otherwise state_dict loading will fail.
    """

    def __init__(self, feature_dim: int = 63, hidden: int = 256, num_layers: int = 2,
                 num_classes: int = 5, dropout: float = 0.3) -> None:
        super().__init__()

        self.lstm = nn.LSTM(
            feature_dim,
            hidden,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        self.dropout = nn.Dropout(dropout)
        self.ln = nn.LayerNorm(hidden)
        self.classifier = nn.Linear(hidden, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq_len, feature_dim)
        _, (h, _) = self.lstm(x)
        h_last = h[-1]  # hidden state of last LSTM layer
        h_last = self.dropout(h_last)
        h_last = self.ln(h_last)
        return self.classifier(h_last)

import torch
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
