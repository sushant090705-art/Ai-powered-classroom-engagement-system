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

MONGO_URI = os.environ.get(
    "MONGO_URI",
    "YOUR_MONGODB_CONNECTION_STRING"
)

client = MongoClient(MONGO_URI)

db = client["classroom_engagement"]
users = db["users"]

print("MongoDB connected successfully!")


# ============================================================
# CAMERA VARIABLES
# ============================================================

MOBILE_CAMERA_URL = ""

camera = None

camera_lock = threading.Lock()

latest_frame = None
frame_lock = threading.Lock()

latest_results = []
results_lock = threading.Lock()

ai_thread = None
ai_running = False

AI_INTERVAL = 0.5


# ============================================================
# EYE STATE TRACKING
# ============================================================

# Less than this = Blink
BLINK_MAX_DURATION = 0.8

# 0.8 - 3 seconds = Drowsy
DROWSY_THRESHOLD = 3.0

# More than 3 seconds = Sleeping
SLEEPING_THRESHOLD = 3.0

# How long Blink remains displayed after reopening
BLINK_DISPLAY_DURATION = 0.5

# Store tracking information for each detected face
eye_tracks = {}

eye_tracks_lock = threading.Lock()

next_track_id = 0


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
# LOAD MRL EYE MODEL
# ============================================================

MRL_MODEL_PATH = os.path.join(
    BASE_DIR,
    "ai-model",
    "models",
    "mrl_eye_model.keras"
)

print("Loading MRL eye model...")

mrl_eye_model = tf.keras.models.load_model(
    MRL_MODEL_PATH
)

print("MRL eye model loaded successfully!")


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
# FACE / EYE DETECTORS
# ============================================================

face_detector = cv2.CascadeClassifier(
    cv2.data.haarcascades +
    "haarcascade_frontalface_default.xml"
)

eye_detector = cv2.CascadeClassifier(
    cv2.data.haarcascades +
    "haarcascade_eye.xml"
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
# MRL EYE PREDICTION
# ============================================================

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

        eye_image = (
            eye_image.astype("float32") / 255.0
        )

        eye_image = np.expand_dims(
            eye_image,
            axis=0
        )

        prediction = mrl_eye_model.predict(
            eye_image,
            verbose=0
        )[0][0]

        # MRL model:
        # < 0.5 = Open
        # >= 0.5 = Close

        if prediction < 0.5:

            eye_state = "Open"

            confidence = (
                1 - prediction
            ) * 100

        else:

            eye_state = "Close"

            confidence = (
                prediction
            ) * 100

        return (
            eye_state,
            float(confidence)
        )

    except Exception as e:

        print(
            "MRL prediction error:",
            e
        )

        return "Unknown", 0.0


# ============================================================
# GET TRACK ID FOR EACH FACE
# ============================================================

def get_eye_track_id(
    center_x,
    center_y
):

    global next_track_id

    current_time = time.time()

    with eye_tracks_lock:

        # Remove old face tracks
        old_tracks = [

            track_id

            for track_id, track
            in eye_tracks.items()

            if (
                current_time
                -
                track["last_seen"]
                >
                2.0
            )
        ]

        for track_id in old_tracks:

            del eye_tracks[track_id]

        # Find closest existing face
        best_track_id = None

        best_distance = float("inf")

        for track_id, track in eye_tracks.items():

            distance = np.sqrt(

                (
                    center_x
                    -
                    track["center_x"]
                ) ** 2

                +

                (
                    center_y
                    -
                    track["center_y"]
                ) ** 2
            )

            if (
                distance < best_distance
                and
                distance < 120
            ):

                best_distance = distance

                best_track_id = track_id

        # New face
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

                "was_sleeping": False
            }

        else:

            eye_tracks[
                best_track_id
            ]["center_x"] = center_x

            eye_tracks[
                best_track_id
            ]["center_y"] = center_y

            eye_tracks[
                best_track_id
            ]["last_seen"] = current_time

        return best_track_id


# ============================================================
# CONVERT RAW EYE STATE TO DISPLAY STATE
# ============================================================

def update_eye_display_state(
    track_id,
    raw_state
):

    current_time = time.time()

    with eye_tracks_lock:

        if track_id not in eye_tracks:

            return raw_state

        track = eye_tracks[
            track_id
        ]

        previous_state = (
            track["previous_raw_state"]
        )

        # ====================================================
        # EYES CLOSED
        # ====================================================

        if raw_state == "Close":

            # Eyes have just closed
            if previous_state != "Close":

                track["closed_since"] = (
                    current_time
                )

            if track["closed_since"] is not None:

                closed_duration = (
                    current_time
                    -
                    track["closed_since"]
                )

            else:

                closed_duration = 0

            track[
                "previous_raw_state"
            ] = "Close"

            # More than 3 seconds
            if (
                closed_duration
                >=
                SLEEPING_THRESHOLD
            ):

                track[
                    "was_sleeping"
                ] = True

                return "Sleeping"

            # 0.8 - 3 seconds
            elif (
                closed_duration
                >=
                BLINK_MAX_DURATION
            ):

                return "Drowsy"

            # Less than 0.8 seconds
            else:

                return "Close"

        # ====================================================
        # EYES OPEN
        # ====================================================

        elif raw_state == "Open":

            closed_duration = 0

            if (
                track["closed_since"]
                is not None
            ):

                closed_duration = (
                    current_time
                    -
                    track["closed_since"]
                )

            track[
                "previous_raw_state"
            ] = "Open"

            track[
                "closed_since"
            ] = None

            # If person was sleeping,
            # reopening = Open
            if track["was_sleeping"]:

                track[
                    "was_sleeping"
                ] = False

                track[
                    "blink_until"
                ] = 0

                return "Open"

            # Quick close + reopen = Blink
            if (
                closed_duration > 0
                and
                closed_duration
                <
                BLINK_MAX_DURATION
            ):

                track[
                    "blink_until"
                ] = (
                    current_time
                    +
                    BLINK_DISPLAY_DURATION
                )

                return "Blink"

            # Keep Blink visible briefly
            if (
                current_time
                <
                track["blink_until"]
            ):

                return "Blink"

            return "Open"

        # ====================================================
        # UNKNOWN
        # ====================================================

        else:

            return "Unknown"


# ============================================================
# PROCESS FRAME
# ============================================================

def process_frame(frame):

    results = []

    try:

        # ====================================================
        # 1. YOLO PERSON DETECTION
        # ====================================================

        yolo_results = yolo_model(
            frame,
            classes=[0],
            conf=0.40,
            verbose=False
        )

        # ====================================================
        # 2. PROCESS EACH PERSON
        # ====================================================

        for box in yolo_results[0].boxes:

            x1, y1, x2, y2 = map(
                int,
                box.xyxy[0].tolist()
            )

            x1 = max(0, x1)
            y1 = max(0, y1)

            x2 = min(
                frame.shape[1],
                x2
            )

            y2 = min(
                frame.shape[0],
                y2
            )

            person_crop = frame[
                y1:y2,
                x1:x2
            ]

            if person_crop.size == 0:

                continue

            # =================================================
            # 3. FACE DETECTION
            # =================================================

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

            # =================================================
            # 4. PROCESS EACH FACE
            # =================================================

            for (
                fx,
                fy,
                fw,
                fh
            ) in faces:

                face_color = person_crop[
                    fy:fy + fh,
                    fx:fx + fw
                ]

                face_gray = gray_person[
                    fy:fy + fh,
                    fx:fx + fw
                ]

                if (
                    face_color.size == 0
                    or
                    face_gray.size == 0
                ):

                    continue

                # =================================================
                # 5. EMOTION MODEL
                # =================================================

                emotion_input = cv2.resize(
                    face_gray,
                    (48, 48)
                )

                emotion_input = (
                    emotion_input.astype(
                        "float32"
                    ) / 255.0
                )

                emotion_input = np.expand_dims(
                    emotion_input,
                    axis=0
                )

                emotion_input = np.expand_dims(
                    emotion_input,
                    axis=-1
                )

                predictions = emotion_model.predict(
                    emotion_input,
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
                        predictions[0][
                            emotion_index
                        ]
                    )
                    *
                    100
                )

                # =================================================
                # 6. EYE DETECTION
                # =================================================

                eyes = eye_detector.detectMultiScale(
                    face_gray,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(15, 15)
                )

                eye_predictions = []

                # =================================================
                # FIRST: USE HAAR DETECTED EYES
                # =================================================

                for (
                    ex,
                    ey,
                    ew,
                    eh
                ) in eyes[:2]:

                    eye_crop = face_color[
                        ey:ey + eh,
                        ex:ex + ew
                    ]

                    if eye_crop.size == 0:

                        continue

                    (
                        eye_state_single,
                        eye_confidence_single
                    ) = predict_eye_state(
                        eye_crop
                    )

                    eye_predictions.append(
                        (
                            eye_state_single,
                            eye_confidence_single
                        )
                    )

                # =================================================
                # FALLBACK:
                # IF HAAR DOES NOT FIND EYES
                #
                # This is important when eyes are closed.
                # =================================================

                if not eye_predictions:

                    face_h, face_w = (
                        face_color.shape[:2]
                    )

                    # Left eye region
                    left_x1 = int(
                        face_w * 0.10
                    )

                    left_x2 = int(
                        face_w * 0.48
                    )

                    eye_y1 = int(
                        face_h * 0.18
                    )

                    eye_y2 = int(
                        face_h * 0.48
                    )

                    # Right eye region
                    right_x1 = int(
                        face_w * 0.52
                    )

                    right_x2 = int(
                        face_w * 0.90
                    )

                    # Left eye crop
                    left_eye = face_color[
                        eye_y1:eye_y2,
                        left_x1:left_x2
                    ]

                    # Right eye crop
                    right_eye = face_color[
                        eye_y1:eye_y2,
                        right_x1:right_x2
                    ]

                    if left_eye.size != 0:

                        state, conf = (
                            predict_eye_state(
                                left_eye
                            )
                        )

                        eye_predictions.append(
                            (state, conf)
                        )

                    if right_eye.size != 0:

                        state, conf = (
                            predict_eye_state(
                                right_eye
                            )
                        )

                        eye_predictions.append(
                            (state, conf)
                        )

                # =================================================
                # 7. COMBINE EYE PREDICTIONS
                # =================================================

                if eye_predictions:

                    close_count = sum(

                        1

                        for (
                            state,
                            _
                        )
                        in eye_predictions

                        if state == "Close"
                    )

                    if (
                        close_count
                        >
                        len(eye_predictions) / 2
                    ):

                        raw_eye_state = "Close"

                    else:

                        raw_eye_state = "Open"

                    eye_confidence = (
                        sum(
                            confidence_value

                            for (
                                _,
                                confidence_value
                            )
                            in eye_predictions
                        )
                        /
                        len(
                            eye_predictions
                        )
                    )

                    # =================================================
                    # 8. FACE CENTER
                    # =================================================

                    face_center_x = (
                        x1
                        +
                        fx
                        +
                        fw // 2
                    )

                    face_center_y = (
                        y1
                        +
                        fy
                        +
                        fh // 2
                    )

                    # =================================================
                    # 9. TRACK THIS FACE
                    # =================================================

                    track_id = get_eye_track_id(
                        face_center_x,
                        face_center_y
                    )

                    # =================================================
                    # 10. CONVERT TO DISPLAY STATE
                    # =================================================

                    eye_state = (
                        update_eye_display_state(
                            track_id,
                            raw_eye_state
                        )
                    )
                    print(
    f"Track {track_id} | Raw Eye: {raw_eye_state} | "
    f"Display Eye: {eye_state}"
)

                else:

                    eye_state = "Unknown"

                    eye_confidence = 0.0

                # =================================================
                # 11. ORIGINAL FRAME COORDINATES
                # =================================================

                face_x = x1 + fx
                face_y = y1 + fy

                # =================================================
                # 12. STORE RESULT
                # =================================================

                result = {

                    "emotion": emotion,

                    "confidence": round(
                        confidence,
                        2
                    ),

                    "eye_state": eye_state,

                    "eye_confidence": round(
                        eye_confidence,
                        2
                    ),

                    "x": int(face_x),

                    "y": int(face_y),

                    "width": int(fw),

                    "height": int(fh),

                    "person_x": int(x1),

                    "person_y": int(y1),

                    "person_width": int(
                        x2 - x1
                    ),

                    "person_height": int(
                        y2 - y1
                    )
                }

                results.append(result)

                # =================================================
                # 13. DRAW FACE
                # =================================================

                cv2.rectangle(
                    frame,
                    (
                        face_x,
                        face_y
                    ),
                    (
                        face_x + fw,
                        face_y + fh
                    ),
                    (0, 255, 0),
                    2
                )

                # =================================================
                # 14. DRAW DETECTED EYES
                # =================================================

                for (
                    ex,
                    ey,
                    ew,
                    eh
                ) in eyes[:2]:

                    cv2.rectangle(
                        frame,
                        (
                            face_x + ex,
                            face_y + ey
                        ),
                        (
                            face_x + ex + ew,
                            face_y + ey + eh
                        ),
                        (255, 0, 0),
                        2
                    )

                # =================================================
                # 15. DISPLAY EMOTION
                # =================================================

                text = (
                    f"{emotion}: "
                    f"{confidence:.1f}%"
                )

                eye_text = (
                    f"Eyes: "
                    f"{eye_state}"
                )

                cv2.putText(
                    frame,
                    text,
                    (
                        face_x,
                        max(
                            face_y - 35,
                            20
                        )
                    ),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2
                )

                cv2.putText(
                    frame,
                    eye_text,
                    (
                        face_x,
                        max(
                            face_y - 10,
                            20
                        )
                    ),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 0, 0),
                    2
                )

            # =================================================
            # 16. DRAW YOLO PERSON BOX
            # =================================================

            cv2.rectangle(
                frame,
                (
                    x1,
                    y1
                ),
                (
                    x2,
                    y2
                ),
                (255, 0, 0),
                2
            )

            cv2.putText(
                frame,
                "Person",
                (
                    x1,
                    max(
                        y1 - 10,
                        20
                    )
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 0, 0),
                2
            )

    except Exception as e:

        print(
            "PROCESS FRAME ERROR:",
            e
        )

    return results


# ============================================================
# BACKGROUND AI PROCESSING
# ============================================================

def ai_processing_loop():

    global ai_running
    global latest_results

    print(
        "AI processing thread started."
    )

    last_process_time = 0

    while ai_running:

        current_time = time.time()

        if (
            current_time
            -
            last_process_time
            <
            AI_INTERVAL
        ):

            time.sleep(0.01)

            continue

        with frame_lock:

            if latest_frame is None:

                frame_copy = None

            else:

                frame_copy = latest_frame.copy()

        if frame_copy is None:

            time.sleep(0.05)

            continue

        last_process_time = current_time

        results = process_frame(
            frame_copy
        )

        with results_lock:

            latest_results = results

    print(
        "AI processing thread stopped."
    )


# ============================================================
# START AI THREAD
# ============================================================

def start_ai_thread():

    global ai_thread
    global ai_running

    if ai_running:

        return

    ai_running = True

    ai_thread = threading.Thread(
        target=ai_processing_loop,
        daemon=True
    )

    ai_thread.start()


# ============================================================
# STOP AI THREAD
# ============================================================

def stop_ai_thread():

    global ai_running

    ai_running = False


# ============================================================
# CAMERA CONNECTION
# ============================================================

def get_camera():

    global camera

    if not MOBILE_CAMERA_URL:

        return None

    with camera_lock:

        if (
            camera is None
            or
            not camera.isOpened()
        ):

            print(
                "Connecting to mobile camera:"
            )

            print(
                MOBILE_CAMERA_URL
            )

            camera = cv2.VideoCapture(
                MOBILE_CAMERA_URL
            )

            try:

                camera.set(
                    cv2.CAP_PROP_BUFFERSIZE,
                    1
                )

            except Exception:

                pass

            if camera.isOpened():

                print(
                    "Mobile camera connected successfully!"
                )

            else:

                print(
                    "ERROR: Could not connect "
                    "to mobile camera."
                )

        return camera


# ============================================================
# CAMERA CONNECT API
# ============================================================

@app.route(
    "/camera/connect",
    methods=["POST"]
)
def connect_camera():

    global MOBILE_CAMERA_URL
    global camera
    global latest_frame
    global eye_tracks

    data = request.get_json()

    if (
        not data
        or
        "url" not in data
    ):

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

    with frame_lock:

        latest_frame = None

    # Reset eye tracking
    with eye_tracks_lock:

        eye_tracks.clear()

    print("--------------------------------")

    print(
        "Camera URL updated:"
    )

    print(
        MOBILE_CAMERA_URL
    )

    print("--------------------------------")

    start_ai_thread()

    return jsonify({
        "success": True,
        "message": "Camera connected successfully",
        "url": MOBILE_CAMERA_URL
    })


# ============================================================
# CAMERA STATUS
# ============================================================

@app.route(
    "/camera/status",
    methods=["GET"]
)
def camera_status():

    global MOBILE_CAMERA_URL
    global camera

    connected = (
        MOBILE_CAMERA_URL != ""
        and
        camera is not None
        and
        camera.isOpened()
    )

    return jsonify({
        "connected": connected,
        "url": MOBILE_CAMERA_URL
    })


# ============================================================
# CAMERA DISCONNECT
# ============================================================

@app.route(
    "/camera/disconnect",
    methods=["POST"]
)
def disconnect_camera():

    global MOBILE_CAMERA_URL
    global camera
    global latest_frame
    global latest_results
    global eye_tracks

    stop_ai_thread()

    with camera_lock:

        if camera is not None:

            camera.release()

            camera = None

        MOBILE_CAMERA_URL = ""

    with frame_lock:

        latest_frame = None

    with results_lock:

        latest_results = []

    # Reset eye tracking
    with eye_tracks_lock:

        eye_tracks.clear()

    print(
        "Camera disconnected"
    )

    return jsonify({
        "success": True,
        "message": "Camera disconnected"
    })


# ============================================================
# CAMERA FRAME GENERATOR
# ============================================================

def generate_frames():

    global camera
    global latest_frame

    while True:

        cap = get_camera()

        if (
            cap is None
            or
            not cap.isOpened()
        ):

            time.sleep(1)

            continue

        success, frame = cap.read()

        if not success:

            print(
                "Could not read mobile camera frame."
            )

            with camera_lock:

                if camera is not None:

                    camera.release()

                camera = None

            time.sleep(1)

            continue

        # Save latest frame
        with frame_lock:

            latest_frame = frame.copy()

        # Get latest AI results
        with results_lock:

            results_copy = list(
                latest_results
            )

        # Draw AI results
        for result in results_copy:

            face_x = result["x"]
            face_y = result["y"]

            fw = result["width"]
            fh = result["height"]

            cv2.rectangle(
                frame,
                (
                    face_x,
                    face_y
                ),
                (
                    face_x + fw,
                    face_y + fh
                ),
                (0, 255, 0),
                2
            )

            emotion_text = (
                f'{result["emotion"]}: '
                f'{result["confidence"]:.1f}%'
            )

            eye_text = (
                f'Eyes: '
                f'{result["eye_state"]}'
            )

            cv2.putText(
                frame,
                emotion_text,
                (
                    face_x,
                    max(
                        face_y - 35,
                        20
                    )
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )

            cv2.putText(
                frame,
                eye_text,
                (
                    face_x,
                    max(
                        face_y - 10,
                        20
                    )
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 0, 0),
                2
            )

        # Encode JPEG
        success, buffer = cv2.imencode(
            ".jpg",
            frame
        )

        if not success:

            continue

        frame_bytes = buffer.tobytes()

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            +
            frame_bytes
            +
            b"\r\n"
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

@app.route(
    "/analyze-video",
    methods=["POST"]
)
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

        # ====================================================
        # UPLOAD FOLDER
        # ====================================================

        upload_folder = os.path.join(
            os.path.dirname(
                os.path.abspath(__file__)
            ),
            "uploads"
        )

        os.makedirs(
            upload_folder,
            exist_ok=True
        )

        filename = (
            f"uploaded_"
            f"{int(time.time())}.mp4"
        )

        video_path = os.path.join(
            upload_folder,
            filename
        )

        video_file.save(
            video_path
        )

        # ====================================================
        # OPEN VIDEO
        # ====================================================

        cap = cv2.VideoCapture(
            video_path
        )

        if not cap.isOpened():

            return jsonify({
                "success": False,
                "message": "Could not open video"
            }), 400

        total_frames = int(
            cap.get(
                cv2.CAP_PROP_FRAME_COUNT
            )
        )

        fps = cap.get(
            cv2.CAP_PROP_FPS
        )

        if fps <= 0:

            fps = 25

        video_duration = (
            total_frames / fps
        )

        emotion_counts = {}

        total_faces = 0

        processed_frames = 0

        frame_interval = max(
            int(fps),
            1
        )

        frame_number = 0

        # Reset eye tracking for recorded video
        with eye_tracks_lock:

            eye_tracks.clear()

        while True:

            success, frame = cap.read()

            if not success:

                break

            frame_number += 1

            if (
                frame_number
                %
                frame_interval
                != 0
            ):

                continue

            results = process_frame(
                frame
            )

            processed_frames += 1

            total_faces += len(
                results
            )

            for result in results:

                emotion = result[
                    "emotion"
                ]

                if (
                    emotion
                    not in
                    emotion_counts
                ):

                    emotion_counts[
                        emotion
                    ] = 0

                emotion_counts[
                    emotion
                ] += 1

        cap.release()

        cap = None

        # ====================================================
        # MOST COMMON EMOTION
        # ====================================================

        most_common_emotion = "Unknown"

        if emotion_counts:

            most_common_emotion = max(
                emotion_counts,
                key=emotion_counts.get
            )

        return jsonify({

            "success": True,

            "message":
                "Video analyzed successfully",

            "duration_seconds":
                round(
                    video_duration,
                    2
                ),

            "total_frames":
                total_frames,

            "processed_frames":
                processed_frames,

            "total_faces_detected":
                total_faces,

            "emotion_counts":
                emotion_counts,

            "most_common_emotion":
                most_common_emotion
        })

    except Exception as e:

        print(
            "VIDEO ANALYSIS ERROR:",
            e
        )

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

    finally:

        if cap is not None:

            cap.release()

        if (
            video_path
            and
            os.path.exists(
                video_path
            )
        ):

            try:

                os.remove(
                    video_path
                )

            except Exception as e:

                print(
                    "Could not delete "
                    "temporary video:",
                    e
                )


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

    app.run(
        debug=True,
        use_reloader=False,
        host="0.0.0.0",
        port=5000
    )

