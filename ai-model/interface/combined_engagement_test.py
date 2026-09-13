import cv2
import os
import sys
import time
import numpy as np
import mediapipe as mp
from collections import deque

# ============================================================
# PATH SETUP
# ============================================================

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_MODEL_DIR = os.path.dirname(CURRENT_DIR)
PROJECT_ROOT = os.path.dirname(AI_MODEL_DIR)

# Allow importing mrl_eye_predict.py
sys.path.append(CURRENT_DIR)

from mrl_eye_predict import predict_eye_state


# ============================================================
# MEDIAPIPE FACE LANDMARKER
# ============================================================

MODEL_PATH = os.path.join(
    AI_MODEL_DIR,
    "models",
    "mediapipe",
    "face_landmarker.task"
)

if not os.path.exists(MODEL_PATH):
    print("ERROR: MediaPipe model not found:")
    print(MODEL_PATH)
    sys.exit(1)


BaseOptions = mp.tasks.BaseOptions
FaceLandmarker = mp.tasks.vision.FaceLandmarker
FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode


options = FaceLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=VisionRunningMode.IMAGE,
    num_faces=10
)

landmarker = FaceLandmarker.create_from_options(options)


# ============================================================
# SETTINGS
# ============================================================

# Number of recent predictions used for smoothing
SMOOTHING_FRAMES = 7

# How long both eyes must remain closed
# before DROWSY/SLEEPING is shown.
DROWSY_TIME = 1.5
SLEEPING_TIME = 3.0

# Eye crop margin
EYE_MARGIN = 0.35


# ============================================================
# EYE LANDMARKS
# ============================================================

# MediaPipe Face Mesh landmark points
LEFT_EYE_POINTS = [
    33,    # outer corner
    133,   # inner corner
    159,   # upper eyelid
    145    # lower eyelid
]

RIGHT_EYE_POINTS = [
    362,   # outer corner
    263,   # inner corner
    386,   # upper eyelid
    374    # lower eyelid
]


# ============================================================
# GET EYE CROP
# ============================================================

def get_eye_crop(frame, landmarks, eye_points, margin=EYE_MARGIN):
    """
    Extracts a tight eye region using MediaPipe landmarks.
    """

    h, w, _ = frame.shape

    points = []

    for index in eye_points:
        x = int(landmarks[index].x * w)
        y = int(landmarks[index].y * h)

        points.append((x, y))

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)

    eye_width = max_x - min_x
    eye_height = max_y - min_y

    # Safety for very small boxes
    if eye_width < 3 or eye_height < 3:
        return None

    margin_x = int(eye_width * margin)
    margin_y = int(eye_height * margin)

    min_x -= margin_x
    max_x += margin_x

    min_y -= margin_y
    max_y += margin_y

    # Keep coordinates inside image
    min_x = max(0, min_x)
    min_y = max(0, min_y)
    max_x = min(w, max_x)
    max_y = min(h, max_y)

    crop = frame[min_y:max_y, min_x:max_x]

    if crop.size == 0:
        return None

    return crop


# ============================================================
# HEAD DIRECTION
# ============================================================

def get_head_direction(landmarks):
    """
    Gives only the physical head direction.
    It does NOT determine engagement/disengagement.
    """

    nose = landmarks[1]

    left_eye = landmarks[33]
    right_eye = landmarks[263]

    forehead = landmarks[10]
    chin = landmarks[152]

    # --------------------------------------------------------
    # Horizontal direction
    # --------------------------------------------------------

    eye_center_x = (left_eye.x + right_eye.x) / 2

    horizontal_difference = nose.x - eye_center_x

    # --------------------------------------------------------
    # Vertical direction
    # --------------------------------------------------------

    face_height = abs(chin.y - forehead.y)

    if face_height == 0:
        return "CENTER"

    vertical_position = (nose.y - forehead.y) / face_height

    # --------------------------------------------------------
    # Thresholds
    # --------------------------------------------------------

    horizontal_threshold = 0.035

    if horizontal_difference < -horizontal_threshold:
        horizontal_direction = "LEFT"

    elif horizontal_difference > horizontal_threshold:
        horizontal_direction = "RIGHT"

    else:
        horizontal_direction = "CENTER"

    # Vertical
    if vertical_position < 0.38:
        vertical_direction = "UP"

    elif vertical_position > 0.62:
        vertical_direction = "DOWN"

    else:
        vertical_direction = "CENTER"

    # --------------------------------------------------------
    # Combine
    # --------------------------------------------------------

    if horizontal_direction != "CENTER":
        return horizontal_direction

    if vertical_direction != "CENTER":
        return vertical_direction

    return "CENTER"


# ============================================================
# DRAW TEXT
# ============================================================

def draw_text(frame, text, position, scale=0.6, thickness=2):
    cv2.putText(
        frame,
        text,
        position,
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        (255, 255, 255),
        thickness,
        cv2.LINE_AA
    )


# ============================================================
# FACE STATE CLASS
# ============================================================

class FaceState:

    def __init__(self):

        # Recent eye predictions
        self.left_history = deque(maxlen=SMOOTHING_FRAMES)
        self.right_history = deque(maxlen=SMOOTHING_FRAMES)

        # Current stable states
        self.left_state = "Unknown"
        self.right_state = "Unknown"

        # Confidence
        self.left_confidence = 0.0
        self.right_confidence = 0.0

        # Both-eyes-closed timer
        self.eyes_closed_start = None

        # Final state
        self.final_state = "NO EYES"


# ============================================================
# SMOOTH PREDICTION
# ============================================================

def smooth_eye_prediction(history, new_state):
    """
    Stores recent predictions and returns the majority result.
    """

    history.append(new_state)

    if len(history) < 3:
        return new_state

    awake_count = history.count("Awake")
    sleepy_count = history.count("Sleepy")

    if sleepy_count > awake_count:
        return "Sleepy"

    return "Awake"


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 60)
    print("AI CLASSROOM - COMBINED DETECTION")
    print("=" * 60)
    print()
    print("Controls:")
    print("  Q = Quit")
    print()
    print("Eye states:")
    print("  AWAKE")
    print("  BLINK")
    print("  DROWSY")
    print("  SLEEPING")
    print()
    print("Head direction:")
    print("  CENTER / LEFT / RIGHT / UP / DOWN")
    print()
    print("=" * 60)

    # --------------------------------------------------------
    # Camera
    # --------------------------------------------------------

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print("ERROR: Could not open webcam.")
        return

    # Camera resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # --------------------------------------------------------
    # Face states
    # --------------------------------------------------------

    face_states = {}

    while True:

        ret, frame = cap.read()

        if not ret:
            print("ERROR: Could not read frame.")
            break

        # ----------------------------------------------------
        # Mirror camera
        # ----------------------------------------------------

        frame = cv2.flip(frame, 1)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb
        )

        # ----------------------------------------------------
        # Detect faces
        # ----------------------------------------------------

        result = landmarker.detect(mp_image)

        detected_faces = result.face_landmarks

        # ----------------------------------------------------
        # No faces
        # ----------------------------------------------------

        if len(detected_faces) == 0:

            draw_text(
                frame,
                "No face detected",
                (30, 40),
                0.8,
                2
            )

            cv2.imshow(
                "AI Classroom - Combined Detection",
                frame
            )

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            continue

        # ----------------------------------------------------
        # Process every face
        # ----------------------------------------------------

        for face_id, landmarks in enumerate(detected_faces):

            # Create state object if new face
            if face_id not in face_states:
                face_states[face_id] = FaceState()

            state = face_states[face_id]

            # ------------------------------------------------
            # HEAD DIRECTION
            # ------------------------------------------------

            head_direction = get_head_direction(landmarks)

            # ------------------------------------------------
            # EYE CROPS
            # ------------------------------------------------

            left_eye_crop = get_eye_crop(
                frame,
                landmarks,
                LEFT_EYE_POINTS
            )

            right_eye_crop = get_eye_crop(
                frame,
                landmarks,
                RIGHT_EYE_POINTS
            )

            # ------------------------------------------------
            # PREDICT LEFT EYE
            # ------------------------------------------------

            if left_eye_crop is not None:

                try:

                    left_state, left_confidence = \
                        predict_eye_state(left_eye_crop)

                    state.left_state = smooth_eye_prediction(
                        state.left_history,
                        left_state
                    )

                    state.left_confidence = left_confidence

                except Exception as e:

                    print("Left eye error:", e)

                    state.left_state = "Unknown"

            # ------------------------------------------------
            # PREDICT RIGHT EYE
            # ------------------------------------------------

            if right_eye_crop is not None:

                try:

                    right_state, right_confidence = \
                        predict_eye_state(right_eye_crop)

                    state.right_state = smooth_eye_prediction(
                        state.right_history,
                        right_state
                    )

                    state.right_confidence = right_confidence

                except Exception as e:

                    print("Right eye error:", e)

                    state.right_state = "Unknown"

            # ------------------------------------------------
            # DETERMINE EYE CONDITION
            # ------------------------------------------------

            left = state.left_state
            right = state.right_state

            # Both eyes available
            if left in ["Awake", "Sleepy"] and \
               right in ["Awake", "Sleepy"]:

                # --------------------------------------------
                # BOTH AWAKE
                # --------------------------------------------

                if left == "Awake" and right == "Awake":

                    state.eyes_closed_start = None

                    state.final_state = "AWAKE"

                # --------------------------------------------
                # BOTH SLEEPY
                # --------------------------------------------

                elif left == "Sleepy" and right == "Sleepy":

                    # Start timer
                    if state.eyes_closed_start is None:
                        state.eyes_closed_start = time.time()

                    closed_time = (
                        time.time()
                        - state.eyes_closed_start
                    )

                    # ----------------------------------------
                    # SHORT CLOSURE
                    # ----------------------------------------

                    if closed_time < DROWSY_TIME:

                        state.final_state = "BLINK"

                    # ----------------------------------------
                    # DROWSY
                    # ----------------------------------------

                    elif closed_time < SLEEPING_TIME:

                        state.final_state = "DROWSY"

                    # ----------------------------------------
                    # SLEEPING
                    # ----------------------------------------

                    else:

                        state.final_state = "SLEEPING"

                # --------------------------------------------
                # ONE SLEEPY + ONE AWAKE
                # --------------------------------------------

                else:

                    # Do not start drowsiness timer
                    state.eyes_closed_start = None

                    state.final_state = "BLINK"

            else:

                state.eyes_closed_start = None
                state.final_state = "NO EYES"

            # ------------------------------------------------
            # FACE BOX
            # ------------------------------------------------

            xs = [
                int(point.x * frame.shape[1])
                for point in landmarks
            ]

            ys = [
                int(point.y * frame.shape[0])
                for point in landmarks
            ]

            x_min = max(0, min(xs))
            x_max = min(frame.shape[1], max(xs))

            y_min = max(0, min(ys))
            y_max = min(frame.shape[0], max(ys))

            # Add small margin
            margin = 15

            x_min = max(0, x_min - margin)
            y_min = max(0, y_min - margin)
            x_max = min(frame.shape[1], x_max + margin)
            y_max = min(frame.shape[0], y_max + margin)

            # ------------------------------------------------
            # Draw face rectangle
            # ------------------------------------------------

            cv2.rectangle(
                frame,
                (x_min, y_min),
                (x_max, y_max),
                (255, 255, 255),
                2
            )

            # ------------------------------------------------
            # Draw eye landmark boxes
            # ------------------------------------------------

            def draw_eye_box(points):

                eye_x = [
                    int(landmarks[i].x * frame.shape[1])
                    for i in points
                ]

                eye_y = [
                    int(landmarks[i].y * frame.shape[0])
                    for i in points
                ]

                ex1 = max(0, min(eye_x))
                ex2 = min(frame.shape[1], max(eye_x))

                ey1 = max(0, min(eye_y))
                ey2 = min(frame.shape[0], max(eye_y))

                # Slight expansion for visibility
                ex_margin = max(5, int((ex2 - ex1) * 0.25))
                ey_margin = max(5, int((ey2 - ey1) * 0.40))

                ex1 = max(0, ex1 - ex_margin)
                ex2 = min(frame.shape[1], ex2 + ex_margin)

                ey1 = max(0, ey1 - ey_margin)
                ey2 = min(frame.shape[0], ey2 + ey_margin)

                cv2.rectangle(
                    frame,
                    (ex1, ey1),
                    (ex2, ey2),
                    (255, 255, 255),
                    1
                )

            draw_eye_box(LEFT_EYE_POINTS)
            draw_eye_box(RIGHT_EYE_POINTS)

            # ------------------------------------------------
            # Text positions
            # ------------------------------------------------

            text_x = x_min
            text_y = max(25, y_min - 10)

            # Face number
            draw_text(
                frame,
                f"Face {face_id + 1}",
                (text_x, text_y),
                0.65,
                2
            )

            # ------------------------------------------------
            # Eye state
            # ------------------------------------------------

            eye_text = f"Eyes: {state.final_state}"

            draw_text(
                frame,
                eye_text,
                (text_x, y_max + 25),
                0.65,
                2
            )

            # ------------------------------------------------
            # Head direction
            # ------------------------------------------------

            draw_text(
                frame,
                f"Head: {head_direction}",
                (text_x, y_max + 50),
                0.60,
                2
            )

            # ------------------------------------------------
            # Individual eye predictions
            # ------------------------------------------------

            draw_text(
                frame,
                f"L: {left} {state.left_confidence:.1f}%",
                (text_x, y_max + 80),
                0.55,
                2
            )

            draw_text(
                frame,
                f"R: {right} {state.right_confidence:.1f}%",
                (text_x, y_max + 105),
                0.55,
                2
            )

            # ------------------------------------------------
            # Closed timer
            # ------------------------------------------------

            if state.eyes_closed_start is not None:

                closed_time = (
                    time.time()
                    - state.eyes_closed_start
                )

                draw_text(
                    frame,
                    f"Closed: {closed_time:.1f}s",
                    (text_x, y_max + 130),
                    0.55,
                    2
                )

        # ----------------------------------------------------
        # Display
        # ----------------------------------------------------

        cv2.imshow(
            "AI Classroom - Combined Detection",
            frame
        )

        # ----------------------------------------------------
        # Quit
        # ----------------------------------------------------

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break

    # --------------------------------------------------------
    # Cleanup
    # --------------------------------------------------------

    cap.release()
    cv2.destroyAllWindows()
    landmarker.close()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()