import torch
import torch.nn as nn

class SignLanguageLSTM(nn.Module):
    def __init__(self, input_size=63, hidden_size=128, num_layers=2, num_classes=6):
        super().__init__()
        self.input_size = input_size
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.3)
        self.fc = nn.Linear(hidden_size, num_classes)

    def forward(self, x):
        # Handle the SilentVoix Flattened Input (1, 3780) -> (1, 60, 63)
        if x.dim() == 2 and x.size(1) == 3780:
            x = x.view(x.size(0), 60, 63)
        elif x.dim() == 2:
            x = x.unsqueeze(1) # Fallback for single frames
            
        out, _ = self.lstm(x)
        # Mean Pooling for better temporal robustness
        out = torch.mean(out, dim=1) 
        return self.fc(out)
