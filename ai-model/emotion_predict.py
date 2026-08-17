import os
import cv2
import numpy as np
import tensorflow as tf

# =========================
# MODEL PATH
# =========================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_PATH = os.path.join(
    BASE_DIR,
    "emotion",
    "emotion_model.keras"
)

# =========================
# LOAD MODEL
# =========================

print("Loading emotion model...")

model = tf.keras.models.load_model(MODEL_PATH)

print("Emotion model loaded successfully!")

# =========================
# EMOTION LABELS
# =========================

emotion_labels = [
    "Angry",
    "Disgust",
    "Fear",
    "Happy",
    "Sad",
    "Surprise",
    "Neutral"
]

# =========================
# FACE DETECTOR
# =========================

face_detector = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

# =========================
# START WEBCAM
# =========================

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

if not cap.isOpened():
    print("ERROR: Could not open webcam.")
    exit()

print("Webcam started.")
print("Press Q to quit.")

while True:

    ret, frame = cap.read()

    if not ret:
        print("ERROR: Could not read webcam frame.")
        break
    frame = cv2.flip(frame, -1)

    # Convert frame to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Detect faces
    faces = face_detector.detectMultiScale(
        gray,
        scaleFactor=1.3,
        minNeighbors=5,
        minSize=(50, 50)
    )

    for (x, y, w, h) in faces:

        # Extract face
        face = gray[y:y + h, x:x + w]

        # Resize to model input size
        face = cv2.resize(face, (48, 48))

        # Normalize
        face = face.astype("float32") / 255.0

        # Reshape
        face = np.expand_dims(face, axis=0)
        face = np.expand_dims(face, axis=-1)

        # Predict emotion
        predictions = model.predict(face, verbose=0)

        emotion_index = np.argmax(predictions[0])
        emotion = emotion_labels[emotion_index]

        confidence = float(predictions[0][emotion_index]) * 100

        # Draw rectangle
        cv2.rectangle(
            frame,
            (x, y),
            (x + w, y + h),
            (0, 255, 0),
            2
        )

        # Display emotion
        text = f"{emotion}: {confidence:.1f}%"

        cv2.putText(
            frame,
            text,
            (x, y - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2
        )

    # Display camera
    cv2.imshow(
        "Classroom AI - Emotion Detection",
        frame
    )

    # Press Q to quit
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

# =========================
# CLEANUP
# =========================

cap.release()
cv2.destroyAllWindows()

print("Emotion detection stopped.")