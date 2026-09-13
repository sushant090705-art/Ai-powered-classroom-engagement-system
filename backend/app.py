from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from pymongo import MongoClient

import os
import cv2
import numpy as np
import tensorflow as tf
import threading
import time
from ultralytics import YOLO

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
# LOAD YOLO MODEL
# ============================================================

print("Loading YOLO model...")

yolo_model = YOLO(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "yolov8n.pt"
    )
)

print("YOLO model loaded successfully!")

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
    "models",
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
    "Neutral",
    "Sad",
    "Surprise"
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

    results = []

    # -----------------------------------
    # 1. YOLO: Detect persons
    # -----------------------------------

    yolo_results = yolo_model(
        frame,
        classes=[0],
        conf=0.40,
        verbose=False
    )

    # -----------------------------------
    # 2. Process each detected person
    # -----------------------------------

    for box in yolo_results[0].boxes:

        x1, y1, x2, y2 = map(
            int,
            box.xyxy[0].tolist()
        )

        # Keep coordinates inside frame
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(frame.shape[1], x2)
        y2 = min(frame.shape[0], y2)

        # Crop person
        person_crop = frame[
            y1:y2,
            x1:x2
        ]

        if person_crop.size == 0:
            continue

        # -----------------------------------
        # 3. Haar: Detect face inside person
        # -----------------------------------

        gray_person = cv2.cvtColor(
            person_crop,
            cv2.COLOR_BGR2GRAY
        )

        faces = face_detector.detectMultiScale(
            gray_person,
            scaleFactor=1.3,
            minNeighbors=5,
            minSize=(50, 50)
        )

        # -----------------------------------
        # 4. Process each face
        # -----------------------------------

        for (fx, fy, fw, fh) in faces:

            face = gray_person[
                fy:fy + fh,
                fx:fx + fw
            ]

            if face.size == 0:
                continue

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

            # -----------------------------------
            # 5. Emotion prediction
            # -----------------------------------

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

            # Convert face coordinates
            # back to original frame
            face_x = x1 + fx
            face_y = y1 + fy

            # -----------------------------------
            # 6. Store result
            # -----------------------------------

            result = {
                "emotion": emotion,
                "confidence": round(
                    confidence,
                    2
                ),
                "x": int(face_x),
                "y": int(face_y),
                "width": int(fw),
                "height": int(fh),

                # YOLO person coordinates
                "person_x": int(x1),
                "person_y": int(y1),
                "person_width": int(x2 - x1),
                "person_height": int(y2 - y1)
            }

            results.append(result)

            # -----------------------------------
            # 7. Draw face rectangle
            # -----------------------------------

            cv2.rectangle(
                frame,
                (face_x, face_y),
                (face_x + fw, face_y + fh),
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
                (face_x, max(face_y - 10, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )

        # -----------------------------------
        # 8. Draw YOLO person rectangle
        # -----------------------------------

        cv2.rectangle(
            frame,
            (x1, y1),
            (x2, y2),
            (255, 0, 0),
            2
        )

        cv2.putText(
            frame,
            "Person",
            (x1, max(y1 - 10, 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 0, 0),
            2
        )

    # -----------------------------------
    # 9. Save latest results
    # -----------------------------------

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
# RECORDED VIDEO ANALYSIS
# ============================================================

@app.route("/analyze-video", methods=["POST"])
def analyze_video():
    video_path = None
    cap = None

    try:
        if "video" not in request.files:
            return jsonify({
                "success": False,
                "message": "No video received"
            }), 400

        video_file = request.files["video"]

        if video_file.filename == "":
            return jsonify({
                "success": False,
                "message": "No video selected"
            }), 400

        # Temporary upload folder
        upload_folder = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "uploads"
        )

        os.makedirs(upload_folder, exist_ok=True)

        video_path = os.path.join(
            upload_folder,
            "uploaded_video.mp4"
        )

        video_file.save(video_path)

        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            return jsonify({
                "success": False,
                "message": "Could not open video"
            }), 400

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)

        if fps <= 0:
            fps = 25

        video_duration = total_frames / fps

        emotion_counts = {}
        total_faces = 0
        processed_frames = 0

        # Process approximately one frame every second
        frame_interval = max(int(fps), 1)

        while True:
            success, frame = cap.read()

            if not success:
                break

            current_frame_number = int(
                cap.get(cv2.CAP_PROP_POS_FRAMES)
            )

            if current_frame_number % frame_interval != 0:
                continue

            results = process_frame(frame)

            processed_frames += 1
            total_faces += len(results)

            for result in results:
                emotion = result["emotion"]

                if emotion not in emotion_counts:
                    emotion_counts[emotion] = 0

                emotion_counts[emotion] += 1

        cap.release()
        cap = None

        most_common_emotion = "Unknown"

        if emotion_counts:
            most_common_emotion = max(
                emotion_counts,
                key=emotion_counts.get
            )

        return jsonify({
            "success": True,
            "message": "Video analyzed successfully",
            "duration_seconds": round(video_duration, 2),
            "total_frames": total_frames,
            "processed_frames": processed_frames,
            "total_faces_detected": total_faces,
            "emotion_counts": emotion_counts,
            "most_common_emotion": most_common_emotion
        })

    except Exception as e:
        print("VIDEO ANALYSIS ERROR:", e)

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

    finally:
        if cap is not None:
            cap.release()

        if video_path and os.path.exists(video_path):
            os.remove(video_path)

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