from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from pymongo import MongoClient

import os
import cv2
import numpy as np
import tensorflow as tf
import threading
import time


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)
CORS(app)


# ============================================================
# MONGODB ATLAS
# ============================================================

# IMPORTANT:
# Do not hard-code your MongoDB password in production.
# Use an environment variable instead.

MONGO_URI = os.environ.get(
    "MONGO_URI",
    "YOUR_MONGODB_CONNECTION_STRING"
)

client = MongoClient(MONGO_URI)

db = client["classroom_engagement"]
users = db["users"]

print("MongoDB connected successfully!")


# ============================================================
# MOBILE CAMERA
# ============================================================

# Camera URL will be provided from the React frontend
MOBILE_CAMERA_URL = ""

camera = None

camera_lock = threading.Lock()

latest_results = []

results_lock = threading.Lock()

# ============================================================
# LOAD EMOTION MODEL
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

MODEL_PATH = os.path.join(
    BASE_DIR,
    "ai-model",
    "emotion",
    "emotion_model.keras"
)

print("Loading emotion model...")

emotion_model = tf.keras.models.load_model(
    MODEL_PATH
)

print("Emotion model loaded successfully!")


# ============================================================
# EMOTION LABELS
# ============================================================

emotion_labels = [
    "Angry",
    "Disgust",
    "Fear",
    "Happy",
    "Sad",
    "Surprise",
    "Neutral"
]


# ============================================================
# FACE DETECTOR
# ============================================================

face_detector = cv2.CascadeClassifier(
    cv2.data.haarcascades +
    "haarcascade_frontalface_default.xml"
)


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    return "Classroom Engagement AI Backend Running!"


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["POST"])
def register():

    data = request.json

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({
            "success": False,
            "message": "Email and password are required"
        }), 400

    existing_user = users.find_one({
        "email": email
    })

    if existing_user:
        return jsonify({
            "success": False,
            "message": "Account already exists"
        }), 409

    users.insert_one({
        "email": email,
        "password": password
    })

    return jsonify({
        "success": True,
        "message": "Account created successfully"
    }), 201


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["POST"])
def login():

    data = request.json

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({
            "success": False,
            "message": "Email and password are required"
        }), 400

    user = users.find_one({
        "email": email,
        "password": password
    })

    if user:

        return jsonify({
            "success": True,
            "message": "Login successful"
        })

    return jsonify({
        "success": False,
        "message": "Invalid email or password"
    }), 401


# ============================================================
# SINGLE IMAGE EMOTION PREDICTION
# ============================================================

@app.route("/predict-emotion", methods=["POST"])
def predict_emotion():

    try:

        if "image" not in request.files:

            return jsonify({
                "success": False,
                "message": "No image received"
            }), 400

        image_file = request.files["image"]

        image_bytes = image_file.read()

        image_array = np.frombuffer(
            image_bytes,
            np.uint8
        )

        frame = cv2.imdecode(
            image_array,
            cv2.IMREAD_COLOR
        )

        if frame is None:

            return jsonify({
                "success": False,
                "message": "Invalid image"
            }), 400

        results = process_frame(frame)

        return jsonify({
            "success": True,
            "faces": results,
            "faces_detected": len(results)
        })

    except Exception as e:

        print("FER ERROR:", e)

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# ============================================================
# PROCESS FRAME
# ============================================================

def process_frame(frame):

    global latest_results

    # Convert to grayscale
    gray = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2GRAY
    )

    # Detect faces
    faces = face_detector.detectMultiScale(
        gray,
        scaleFactor=1.3,
        minNeighbors=5,
        minSize=(50, 50)
    )

    results = []

    for (x, y, w, h) in faces:

        # Extract face
        face = gray[
            y:y + h,
            x:x + w
        ]

        # Resize
        face = cv2.resize(
            face,
            (48, 48)
        )

        # Normalize
        face = face.astype(
            "float32"
        ) / 255.0

        # Reshape
        face = np.expand_dims(
            face,
            axis=0
        )

        face = np.expand_dims(
            face,
            axis=-1
        )

        # Predict
        predictions = emotion_model.predict(
            face,
            verbose=0
        )

        emotion_index = np.argmax(
            predictions[0]
        )

        emotion = emotion_labels[
            emotion_index
        ]

        confidence = (
            float(
                predictions[0][emotion_index]
            ) * 100
        )

        result = {
            "emotion": emotion,
            "confidence": round(
                confidence,
                2
            ),
            "x": int(x),
            "y": int(y),
            "width": int(w),
            "height": int(h)
        }

        results.append(result)

        # Draw face rectangle
        cv2.rectangle(
            frame,
            (x, y),
            (x + w, y + h),
            (0, 255, 0),
            2
        )

        # Display emotion
        text = (
            f"{emotion}: "
            f"{confidence:.1f}%"
        )

        cv2.putText(
            frame,
            text,
            (x, y - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2
        )

    # Save latest results
    with results_lock:

        latest_results = results

    return results


# ============================================================
# MOBILE CAMERA CONNECTION
# ============================================================

def get_camera():

    global camera

    if not MOBILE_CAMERA_URL:
        return None

    with camera_lock:

        if camera is None or not camera.isOpened():

            print(
                "Connecting to mobile camera:"
            )

            print(
                MOBILE_CAMERA_URL
            )

            camera = cv2.VideoCapture(
                MOBILE_CAMERA_URL
            )

            if camera.isOpened():

                print(
                    "Mobile camera connected successfully!"
                )

            else:

                print(
                    "ERROR: Could not connect to mobile camera."
                )

        return camera


# ============================================================
# CAMERA CONNECTION API
# ============================================================

@app.route("/camera/connect", methods=["POST"])
def connect_camera():

    global MOBILE_CAMERA_URL, camera

    data = request.get_json()

    if not data or "url" not in data:
        return jsonify({
            "success": False,
            "message": "Camera URL is required"
        }), 400

    new_url = data["url"].strip()

    if not new_url:
        return jsonify({
            "success": False,
            "message": "Camera URL cannot be empty"
        }), 400

    with camera_lock:

        if camera is not None:
            camera.release()
            camera = None

        MOBILE_CAMERA_URL = new_url

    print("--------------------------------")
    print("Camera URL updated:")
    print(MOBILE_CAMERA_URL)
    print("--------------------------------")

    return jsonify({
        "success": True,
        "message": "Camera connected successfully",
        "url": MOBILE_CAMERA_URL
    })


@app.route("/camera/status", methods=["GET"])
def camera_status():

    global MOBILE_CAMERA_URL, camera

    connected = (
        MOBILE_CAMERA_URL != ""
        and camera is not None
        and camera.isOpened()
    )

    return jsonify({
        "connected": connected,
        "url": MOBILE_CAMERA_URL
    })


@app.route("/camera/disconnect", methods=["POST"])
def disconnect_camera():

    global MOBILE_CAMERA_URL, camera

    with camera_lock:

        if camera is not None:
            camera.release()
            camera = None

        MOBILE_CAMERA_URL = ""

    print("Camera disconnected")

    return jsonify({
        "success": True,
        "message": "Camera disconnected"
    })


# ============================================================
# LIVE VIDEO GENERATOR
# ============================================================

def generate_frames():

    global camera

    while True:

        cap = get_camera()

        if cap is None or not cap.isOpened():

            print(
                "Waiting for mobile camera..."
            )

            time.sleep(2)

            continue

        success, frame = cap.read()

        if not success:

            print(
                "Could not read mobile camera frame."
            )

            with camera_lock:

                cap.release()
                camera = None

            time.sleep(1)

            continue

        # Process frame using AI
        process_frame(frame)

        # Encode frame as JPEG
        success, buffer = cv2.imencode(
            ".jpg",
            frame
        )

        if not success:
            continue

        frame_bytes = buffer.tobytes()

        # Send frame to browser
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + frame_bytes
            + b"\r\n"
        )


# ============================================================
# LIVE VIDEO API
# ============================================================

@app.route("/video_feed")
def video_feed():

    return Response(
        generate_frames(),
        mimetype=(
            "multipart/x-mixed-replace; "
            "boundary=frame"
        )
    )


# ============================================================
# LATEST EMOTION RESULTS
# ============================================================

@app.route("/emotion-results")
def emotion_results():

    with results_lock:

        results_copy = list(
            latest_results
        )

    return jsonify({
        "success": True,
        "faces_detected": len(
            results_copy
        ),
        "faces": results_copy
    })


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    print("--------------------------------")
    print("Classroom AI Backend")
    print("--------------------------------")

    print(
        "Mobile Camera:",
        MOBILE_CAMERA_URL
    )

    print(
        "Live Video:"
    )

    print(
        "http://127.0.0.1:5000/video_feed"
    )

    print(
        "Emotion Results:"
    )

    print(
        "http://127.0.0.1:5000/emotion-results"
    )

    print("--------------------------------")

    # IMPORTANT:
    # use_reloader=False prevents Flask
    # from starting the camera twice.

    app.run(
        debug=True,
        use_reloader=False,
        host="0.0.0.0",
        port=5000
    )