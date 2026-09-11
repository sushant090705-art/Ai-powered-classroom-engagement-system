import os
import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TEST_DIR = os.path.join(
    BASE_DIR,
    "dataset",
    "FER2013",
    "test"
)

MODEL_PATH = os.path.join(
    BASE_DIR,
    "ai-model",
    "emotion",
    "emotion_model.keras"
)

# Load trained FER2013 model
model = tf.keras.models.load_model(MODEL_PATH)

print("FER2013 model loaded successfully!")

# Test dataset
test_datagen = ImageDataGenerator(rescale=1.0 / 255)

test_data = test_datagen.flow_from_directory(
    TEST_DIR,
    target_size=(48, 48),
    color_mode="grayscale",
    batch_size=64,
    class_mode="categorical",
    shuffle=False
)

# Calculate accuracy
loss, accuracy = model.evaluate(test_data)

print("\n==============================")
print("FER2013 MODEL ACCURACY")
print("==============================")
print(f"Accuracy: {accuracy * 100:.2f}%")
print("==============================")