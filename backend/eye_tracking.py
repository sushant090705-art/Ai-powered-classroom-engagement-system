"""Eye-state prediction and per-person eye tracking.

This module owns all MRL eye-model inference and temporal eye-state logic.
It is shared by live-camera and recorded-video processing.
"""

import os
import time
import threading

import cv2
import numpy as np
import tensorflow as tf


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MRL_MODEL_PATH = os.path.join(
    BASE_DIR, "ai-model", "models", "mrl_eye_model.keras"
)

print("Loading MRL eye model...")
mrl_eye_model = tf.keras.models.load_model(MRL_MODEL_PATH)
print("MRL eye model loaded successfully!")


# Eye-state thresholds (seconds)
BLINK_MAX_DURATION = 0.8
SLEEPING_THRESHOLD = 3.0
BLINK_DISPLAY_DURATION = 0.5

# Shared tracking state for the current live camera session.
eye_tracks = {}
eye_tracks_lock = threading.Lock()
next_track_id = 0


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
        print("MRL prediction error:", exc)
        return "Unknown", 0.0


def get_eye_track_id(center_x, center_y):
    """Associate the current face position with a short-lived track ID."""
    global next_track_id

    current_time = time.time()

    with eye_tracks_lock:
        stale_ids = [
            track_id
            for track_id, track in eye_tracks.items()
            if current_time - track["last_seen"] > 2.0
        ]

        for track_id in stale_ids:
            del eye_tracks[track_id]

        best_track_id = None
        best_distance = float("inf")

        for track_id, track in eye_tracks.items():
            distance = np.sqrt(
                (center_x - track["center_x"]) ** 2
                + (center_y - track["center_y"]) ** 2
            )

            if distance < best_distance and distance < 120:
                best_distance = distance
                best_track_id = track_id

        if best_track_id is None:
            best_track_id = next_track_id
            next_track_id += 1

            eye_tracks[best_track_id] = {
                "center_x": center_x,
                "center_y": center_y,
                "last_seen": current_time,
                "previous_raw_state": "Unknown",
                "closed_since": None,
                "blink_until": 0,
                "was_sleeping": False,
            }
        else:
            track = eye_tracks[best_track_id]
            track["center_x"] = center_x
            track["center_y"] = center_y
            track["last_seen"] = current_time

        return best_track_id


def update_eye_display_state(track_id, raw_state):
    """Convert raw eye predictions into Open/Close/Blink/Drowsy/Sleeping."""
    current_time = time.time()

    with eye_tracks_lock:
        if track_id not in eye_tracks:
            return raw_state

        track = eye_tracks[track_id]
        previous_state = track["previous_raw_state"]

        if raw_state == "Close":
            if previous_state != "Close":
                track["closed_since"] = current_time

            closed_duration = (
                current_time - track["closed_since"]
                if track["closed_since"] is not None
                else 0
            )

            track["previous_raw_state"] = "Close"

            if closed_duration >= SLEEPING_THRESHOLD:
                track["was_sleeping"] = True
                return "Sleeping"

            if closed_duration >= BLINK_MAX_DURATION:
                return "Drowsy"

            return "Close"

        if raw_state == "Open":
            closed_duration = (
                current_time - track["closed_since"]
                if track["closed_since"] is not None
                else 0
            )

            track["previous_raw_state"] = "Open"
            track["closed_since"] = None

            if track["was_sleeping"]:
                track["was_sleeping"] = False
                track["blink_until"] = 0
                return "Open"

            if 0 < closed_duration < BLINK_MAX_DURATION:
                track["blink_until"] = (
                    current_time + BLINK_DISPLAY_DURATION
                )
                return "Blink"

            if current_time < track["blink_until"]:
                return "Blink"

            return "Open"

        return "Unknown"


def reset_eye_tracks():
    """Clear live eye tracking state at the start/end of a camera session."""
    global next_track_id

    with eye_tracks_lock:
        eye_tracks.clear()
        next_track_id = 0
