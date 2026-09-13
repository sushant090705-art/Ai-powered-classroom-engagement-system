import cv2
import mediapipe as mp
import numpy as np
import os


# ============================================================
# PATH TO MEDIAPIPE FACE LANDMARKER MODEL
# ============================================================

MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "models",
    "mediapipe",
    "face_landmarker.task"
)

MODEL_PATH = os.path.abspath(MODEL_PATH)


# Check model file
if not os.path.exists(MODEL_PATH):
    print("Error: Face Landmarker model not found.")
    print("Expected path:")
    print(MODEL_PATH)
    exit()


# ============================================================
# MEDIAPIPE FACE LANDMARKER
# ============================================================

BaseOptions = mp.tasks.BaseOptions
FaceLandmarker = mp.tasks.vision.FaceLandmarker
FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode


options = FaceLandmarkerOptions(
    base_options=BaseOptions(
        model_asset_path=MODEL_PATH
    ),
    running_mode=VisionRunningMode.IMAGE,
    num_faces=5,
    min_face_detection_confidence=0.5,
    min_face_presence_confidence=0.5,
    min_tracking_confidence=0.5
)


# ============================================================
# HEAD POSE FUNCTION
# ============================================================

def get_head_direction(face_landmarks, frame_width, frame_height):

    # Important facial landmarks
    nose = face_landmarks[1]

    left_eye = face_landmarks[33]
    right_eye = face_landmarks[263]

    forehead = face_landmarks[10]
    chin = face_landmarks[152]

    # Convert normalized coordinates to pixels
    nose_x = int(nose.x * frame_width)
    nose_y = int(nose.y * frame_height)

    left_eye_x = int(left_eye.x * frame_width)
    right_eye_x = int(right_eye.x * frame_width)

    forehead_y = int(forehead.y * frame_height)
    chin_y = int(chin.y * frame_height)

    # --------------------------------------------------------
    # LEFT / RIGHT
    # --------------------------------------------------------

    eye_center_x = (left_eye_x + right_eye_x) / 2

    horizontal_difference = nose_x - eye_center_x

    # --------------------------------------------------------
    # UP / DOWN
    # --------------------------------------------------------

    face_height = abs(chin_y - forehead_y)

    vertical_ratio = 0

    if face_height > 0:
        vertical_ratio = (
            nose_y - forehead_y
        ) / face_height

    # --------------------------------------------------------
    # Determine direction
    # --------------------------------------------------------

    if horizontal_difference > frame_width * 0.035:
        direction = "RIGHT"

    elif horizontal_difference < -frame_width * 0.035:
        direction = "LEFT"

    elif vertical_ratio < 0.38:
        direction = "UP"

    elif vertical_ratio > 0.62:
        direction = "DOWN"

    else:
        direction = "CENTER"

    return direction, nose_x, nose_y


# ============================================================
# START CAMERA
# ============================================================

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Error: Could not open webcam.")
    exit()


print("Webcam started.")
print("Move your head LEFT / RIGHT / UP / DOWN.")
print("Press Q to quit.")


# ============================================================
# RUN MEDIAPIPE
# ============================================================

with FaceLandmarker.create_from_options(options) as landmarker:

    while True:

        ret, frame = cap.read()

        if not ret:
            print("Error: Could not read webcam frame.")
            break

        frame_height, frame_width, _ = frame.shape

        # OpenCV BGR → RGB
        rgb_frame = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        # Create MediaPipe image
        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb_frame
        )

        # Detect faces
        result = landmarker.detect(mp_image)

        # ----------------------------------------------------
        # Process every detected face
        # ----------------------------------------------------

        if result.face_landmarks:

            for face_id, face_landmarks in enumerate(
                result.face_landmarks
            ):

                direction, nose_x, nose_y = get_head_direction(
                    face_landmarks,
                    frame_width,
                    frame_height
                )

                # ------------------------------------------------
                # Draw nose
                # ------------------------------------------------

                cv2.circle(
                    frame,
                    (nose_x, nose_y),
                    6,
                    (0, 255, 0),
                    -1
                )

                # ------------------------------------------------
                # Draw face landmarks
                # ------------------------------------------------

                for landmark in face_landmarks:

                    x = int(landmark.x * frame_width)
                    y = int(landmark.y * frame_height)

                    cv2.circle(
                        frame,
                        (x, y),
                        1,
                        (255, 255, 255),
                        -1
                    )

                # ------------------------------------------------
                # Display direction
                # ------------------------------------------------

                cv2.putText(
                    frame,
                    f"Face {face_id + 1}: {direction}",
                    (20, 40 + face_id * 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (0, 255, 255),
                    2
                )

                # Nose coordinates
                cv2.putText(
                    frame,
                    f"Nose: ({nose_x}, {nose_y})",
                    (20, 70 + face_id * 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (255, 255, 255),
                    1
                )

        else:

            cv2.putText(
                frame,
                "No face detected",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 0, 255),
                2
            )

        # --------------------------------------------------------
        # Show camera
        # --------------------------------------------------------

        cv2.imshow(
            "Head Pose Detection",
            frame
        )

        # Q → quit
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break


# ============================================================
# CLEANUP
# ============================================================

cap.release()
cv2.destroyAllWindows()

print("Head pose detection stopped.")