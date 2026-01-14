import tensorflowjs as tfjs
import tensorflow as tf
import os

def convert_model():
    """
    Converts the Keras model to TensorFlow.js format.
    """
    try:
        # Define paths
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_path = os.path.join(base_dir, 'AI', 'models', 'gesture_model_fold1.h5')
        output_path = os.path.join(base_dir, '..', 'frontend', 'public', 'tfjs_model')

        # Create output directory if it doesn't exist
        os.makedirs(output_path, exist_ok=True)

        # Load the Keras model
        model = tf.keras.models.load_model(model_path)

        # Convert the model
        tfjs.converters.save_keras_model(model, output_path)

        print(f"Model converted successfully and saved to {output_path}")

    except Exception as e:
        print(f"An error occurred during model conversion: {e}")

if __name__ == "__main__":
    convert_model()
