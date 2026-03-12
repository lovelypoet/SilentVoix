import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pickle
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay

# Vẽ biểu đồ loss và accuracy từ history của Keras
# Sử dụng sau khi train xong, truyền vào history.history
# Ví dụ: plot_history(history.history)
def plot_history(history):
    # Loss
    plt.figure(figsize=(10,4))
    plt.subplot(1,2,1)
    plt.plot(history['loss'], label='Train loss')
    if 'val_loss' in history:
        plt.plot(history['val_loss'], label='Val loss')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.title('Biểu đồ Loss')
    plt.legend()
    # Accuracy
    plt.subplot(1,2,2)
    plt.plot(history['accuracy'], label='Train acc')
    if 'val_accuracy' in history:
        plt.plot(history['val_accuracy'], label='Val acc')
    plt.xlabel('Epoch')
    plt.ylabel('Accuracy')
    plt.title('Biểu đồ Accuracy')
    plt.legend()
    plt.tight_layout()
    plt.show()

# Vẽ confusion matrix
# y_true: nhãn thật, y_pred: nhãn dự đoán, labels: list tên class
# Ví dụ: plot_confusion_matrix(y_true, y_pred, labels)
def plot_confusion_matrix(y_true, y_pred, labels):
    cm = confusion_matrix(y_true, y_pred, labels=range(len(labels)))
    plt.figure(figsize=(10,8))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=labels, yticklabels=labels)
    plt.xlabel('Dự đoán')
    plt.ylabel('Thực tế')
    plt.title('Confusion Matrix')
    plt.show()

# Hướng dẫn sử dụng:
# 1. Sau khi train, lưu lại history: np.save('history.npy', history.history)
# 2. Để vẽ: 
#    history = np.load('history.npy', allow_pickle=True).item()
#    plot_history(history)
# 3. Để vẽ confusion matrix:
#    plot_confusion_matrix(y_true, y_pred, labels) 