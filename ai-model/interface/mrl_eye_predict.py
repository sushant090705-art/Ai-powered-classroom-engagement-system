import tensorflow as tf
import numpy as np
import os
import cv2
from tensorflow.keras.utils import load_img, img_to_array


# Get the directory where this Python file is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Go from interface/ → ai-model/
AI_MODEL_DIR = os.path.dirname(BASE_DIR)

# Model location
MODEL_PATH = os.path.join(
    AI_MODEL_DIR,
    "models",
    "mrl_eye_model.keras"
)

# Test image location
TEST_IMAGE = os.path.join(
    AI_MODEL_DIR,
    "..",
    "dataset",
    "MRL eye",
    "test",
    "sleepy",
    "s0019_01594_0_0_0_0_0_01.png"
)


# Load trained model
model = tf.keras.models.load_model(MODEL_PATH)


def predict_eye_state(frame):
    """
    Predict whether an eye is Awake or Sleepy.
    """

    # Resize to model input size
    frame = cv2.resize(frame, (64, 64))

    # OpenCV uses BGR, convert to RGB
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Convert to NumPy array
    img_array = np.array(frame, dtype=np.float32)

    # Normalize pixel values
    img_array = img_array / 255.0

    # Add batch dimension
    img_array = np.expand_dims(img_array, axis=0)

    # Make prediction
    prediction = model.predict(img_array, verbose=0)[0][0]

    # Class mapping
    if prediction < 0.5:
        state = "Awake"
        confidence = (1 - prediction) * 100
    else:
        state = "Sleepy"
        confidence = prediction * 100

    return state, confidence


if __name__ == "__main__":

    test_image = r"C:\Projects\Ai-powered-classroom-engagement-system\dataset\MRL eye\test\sleepy\s0019_01594_0_0_0_0_0_01.png"

    # Read image using OpenCV
    frame = cv2.imread(test_image)

    if frame is None:
        print("Error: Could not load test image.")
    else:
        state, confidence = predict_eye_state(frame)

        print("Eye State:", state)
        print("Confidence:", round(confidence, 2), "%")