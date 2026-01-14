import joblib
import json
import numpy as np
import os

def extract_data():
    """
    Extracts scaler and label encoder data to a JSON file.
    """
    try:
        # Define paths
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        scaler_path = os.path.join(base_dir, 'AI', 'results', 'scaler.pkl')
        encoder_path = os.path.join(base_dir, 'AI', 'results', 'label_encoder.pkl')
        output_path = os.path.join(base_dir, '..', 'frontend', 'public', 'preprocessing_data.json')

        # Load the scaler and encoder
        scaler = joblib.load(scaler_path)
        encoder = joblib.load(encoder_path)

        # Prepare the data for JSON serialization
        data = {
            'scaler': {
                'mean': scaler.mean_.tolist(),
                'scale': scaler.scale_.tolist()
            },
            'encoder': {
                'classes': encoder.classes_.tolist()
            }
        }

        # Save the data to a JSON file
        with open(output_path, 'w') as f:
            json.dump(data, f)

        print(f"Preprocessing data extracted successfully and saved to {output_path}")

    except Exception as e:
        print(f"An error occurred during data extraction: {e}")

if __name__ == "__main__":
    extract_data()
