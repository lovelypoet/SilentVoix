import torch
import torch.nn as nn


class SignLanguageLSTM(nn.Module):
    def __init__(self, input_size=63, hidden_size=128, num_layers=2, num_classes=6):
        super().__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers

        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, num_classes)

    def forward(self, x):
        if x.dim() == 2:
            if x.size(1) != self.input_size:
                raise ValueError(f"Expected input feature size {self.input_size}, got {x.size(1)}")
            x = x.unsqueeze(1)

        if x.dim() != 3:
            raise ValueError(f"Expected 2D or 3D input, got shape {tuple(x.shape)}")

        if x.size(-1) != self.input_size:
            raise ValueError(f"Expected last dimension {self.input_size}, got {x.size(-1)}")

        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size, device=x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size, device=x.device)

        out, _ = self.lstm(x, (h0, c0))
        out = self.fc(out[:, -1, :])
        return out
