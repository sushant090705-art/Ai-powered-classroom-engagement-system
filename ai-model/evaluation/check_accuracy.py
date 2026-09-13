import os
import tensorflow as tf

# =========================
# PATHS
# =========================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Go to project root
PROJECT_DIR = os.path.dirname(BASE_DIR)

MODEL_PATH = os.path.join(
    BASE_DIR,
    "..",
    "models",
    "emotion_model.keras"
)

TEST_DIR = os.path.join(
    os.path.dirname(PROJECT_DIR),
    "dataset",
    "FER 2013",
    "test"
)
print("Model Path:", MODEL_PATH)
print("Test Dataset Path:", TEST_DIR)

# =========================
# LOAD MODEL
# =========================

print("Loading model...")

model = tf.keras.models.load_model(MODEL_PATH)

print("Model loaded successfully!")

# =========================
# LOAD TEST DATA
# =========================

IMG_SIZE = (48, 48)
BATCH_SIZE = 32

test_dataset = tf.keras.utils.image_dataset_from_directory(
    TEST_DIR,
    image_size=IMG_SIZE,
    color_mode="grayscale",
    batch_size=BATCH_SIZE,
    shuffle=False,
    label_mode="categorical"
)

# Normalize images
test_dataset = test_dataset.map(
    lambda x, y: (tf.cast(x, tf.float32) / 255.0, y)
)

# =========================
# EVALUATE MODEL
# =========================

print("\nEvaluating model...\n")

loss, accuracy = model.evaluate(test_dataset)

print("\n==============================")
print(f"Test Loss: {loss:.4f}")
print(f"Test Accuracy: {accuracy * 100:.2f}%")
print("==============================")