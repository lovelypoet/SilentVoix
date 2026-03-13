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
