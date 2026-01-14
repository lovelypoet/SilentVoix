"""
Dual-Hand Model Training Script
-------------------------------
Trains a TensorFlow model on dual-hand sensor data (22 inputs total)
"""

import pandas as pd
import numpy as np
import tensorflow as tf
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns
import json
import os
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DualHandModelTrainer:
    def __init__(self, data_path: str = None):
        self.data_path = data_path or "data/dual_hand_raw_data.csv"
        self.model = None
        self.history = None
        self.label_encoder = LabelEncoder()
        
    def load_and_prepare_data(self) -> tuple:
        """Load and prepare dual-hand data for training"""
        try:
            logger.info(f"Loading data from {self.data_path}")
            
            if not os.path.exists(self.data_path):
                raise FileNotFoundError(f"Data file not found: {self.data_path}")
            
            # Load CSV data
            df = pd.read_csv(self.data_path)
            logger.info(f"Loaded {len(df)} samples")
            
            # Extract features (22 sensor values)
            feature_columns = []
            for i in range(1, 6):  # Left hand flex sensors
                feature_columns.append(f'left_flex_{i}')
            for i in range(1, 4):  # Left hand accelerometer
                feature_columns.append(f'left_acc_{i}')
            for i in range(1, 4):  # Left hand gyroscope
                feature_columns.append(f'left_gyro_{i}')
            for i in range(1, 6):  # Right hand flex sensors
                feature_columns.append(f'right_flex_{i}')
            for i in range(1, 4):  # Right hand accelerometer
                feature_columns.append(f'right_acc_{i}')
            for i in range(1, 4):  # Right hand gyroscope
                feature_columns.append(f'right_gyro_{i}')
            
            # Verify we have 22 features
            if len(feature_columns) != 22:
                raise ValueError(f"Expected 22 features, got {len(feature_columns)}")
            
            # Extract features and labels
            X = df[feature_columns].values
            y = df['label'].values
            
            logger.info(f"Features shape: {X.shape}")
            logger.info(f"Labels: {np.unique(y)}")
            
            # Normalize features (0-1 range)
            X = X.astype(np.float32) / 4095.0  # Assuming 12-bit ADC (0-4095)
            
            # Encode labels
            y_encoded = self.label_encoder.fit_transform(y)
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
            )
            
            logger.info(f"Training set: {X_train.shape}")
            logger.info(f"Test set: {X_test.shape}")
            
            return X_train, X_test, y_train, y_test
            
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            raise
    
    def create_model(self, input_shape: tuple, num_classes: int) -> tf.keras.Model:
        """Create a neural network model for dual-hand gesture recognition"""
        
        model = tf.keras.Sequential([
            # Input layer - 22 features
            tf.keras.layers.Input(shape=input_shape),
            
            # Dense layers with dropout for regularization
            tf.keras.layers.Dense(128, activation='relu'),
            tf.keras.layers.Dropout(0.3),
            tf.keras.layers.Dense(64, activation='relu'),
            tf.keras.layers.Dropout(0.3),
            tf.keras.layers.Dense(32, activation='relu'),
            tf.keras.layers.Dropout(0.2),
            
            # Output layer
            tf.keras.layers.Dense(num_classes, activation='softmax')
        ])
        
        # Compile model
        model.compile(
            optimizer='adam',
            loss='sparse_categorical_crossentropy',
            metrics=['accuracy']
        )
        
        logger.info("Model created successfully")
        model.summary()
        
        return model
    
    def train_model(self, X_train: np.ndarray, y_train: np.ndarray, 
                   X_test: np.ndarray, y_test: np.ndarray) -> dict:
        """Train the dual-hand model"""
        
        # Create model
        input_shape = (X_train.shape[1],)  # (22,)
        num_classes = len(np.unique(y_train))
        
        self.model = self.create_model(input_shape, num_classes)
        
        # Early stopping to prevent overfitting
        early_stopping = tf.keras.callbacks.EarlyStopping(
            monitor='val_loss',
            patience=10,
            restore_best_weights=True
        )
        
        # Train model
        logger.info("Starting model training...")
        self.history = self.model.fit(
            X_train, y_train,
            validation_data=(X_test, y_test),
            epochs=100,
            batch_size=32,
            callbacks=[early_stopping],
            verbose=1
        )
        
        # Evaluate model
        test_loss, test_accuracy = self.model.evaluate(X_test, y_test, verbose=0)
        logger.info(f"Test accuracy: {test_accuracy:.4f}")
        
        return {
            'test_accuracy': test_accuracy,
            'test_loss': test_loss,
            'num_classes': num_classes,
            'input_features': X_train.shape[1]
        }
    
    def save_model(self, output_path: str = None) -> str:
        """Save the trained model as TFLite"""
        if self.model is None:
            raise ValueError("No trained model to save")
        
        if output_path is None:
            output_path = "AI/gesture_model_dual.tflite"
        
        # Convert to TFLite
        converter = tf.lite.TFLiteConverter.from_keras_model(self.model)
        tflite_model = converter.convert()
        
        # Save model
        with open(output_path, 'wb') as f:
            f.write(tflite_model)
        
        logger.info(f"Model saved to {output_path}")
        return output_path
    
    def generate_metrics(self, X_test: np.ndarray, y_test: np.ndarray, 
                        output_dir: str = "AI/results") -> dict:
        """Generate and save training metrics"""
        
        if self.model is None:
            raise ValueError("No trained model available")
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Predictions
        y_pred = self.model.predict(X_test)
        y_pred_classes = np.argmax(y_pred, axis=1)
        
        # Classification report
        report = classification_report(y_test, y_pred_classes, 
                                    target_names=self.label_encoder.classes_,
                                    output_dict=True)
        
        # Confusion matrix
        cm = confusion_matrix(y_test, y_pred_classes)
        
        # Save metrics
        metrics = {
            'test_accuracy': float(report['accuracy']),
            'per_class_metrics': report,
            'confusion_matrix': cm.tolist(),
            'training_history': {
                'accuracy': [float(x) for x in self.history.history['accuracy']],
                'val_accuracy': [float(x) for x in self.history.history['val_accuracy']],
                'loss': [float(x) for x in self.history.history['loss']],
                'val_loss': [float(x) for x in self.history.history['val_loss']]
            },
            'model_info': {
                'input_features': X_test.shape[1],
                'num_classes': len(self.label_encoder.classes_),
                'classes': self.label_encoder.classes_.tolist(),
                'training_date': datetime.now().isoformat()
            }
        }
        
        # Save to JSON
        metrics_path = os.path.join(output_dir, 'dual_hand_training_metrics.json')
        with open(metrics_path, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        # Generate plots
        self._create_training_plots(output_dir)
        self._create_confusion_matrix_plot(cm, self.label_encoder.classes_, output_dir)
        
        logger.info(f"Metrics saved to {metrics_path}")
        return metrics
    
    def _create_training_plots(self, output_dir: str):
        """Create training history plots"""
        if self.history is None:
            return
        
        # Training history
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))
        
        # Accuracy plot
        ax1.plot(self.history.history['accuracy'], label='Training Accuracy')
        ax1.plot(self.history.history['val_accuracy'], label='Validation Accuracy')
        ax1.set_title('Model Accuracy')
        ax1.set_xlabel('Epoch')
        ax1.set_ylabel('Accuracy')
        ax1.legend()
        ax1.grid(True)
        
        # Loss plot
        ax2.plot(self.history.history['loss'], label='Training Loss')
        ax2.plot(self.history.history['val_loss'], label='Validation Loss')
        ax2.set_title('Model Loss')
        ax2.set_xlabel('Epoch')
        ax2.set_ylabel('Loss')
        ax2.legend()
        ax2.grid(True)
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'dual_hand_training_history.png'), dpi=300, bbox_inches='tight')
        plt.close()
    
    def _create_confusion_matrix_plot(self, cm: np.ndarray, classes: np.ndarray, output_dir: str):
        """Create confusion matrix plot"""
        plt.figure(figsize=(10, 8))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                   xticklabels=classes, yticklabels=classes)
        plt.title('Dual-Hand Model Confusion Matrix')
        plt.xlabel('Predicted')
        plt.ylabel('Actual')
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'dual_hand_confusion_matrix.png'), dpi=300, bbox_inches='tight')
        plt.close()
    
    def run_training_pipeline(self) -> dict:
        """Run the complete training pipeline"""
        try:
            logger.info("Starting dual-hand model training pipeline...")
            
            # Load and prepare data
            X_train, X_test, y_train, y_test = self.load_and_prepare_data()
            
            # Train model
            training_results = self.train_model(X_train, y_train, X_test, y_test)
            
            # Save model
            model_path = self.save_model()
            training_results['model_path'] = model_path
            
            # Generate metrics
            metrics = self.generate_metrics(X_test, y_test)
            training_results.update(metrics)
            
            logger.info("Training pipeline completed successfully!")
            return training_results
            
        except Exception as e:
            logger.error(f"Training pipeline failed: {e}")
            raise

def main():
    """Main function to run training"""
    trainer = DualHandModelTrainer()
    
    try:
        results = trainer.run_training_pipeline()
        print(f"\nTraining completed successfully!")
        print(f"Test accuracy: {results['test_accuracy']:.4f}")
        print(f"Model saved to: {results['model_path']}")
        print(f"Metrics saved to: AI/results/")
        
    except Exception as e:
        print(f"Training failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 