import os
import shutil
import tensorflow as tf

from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras import layers, models, regularizers
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import (
    ModelCheckpoint,
    EarlyStopping,
    ReduceLROnPlateau
)

# ============================================================
# PATHS
# ============================================================

# Project root:
# Ai-powered-classroom-engagement-system/
BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

FER_TRAIN_DIR = os.path.join(
    BASE_DIR,
    "dataset",
    "FER 2013",
    "train"
)

RAF_ZIP = os.path.join(
    BASE_DIR,
    "dataset",
    "RAF DB.zip"
)

WORK_DIR = os.path.join(
    BASE_DIR,
    "dataset",
    "combined_training"
)

COMBINED_TRAIN_DIR = os.path.join(
    WORK_DIR,
    "train"
)

MODEL_DIR = os.path.join(
    BASE_DIR,
    "ai-model",
    "models"
)

MODEL_PATH = os.path.join(
    MODEL_DIR,
    "emotion_model.keras"
)

# ============================================================
# SETTINGS
# ============================================================

IMG_SIZE = (48, 48)
BATCH_SIZE = 64
EPOCHS = 40
VALIDATION_SPLIT = 0.15

# ============================================================
# EMOTION MAPPING
# ============================================================

EMOTIONS = [
    "angry",
    "disgust",
    "fear",
    "happy",
    "neutral",
    "sad",
    "surprise"
]

RAF_TO_EMOTION = {
    "1": "surprise",
    "2": "fear",
    "3": "disgust",
    "4": "happy",
    "5": "sad",
    "6": "angry",
    "7": "neutral"
}

# ============================================================
# CHECK DATASET
# ============================================================

print("\n===================================")
print("Checking datasets...")
print("===================================\n")

if not os.path.exists(FER_TRAIN_DIR):
    raise FileNotFoundError(
        f"FER2013 training folder not found:\n{FER_TRAIN_DIR}"
    )

if not os.path.exists(RAF_ZIP):
    raise FileNotFoundError(
        f"RAF-DB ZIP not found:\n{RAF_ZIP}"
    )

print("FER2013:", FER_TRAIN_DIR)
print("RAF-DB  :", RAF_ZIP)

# ============================================================
# CREATE COMBINED DATASET
# ============================================================

print("\n===================================")
print("Preparing combined dataset...")
print("===================================\n")

if os.path.exists(WORK_DIR):
    print("Removing old combined dataset...")
    shutil.rmtree(WORK_DIR)

for emotion in EMOTIONS:
    os.makedirs(
        os.path.join(COMBINED_TRAIN_DIR, emotion),
        exist_ok=True
    )

# ============================================================
# COPY FER2013
# ============================================================

print("\nCopying FER2013 images...")

for emotion in EMOTIONS:

    source_dir = os.path.join(
        FER_TRAIN_DIR,
        emotion
    )

    destination_dir = os.path.join(
        COMBINED_TRAIN_DIR,
        emotion
    )

    if not os.path.exists(source_dir):
        continue

    count = 0

    for filename in os.listdir(source_dir):

        source_file = os.path.join(
            source_dir,
            filename
        )

        if os.path.isfile(source_file):

            destination_file = os.path.join(
                destination_dir,
                "FER_" + filename
            )

            shutil.copy2(
                source_file,
                destination_file
            )

            count += 1

    print(f"{emotion}: {count} FER2013 images")

# ============================================================
# RAF-DB
# ============================================================

print("\n===================================")
print("RAF-DB preparation")
print("===================================\n")

RAF_WORK_DIR = os.path.join(
    WORK_DIR,
    "raf_temp"
)

os.makedirs(RAF_WORK_DIR, exist_ok=True)

print("Extracting RAF-DB...")

shutil.unpack_archive(
    RAF_ZIP,
    RAF_WORK_DIR
)

RAF_DATASET_DIR = os.path.join(
    RAF_WORK_DIR,
    "DATASET"
)

RAF_TRAIN_DIR = os.path.join(
    RAF_DATASET_DIR,
    "train"
)

if not os.path.exists(RAF_TRAIN_DIR):
    raise FileNotFoundError(
        f"RAF-DB train folder not found:\n{RAF_TRAIN_DIR}"
    )

print("RAF-DB extracted successfully.")

# ============================================================
# COPY RAF-DB TRAINING IMAGES
# ============================================================

print("\nCopying RAF-DB images...")

for raf_folder, emotion in RAF_TO_EMOTION.items():

    source_dir = os.path.join(
        RAF_TRAIN_DIR,
        raf_folder
    )

    destination_dir = os.path.join(
        COMBINED_TRAIN_DIR,
        emotion
    )

    if not os.path.exists(source_dir):
        print(
            f"Warning: RAF folder {raf_folder} not found"
        )
        continue

    count = 0

    for filename in os.listdir(source_dir):

        source_file = os.path.join(
            source_dir,
            filename
        )

        if os.path.isfile(source_file):

            destination_file = os.path.join(
                destination_dir,
                "RAF_" + filename
            )

            shutil.copy2(
                source_file,
                destination_file
            )

            count += 1

    print(
        f"{emotion}: {count} RAF-DB images"
    )

# ============================================================
# COUNT COMBINED DATASET
# ============================================================

print("\n===================================")
print("Combined dataset counts")
print("===================================\n")

total_images = 0

for emotion in EMOTIONS:

    folder = os.path.join(
        COMBINED_TRAIN_DIR,
        emotion
    )

    count = len([
        f for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f))
    ])

    total_images += count

    print(f"{emotion:10s}: {count}")

print("-----------------------------------")
print(f"TOTAL      : {total_images}")
print("-----------------------------------")

# ============================================================
# DATA GENERATORS
# ============================================================

print("\n===================================")
print("Creating data generators...")
print("===================================\n")

train_datagen = ImageDataGenerator(
    rescale=1.0 / 255,
    rotation_range=15,
    width_shift_range=0.1,
    height_shift_range=0.1,
    zoom_range=0.1,
    horizontal_flip=True,
    validation_split=VALIDATION_SPLIT
)

validation_datagen = ImageDataGenerator(
    rescale=1.0 / 255,
    validation_split=VALIDATION_SPLIT
)

train_data = train_datagen.flow_from_directory(
    COMBINED_TRAIN_DIR,
    target_size=IMG_SIZE,
    color_mode="grayscale",
    class_mode="categorical",
    batch_size=BATCH_SIZE,
    shuffle=True,
    subset="training",
    seed=42
)

validation_data = validation_datagen.flow_from_directory(
    COMBINED_TRAIN_DIR,
    target_size=IMG_SIZE,
    color_mode="grayscale",
    class_mode="categorical",
    batch_size=BATCH_SIZE,
    shuffle=False,
    subset="validation",
    seed=42
)

print("\nClass mapping:")
print(train_data.class_indices)

# ============================================================
# CLASS WEIGHTS
# ============================================================

print("\nCalculating class weights...")

class_counts = [
    len([
        f for f in os.listdir(
            os.path.join(COMBINED_TRAIN_DIR, emotion)
        )
        if os.path.isfile(
            os.path.join(
                COMBINED_TRAIN_DIR,
                emotion,
                f
            )
        )
    ])
    for emotion in EMOTIONS
]

total = sum(class_counts)
num_classes = len(EMOTIONS)

class_weights = {}

for index, count in enumerate(class_counts):

    class_weights[index] = total / (
        num_classes * count
    )

print("\nClass weights:")

for index, weight in class_weights.items():

    print(
        f"{EMOTIONS[index]:10s}: {weight:.2f}"
    )

# ============================================================
# MODEL
# ============================================================

print("\n===================================")
print("Building CNN model...")
print("===================================\n")

model = models.Sequential([

    layers.Input(shape=(48, 48, 1)),

    # --------------------------------------------------------
    # Block 1
    # --------------------------------------------------------

    layers.Conv2D(
        32,
        (3, 3),
        padding="same",
        kernel_regularizer=regularizers.l2(0.0005)
    ),
    layers.BatchNormalization(),
    layers.Activation("relu"),

    layers.Conv2D(
        32,
        (3, 3),
        padding="same",
        kernel_regularizer=regularizers.l2(0.0005)
    ),
    layers.BatchNormalization(),
    layers.Activation("relu"),

    layers.MaxPooling2D((2, 2)),
    layers.Dropout(0.20),

    # --------------------------------------------------------
    # Block 2
    # --------------------------------------------------------

    layers.Conv2D(
        64,
        (3, 3),
        padding="same",
        kernel_regularizer=regularizers.l2(0.0005)
    ),
    layers.BatchNormalization(),
    layers.Activation("relu"),

    layers.Conv2D(
        64,
        (3, 3),
        padding="same",
        kernel_regularizer=regularizers.l2(0.0005)
    ),
    layers.BatchNormalization(),
    layers.Activation("relu"),

    layers.MaxPooling2D((2, 2)),
    layers.Dropout(0.25),

    # --------------------------------------------------------
    # Block 3
    # --------------------------------------------------------

    layers.Conv2D(
        128,
        (3, 3),
        padding="same",
        kernel_regularizer=regularizers.l2(0.0005)
    ),
    layers.BatchNormalization(),
    layers.Activation("relu"),

    layers.Conv2D(
        128,
        (3, 3),
        padding="same",
        kernel_regularizer=regularizers.l2(0.0005)
    ),
    layers.BatchNormalization(),
    layers.Activation("relu"),

    layers.MaxPooling2D((2, 2)),
    layers.Dropout(0.30),

    # --------------------------------------------------------
    # Block 4
    # --------------------------------------------------------

    layers.Conv2D(
        256,
        (3, 3),
        padding="same",
        kernel_regularizer=regularizers.l2(0.0005)
    ),
    layers.BatchNormalization(),
    layers.Activation("relu"),

    layers.Conv2D(
        256,
        (3, 3),
        padding="same",
        kernel_regularizer=regularizers.l2(0.0005)
    ),
    layers.BatchNormalization(),
    layers.Activation("relu"),

    layers.MaxPooling2D((2, 2)),
    layers.Dropout(0.35),

    # --------------------------------------------------------
    # Classifier
    # --------------------------------------------------------

    layers.GlobalAveragePooling2D(),

    layers.Dense(
        256,
        activation="relu",
        kernel_regularizer=regularizers.l2(0.0005)
    ),

    layers.BatchNormalization(),
    layers.Dropout(0.50),

    layers.Dense(
        7,
        activation="softmax"
    )
])

# ============================================================
# COMPILE
# ============================================================

model.compile(
    optimizer=Adam(
        learning_rate=0.0005
    ),
    loss="categorical_crossentropy",
    metrics=["accuracy"]
)

model.summary()

# ============================================================
# CALLBACKS
# ============================================================

checkpoint = ModelCheckpoint(
    MODEL_PATH,
    monitor="val_accuracy",
    mode="max",
    save_best_only=True,
    verbose=1
)

early_stopping = EarlyStopping(
    monitor="val_loss",
    patience=7,
    mode="min",
    restore_best_weights=True,
    verbose=1
)

reduce_lr = ReduceLROnPlateau(
    monitor="val_loss",
    factor=0.5,
    patience=3,
    min_lr=1e-6,
    verbose=1
)

callbacks = [
    checkpoint,
    early_stopping,
    reduce_lr
]

# ============================================================
# TRAIN
# ============================================================

print("\n===================================")
print("Starting combined emotion training")
print("===================================\n")

history = model.fit(
    train_data,
    validation_data=validation_data,
    epochs=EPOCHS,
    class_weight=class_weights,
    callbacks=callbacks
)

# ============================================================
# SAVE FINAL MODEL
# ============================================================

print("\n===================================")
print("Training completed!")
print("===================================\n")

model.save(MODEL_PATH)

print("Model saved at:")
print(MODEL_PATH)