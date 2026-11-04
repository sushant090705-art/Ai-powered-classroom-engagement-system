"""Eye-state prediction and per-person eye tracking.

This module owns all MRL eye-model inference and temporal eye-state logic.
It is shared by live-camera and recorded-video processing.
"""

import logging
import os

import cv2
import numpy as np
import tensorflow as tf

logger = logging.getLogger(__name__)


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MRL_MODEL_PATH = os.path.join(
    BASE_DIR, "ai-model", "models", "mrl_eye_model.keras"
)

logger.info("Loading MRL eye model...")
mrl_eye_model = tf.keras.models.load_model(MRL_MODEL_PATH)
logger.info("MRL eye model loaded successfully!")


# The temporal logic lives in eye_state.py (no TensorFlow needed). These
# thin wrappers keep the old module-level API for any code that still uses
# one shared tracker; new code should use one EyeTracker per class.
from eye_state import (  # noqa: E402
    BLINK_DISPLAY_DURATION,
    BLINK_MAX_DURATION,
    SLEEPING_THRESHOLD,
    EyeTracker,
)

default_tracker = EyeTracker()


def predict_eye_state(eye_image):
    """Predict Open/Close from an eye crop.

    Confidence is returned as a percentage (0-100).
    """
    try:
        eye_image = cv2.resize(eye_image, (64, 64))
        eye_image = cv2.cvtColor(eye_image, cv2.COLOR_BGR2RGB)
        eye_image = eye_image.astype(np.float32) / 255.0
        eye_image = np.expand_dims(eye_image, axis=0)

        prediction = float(
            mrl_eye_model.predict(eye_image, verbose=0)[0][0]
        )

        if prediction < 0.5:
            return "Open", (1.0 - prediction) * 100.0

        return "Close", prediction * 100.0

    except Exception as exc:
        logger.error("MRL prediction error: %s", exc)
        return "Unknown", 0.0


def get_eye_track_id(center_x, center_y):
    return default_tracker.get_track_id(center_x, center_y)


def update_eye_display_state(track_id, raw_state):
    return default_tracker.update_display_state(track_id, raw_state)


def reset_eye_tracks():
    default_tracker.reset()
