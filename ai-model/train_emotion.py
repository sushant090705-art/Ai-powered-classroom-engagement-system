import os
import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras import layers, models

# =========================
# PATHS
# =========================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TRAIN_DIR = os.path.join(BASE_DIR, "dataset", "FER2013", "train")
TEST_DIR = os.path.join(BASE_DIR, "dataset", "FER2013", "test")

MODEL_DIR = os.path.join(BASE_DIR, "ai-model", "emotion")
MODEL_PATH = os.path.join(MODEL_DIR, "emotion_model.keras")

os.makedirs(MODEL_DIR, exist_ok=True)

# =========================
# SETTINGS
# =========================

IMG_SIZE = (48, 48)
BATCH_SIZE = 64
EPOCHS = 15

# =========================
# DATA PREPARATION
# =========================

train_datagen = ImageDataGenerator(
    rescale=1.0 / 255,
    rotation_range=10,
    width_shift_range=0.1,
    height_shift_range=0.1,
    zoom_range=0.1,
    horizontal_flip=True
)

test_datagen = ImageDataGenerator(
    rescale=1.0 / 255
)

train_data = train_datagen.flow_from_directory(
    TRAIN_DIR,
    target_size=IMG_SIZE,
    color_mode="grayscale",
    batch_size=BATCH_SIZE,
    class_mode="categorical",
    shuffle=True
)

test_data = test_datagen.flow_from_directory(
    TEST_DIR,
    target_size=IMG_SIZE,
    color_mode="grayscale",
    batch_size=BATCH_SIZE,
    class_mode="categorical",
    shuffle=False
)

# =========================
# MODEL
# =========================

model = models.Sequential([
    layers.Input(shape=(48, 48, 1)),

    layers.Conv2D(32, (3, 3), activation="relu"),
    layers.MaxPooling2D((2, 2)),

    layers.Conv2D(64, (3, 3), activation="relu"),
    layers.MaxPooling2D((2, 2)),

    layers.Conv2D(128, (3, 3), activation="relu"),
    layers.MaxPooling2D((2, 2)),

    layers.Flatten(),

    layers.Dense(128, activation="relu"),
    layers.Dropout(0.5),

    layers.Dense(7, activation="softmax")
])

# =========================
# COMPILE
# =========================

model.compile(
    optimizer="adam",
    loss="categorical_crossentropy",
    metrics=["accuracy"]
)

model.summary()

# =========================
# TRAIN
# =========================

print("\nStarting emotion model training...\n")

history = model.fit(
    train_data,
    validation_data=test_data,
    epochs=EPOCHS
)

# =========================
# SAVE MODEL
# =========================

model.save(MODEL_PATH)

print("\n===================================")
print("Emotion model training completed!")
print("Model saved at:")
print(MODEL_PATH)
print("===================================")