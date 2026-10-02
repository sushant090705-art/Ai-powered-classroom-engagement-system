import cv2
import os
import time
import threading
import numpy as np
import tensorflow as tf


# =========================
# MRL Eye Model
# =========================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

MRL_MODEL_PATH = os.path.join(
    BASE_DIR,
    "ai-model",
    "models",
    "mrl_eye_model.keras"
)

mrl_eye_model = tf.keras.models.load_model(MRL_MODEL_PATH)


# =========================
# Eye State Settings
# =========================

BLINK_MAX_DURATION = 0.8
DROWSY_THRESHOLD = 3.0
SLEEPING_THRESHOLD = 3.0
BLINK_DISPLAY_DURATION = 0.5


# =========================
# Eye Tracking Data
# =========================

eye_tracks = {}
eye_tracks_lock = threading.Lock()


# =========================
# Predict Eye State
# =========================

def predict_eye_state(eye_image):

    try:
        eye_image = cv2.resize(
            eye_image,
            (64, 64)
        )

        eye_image = cv2.cvtColor(
            eye_image,
            cv2.COLOR_BGR2RGB
        )

        eye_image = eye_image.astype(
            np.float32
        ) / 255.0

        eye_image = np.expand_dims(
            eye_image,
            axis=0
        )

        prediction = mrl_eye_model.predict(
            eye_image,
            verbose=0
        )[0][0]

        if prediction < 0.5:
            state = "Open"
            confidence = 1 - prediction
        else:
            state = "Close"
            confidence = prediction

        return state, float(confidence)

    except Exception as e:

        print(
            "Eye prediction error:",
            e
        )

        return "Unknown", 0.0


# =========================
# Update Eye Display State
# =========================

def update_eye_display_state(track_id, raw_state):

    current_time = time.time()

    if track_id is None:
        return "Unknown"

    with eye_tracks_lock:

        if track_id not in eye_tracks:

            eye_tracks[track_id] = {
                "previous_raw_state": "Unknown",
                "closed_since": None,
                "blink_until": 0,
                "was_sleeping": False,
                "last_seen": current_time
            }

        track = eye_tracks[track_id]

        track["last_seen"] = current_time

        previous_state = track["previous_raw_state"]


        # =========================
        # Eyes Closed
        # =========================

        if raw_state == "Close":

            if previous_state != "Close":
                track["closed_since"] = current_time

            if track["closed_since"] is not None:

                closed_duration = (
                    current_time -
                    track["closed_since"]
                )

            else:
                closed_duration = 0

            track["previous_raw_state"] = "Close"


            # Sleeping
            if closed_duration >= SLEEPING_THRESHOLD:

                track["was_sleeping"] = True

                return "Sleeping"


            # Drowsy
            elif closed_duration >= BLINK_MAX_DURATION:

                return "Drowsy"


            # Normal closed state
            else:

                return "Close"


        # =========================
        # Eyes Open
        # =========================

        elif raw_state == "Open":

            closed_duration = 0

            if track["closed_since"] is not None:

                closed_duration = (
                    current_time -
                    track["closed_since"]
                )

            track["previous_raw_state"] = "Open"

            track["closed_since"] = None


            # Person was sleeping
            if track["was_sleeping"]:

                track["was_sleeping"] = False

                track["blink_until"] = 0

                return "Open"


            # Short close = Blink
            if (
                closed_duration > 0
                and closed_duration < BLINK_MAX_DURATION
            ):

                track["blink_until"] = (
                    current_time +
                    BLINK_DISPLAY_DURATION
                )

                return "Blink"


            # Keep displaying Blink briefly
            if current_time < track["blink_until"]:

                return "Blink"


            return "Open"


        # Unknown
        else:

            return "Unknown"
        
        
print("Eye tracking module loaded successfully!")        