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

from student_reports import (
    students_bp,
    update_student_registry,
    reset_student_registry
)


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)
CORS(app)

# Per-student report endpoints (/students/report, ...)
app.register_blueprint(students_bp)


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

CAMERA_SOURCE = None
CAMERA_TYPE = "none"
MOBILE_CAMERA_URL = ""

camera = None

camera_lock = threading.Lock()

latest_frame = None
frame_lock = threading.Lock()

latest_results = []
results_lock = threading.Lock()

# YOLO person boxes (x1, y1, x2, y2) of the last processed frame.
# Written and read only by the AI thread; used for student reports.
last_person_boxes = []

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

    global last_person_boxes

    last_person_boxes = []

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

            # Remember this person for the student reports
            last_person_boxes.append((x1, y1, x2, y2))

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

        try:

            update_student_registry(
                list(last_person_boxes),
                results
            )

        except Exception as report_error:

            print(
                "Student report update error:",
                report_error
            )

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
    global CAMERA_SOURCE
    global CAMERA_TYPE
    global MOBILE_CAMERA_URL

    source = (
        CAMERA_SOURCE
        if CAMERA_SOURCE is not None
        else (MOBILE_CAMERA_URL if MOBILE_CAMERA_URL else None)
    )

    if source is None or source == "":

        return None

    with camera_lock:

        if (
            camera is None
            or
            not camera.isOpened()
        ):

            print(
                f"Connecting to camera ({CAMERA_TYPE}): {source}"
            )

            try:

                # If source is an integer index (webcam) or digit string "0", "1"
                if isinstance(source, int) or (isinstance(source, str) and source.strip().isdigit()):

                    cam_idx = int(source)

                    # On Windows, cv2.CAP_DSHOW initializes webcams much faster than MSMF
                    if os.name == "nt":

                        camera = cv2.VideoCapture(
                            cam_idx,
                            cv2.CAP_DSHOW
                        )

                    else:

                        camera = cv2.VideoCapture(
                            cam_idx
                        )

                else:

                    camera = cv2.VideoCapture(
                        str(source)
                    )

            except Exception as e:

                print(
                    f"Exception creating VideoCapture: {e}"
                )

                camera = None

                return None

            try:

                camera.set(
                    cv2.CAP_PROP_BUFFERSIZE,
                    1
                )

            except Exception:

                pass

            if camera is not None and camera.isOpened():

                print(
                    f"{CAMERA_TYPE.capitalize()} camera connected successfully!"
                )

            else:

                print(
                    f"ERROR: Could not connect to {CAMERA_TYPE} camera."
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

    global CAMERA_SOURCE
    global CAMERA_TYPE
    global MOBILE_CAMERA_URL
    global camera
    global latest_frame
    global eye_tracks
    global latest_results

    data = request.get_json() or {}
    cam_type = data.get("type", "phone").lower()

    if cam_type == "webcam":

        cam_index = data.get("index", 0)

        try:

            cam_index = int(cam_index)

        except (ValueError, TypeError):

            cam_index = 0

        new_source = cam_index
        display_name = f"Webcam (Device {cam_index})"

    else:

        cam_type = "phone"
        new_url = data.get("url", "").strip()

        if not new_url:

            return jsonify({
                "success": False,
                "message": "Camera URL cannot be empty for phone mode"
            }), 400

        new_source = new_url
        display_name = f"Phone Camera ({new_url})"

    with camera_lock:

        if camera is not None:

            try:

                camera.release()

            except Exception:

                pass

            camera = None

        CAMERA_SOURCE = new_source
        CAMERA_TYPE = cam_type
        MOBILE_CAMERA_URL = str(new_source)

    with frame_lock:

        latest_frame = None

    with results_lock:

        latest_results.clear()

    # Reset eye tracking
    with eye_tracks_lock:

        eye_tracks.clear()

    # Start a fresh student-report session
    reset_student_registry()

    print("--------------------------------")

    print(
        f"Camera source updated: [{CAMERA_TYPE}] {new_source}"
    )

    print("--------------------------------")

    start_ai_thread()

    return jsonify({
        "success": True,
        "message": f"{display_name} connected successfully",
        "type": CAMERA_TYPE,
        "source": str(CAMERA_SOURCE),
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

    global CAMERA_SOURCE
    global CAMERA_TYPE
    global MOBILE_CAMERA_URL
    global camera

    has_source = (CAMERA_SOURCE is not None) or (MOBILE_CAMERA_URL != "")
    is_open = camera is not None and camera.isOpened()
    connected = has_source and is_open

    return jsonify({
        "connected": connected,
        "type": CAMERA_TYPE,
        "source": str(CAMERA_SOURCE) if CAMERA_SOURCE is not None else "",
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

    global CAMERA_SOURCE
    global CAMERA_TYPE
    global MOBILE_CAMERA_URL
    global camera
    global latest_frame
    global latest_results
    global eye_tracks

    stop_ai_thread()

    with camera_lock:

        if camera is not None:

            try:

                camera.release()

            except Exception:

                pass

            camera = None

        CAMERA_SOURCE = None
        CAMERA_TYPE = "none"
        MOBILE_CAMERA_URL = ""

    with frame_lock:

        latest_frame = None

    with results_lock:

        latest_results.clear()

    # Reset eye tracking
    with eye_tracks_lock:

        eye_tracks.clear()

    # Start a fresh student-report session
    reset_student_registry()

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
                f"Could not read frame from camera ({CAMERA_TYPE})."
            )

            with camera_lock:

                if camera is not None:

                    try:

                        camera.release()

                    except Exception:

                        pass

                camera = None

            time.sleep(1)

            continue

        # Mirror frame horizontally for laptop/PC webcam for natural user experience
        if CAMERA_TYPE == "webcam":

            frame = cv2.flip(frame, 1)

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

def recorded_iou(box_a, box_b):
    """IoU for (x, y, w, h) boxes."""

    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b

    ax2 = ax + aw
    ay2 = ay + ah
    bx2 = bx + bw
    by2 = by + bh

    inter_x1 = max(ax, bx)
    inter_y1 = max(ay, by)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)

    intersection = inter_w * inter_h

    area_a = max(0, aw) * max(0, ah)
    area_b = max(0, bw) * max(0, bh)

    union = area_a + area_b - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def recorded_center(box):
    x, y, w, h = box

    return (
        x + w / 2.0,
        y + h / 2.0
    )


def recorded_center_distance(box_a, box_b):

    ax, ay = recorded_center(box_a)
    bx, by = recorded_center(box_b)

    dx = ax - bx
    dy = ay - by

    distance = float(
        np.sqrt(dx * dx + dy * dy)
    )

    _, _, aw, ah = box_a
    _, _, bw, bh = box_b

    scale = max(
        1.0,
        (aw + ah + bw + bh) / 4.0
    )

    return distance / scale


# ============================================================
# YOLO PERSON DETECTION
# ============================================================

def recorded_detect_people(frame):

    results = yolo_model(
        frame,
        classes=[0],          # COCO class 0 = person
        conf=0.35,
        verbose=False
    )

    person_boxes = []

    for result in results:

        if result.boxes is None:
            continue

        for box in result.boxes:

            xyxy = box.xyxy[0].cpu().numpy()

            x1, y1, x2, y2 = map(
                int,
                xyxy
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

            w = x2 - x1
            h = y2 - y1

            if w <= 0 or h <= 0:
                continue

            person_boxes.append(
                (x1, y1, w, h)
            )

    return person_boxes


# ============================================================
# FACE DETECTION INSIDE YOLO PERSON
# ============================================================

def recorded_detect_face_inside_person(
    frame,
    person_box
):

    px, py, pw, ph = person_box

    person_crop = frame[
        py:py + ph,
        px:px + pw
    ]

    if person_crop.size == 0:
        return None

    gray = cv2.cvtColor(
        person_crop,
        cv2.COLOR_BGR2GRAY
    )

    faces = face_detector.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(40, 40)
    )

    if len(faces) == 0:
        return None

    # Choose the largest face.
    face = max(
        faces,
        key=lambda b: b[2] * b[3]
    )

    fx, fy, fw, fh = face

    return (
        px + fx,
        py + fy,
        fw,
        fh
    )


# ============================================================
# FER2013 EMOTION
# ============================================================

def recorded_predict_emotion(
    frame,
    face_box
):

    x, y, w, h = face_box

    frame_h, frame_w = frame.shape[:2]

    x = max(0, int(x))
    y = max(0, int(y))
    w = max(1, int(w))
    h = max(1, int(h))

    x2 = min(
        frame_w,
        x + w
    )

    y2 = min(
        frame_h,
        y + h
    )

    face = frame[
        y:y2,
        x:x2
    ]

    if face.size == 0:
        return "Unknown", 0.0

    gray_face = cv2.cvtColor(
        face,
        cv2.COLOR_BGR2GRAY
    )

    gray_face = cv2.resize(
        gray_face,
        (48, 48),
        interpolation=cv2.INTER_AREA
    )

    model_input = (
        gray_face.astype("float32") / 255.0
    )

    model_input = np.expand_dims(
        model_input,
        axis=0
    )

    model_input = np.expand_dims(
        model_input,
        axis=-1
    )

    predictions = emotion_model.predict(
        model_input,
        verbose=0
    )

    probabilities = np.asarray(
        predictions[0],
        dtype=np.float32
    )

    emotion_index = int(
        np.argmax(probabilities)
    )

    if emotion_index >= len(
        emotion_labels
    ):
        return "Unknown", 0.0

    emotion = emotion_labels[
        emotion_index
    ]

    confidence = float(
        probabilities[
            emotion_index
        ] * 100.0
    )

    return emotion, confidence


# ============================================================
# MRL EYE STATE
# ============================================================

def recorded_predict_eye_state(
    frame,
    face_box
):

    x, y, w, h = face_box

    frame_h, frame_w = frame.shape[:2]

    x = max(0, int(x))
    y = max(0, int(y))
    w = max(1, int(w))
    h = max(1, int(h))

    x2 = min(
        frame_w,
        x + w
    )

    y2 = min(
        frame_h,
        y + h
    )

    face = frame[
        y:y2,
        x:x2
    ]

    if face.size == 0:
        return "Unknown", 0.0

    # Eyes are normally located in upper half of face.
    upper_face = face[
        0:max(1, int(face.shape[0] * 0.60)),
        :
    ]

    gray = cv2.cvtColor(
        upper_face,
        cv2.COLOR_BGR2GRAY
    )

    eyes = eye_detector.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(15, 15)
    )

    if len(eyes) == 0:
        return "Unknown", 0.0

    # Select largest detected eye region.
    eye_box = max(
        eyes,
        key=lambda b: b[2] * b[3]
    )

    ex, ey, ew, eh = eye_box

    eye_crop = upper_face[
        ey:ey + eh,
        ex:ex + ew
    ]

    if eye_crop.size == 0:
        return "Unknown", 0.0

    # Reuse the existing MRL prediction function.
    return predict_eye_state(
        eye_crop
    )


# ============================================================
# PERSON TRACK MATCHING
# ============================================================

def recorded_match_person(
    person_box,
    tracks,
    used_track_ids
):

    best_track_id = None
    best_score = -1.0

    current_area = max(
        1,
        person_box[2] * person_box[3]
    )

    for track_id, track in tracks.items():

        if track_id in used_track_ids:
            continue

        previous_box = track["box"]

        iou = recorded_iou(
            person_box,
            previous_box
        )

        distance = recorded_center_distance(
            person_box,
            previous_box
        )

        previous_area = max(
            1,
            previous_box[2] * previous_box[3]
        )

        area_ratio = (
            min(
                current_area,
                previous_area
            )
            /
            max(
                current_area,
                previous_area
            )
        )

        if iou >= 0.20:

            score = (
                0.70 * iou
                +
                0.20 * max(
                    0.0,
                    1.0 - distance / 2.5
                )
                +
                0.10 * area_ratio
            )

        elif (
            distance <= 1.80
            and area_ratio >= 0.45
        ):

            score = (
                0.70 * max(
                    0.0,
                    1.0 - distance / 1.80
                )
                +
                0.30 * area_ratio
            )

        else:
            continue

        if score > best_score:

            best_score = score
            best_track_id = track_id

    return best_track_id


# ============================================================
# BUILD FINAL SUMMARY
# ============================================================

def recorded_build_person_summary(
    tracks
):

    summary = []

    for track_id in sorted(
        tracks.keys()
    ):

        track = tracks[track_id]

        emotion_counts = track[
            "emotion_counts"
        ]

        eye_counts = track[
            "eye_counts"
        ]

        # -------------------------
        # Emotion
        # -------------------------

        if emotion_counts:

            dominant_emotion = max(
                emotion_counts.items(),
                key=lambda item: (
                    item[1],
                    track[
                        "emotion_confidence_sum"
                    ].get(
                        item[0],
                        0.0
                    )
                )
            )[0]

        else:

            dominant_emotion = "Unknown"

        # -------------------------
        # Eyes
        # -------------------------

        if eye_counts:

            dominant_eye_state = max(
                eye_counts.items(),
                key=lambda item: (
                    item[1],
                    track[
                        "eye_confidence_sum"
                    ].get(
                        item[0],
                        0.0
                    )
                )
            )[0]

        else:

            dominant_eye_state = "Unknown"

        summary.append({

            "person_id": int(
                track_id
            ),

            "most_common_emotion":
                dominant_emotion,

            "most_common_eye_state":
                dominant_eye_state,

            "emotion_samples": int(
                sum(
                    emotion_counts.values()
                )
            ),

            "eye_samples": int(
                sum(
                    eye_counts.values()
                )
            ),

            "samples_analyzed": int(
                track[
                    "samples_analyzed"
                ]
            )
        })

    return summary


# ============================================================
# ANALYZE RECORDED VIDEO
# ============================================================

@app.route(
    "/analyze-video",
    methods=["POST"]
)
def analyze_video():

    video_path = None
    cap = None

    try:

        # ====================================================
        # 1. RECEIVE VIDEO
        # ====================================================

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
        # 2. SAVE VIDEO
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

        extension = os.path.splitext(
            video_file.filename
        )[1].lower()

        if not extension:
            extension = ".mp4"

        filename = (
            f"uploaded_"
            f"{int(time.time() * 1000)}"
            f"{extension}"
        )

        video_path = os.path.join(
            upload_folder,
            filename
        )

        video_file.save(video_path)

        # ====================================================
        # 3. OPEN VIDEO
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

        fps = float(
            cap.get(
                cv2.CAP_PROP_FPS
            )
        )

        if not np.isfinite(fps) or fps <= 0:

            fps = 25.0

        # ====================================================
        # 4. PERSON TRACKING STATE
        # ====================================================

        tracks = {}

        next_person_id = 1

        sample_fps = min(
            5.0,
            fps
        )

        frame_step = max(
            1,
            int(
                round(
                    fps / sample_fps
                )
            )
        )

        frame_number = 0
        sampled_frames = 0

        max_missed_frames = 4

        # ====================================================
        # 5. PROCESS VIDEO
        # ====================================================

        while True:

            success, frame = cap.read()

            if not success:
                break

            frame_number += 1

            if (
                (frame_number - 1)
                % frame_step
                != 0
            ):
                continue

            sampled_frames += 1

            # =================================================
            # YOLO PERSON DETECTION
            # =================================================

            person_boxes = recorded_detect_people(
                frame
            )

            used_track_ids = set()
            matched_track_ids = set()

            # =================================================
            # MATCH EACH PERSON
            # =================================================

            for person_box in person_boxes:

                track_id = recorded_match_person(
                    person_box,
                    tracks,
                    used_track_ids
                )

                if track_id is None:

                    track_id = next_person_id

                    next_person_id += 1

                    tracks[track_id] = {

                        "box": person_box,

                        "samples_analyzed": 0,

                        "missed_frames": 0,

                        "emotion_counts": {},

                        "emotion_confidence_sum": {},

                        "eye_counts": {},

                        "eye_confidence_sum": {}
                    }

                track = tracks[
                    track_id
                ]

                used_track_ids.add(
                    track_id
                )

                matched_track_ids.add(
                    track_id
                )

                track["box"] = (
                    person_box
                )

                track["missed_frames"] = 0

                # =================================================
                # FACE DETECTION INSIDE PERSON
                # =================================================

                face_box = recorded_detect_face_inside_person(
                    frame,
                    person_box
                )

                if face_box is None:

                    continue

                # =================================================
                # FER2013 EMOTION
                # =================================================

                emotion, emotion_confidence = (
                    recorded_predict_emotion(
                        frame,
                        face_box
                    )
                )

                # =================================================
                # MRL EYE STATE
                # =================================================

                eye_state, eye_confidence = (
                    recorded_predict_eye_state(
                        frame,
                        face_box
                    )
                )

                # =================================================
                # STORE EMOTION
                # =================================================

                if emotion != "Unknown":

                    track[
                        "emotion_counts"
                    ][emotion] = (
                        track[
                            "emotion_counts"
                        ].get(
                            emotion,
                            0
                        ) + 1
                    )

                    track[
                        "emotion_confidence_sum"
                    ][emotion] = (
                        track[
                            "emotion_confidence_sum"
                        ].get(
                            emotion,
                            0.0
                        )
                        +
                        emotion_confidence
                    )

                # =================================================
                # STORE EYE STATE
                # =================================================

                if eye_state != "Unknown":

                    track[
                        "eye_counts"
                    ][eye_state] = (
                        track[
                            "eye_counts"
                        ].get(
                            eye_state,
                            0
                        ) + 1
                    )

                    track[
                        "eye_confidence_sum"
                    ][eye_state] = (
                        track[
                            "eye_confidence_sum"
                        ].get(
                            eye_state,
                            0.0
                        )
                        +
                        eye_confidence
                    )

                track[
                    "samples_analyzed"
                ] += 1

                print(
                    f"[VIDEO] Person "
                    f"{track_id} | "
                    f"Emotion: {emotion} "
                    f"({emotion_confidence:.1f}%) | "
                    f"Eyes: {eye_state} "
                    f"({eye_confidence:.1f}%)"
                )

            # =================================================
            # UPDATE MISSED TRACKS
            # =================================================

            for track_id in list(
                tracks.keys()
            ):

                if (
                    track_id
                    not in matched_track_ids
                ):

                    tracks[
                        track_id
                    ][
                        "missed_frames"
                    ] += 1

        # ====================================================
        # 6. FINAL PERSON SUMMARY
        # ====================================================

        person_summary = (
            recorded_build_person_summary(
                tracks
            )
        )

        total_faces_detected = len(
            [
                track
                for track in tracks.values()
                if track[
                    "samples_analyzed"
                ] > 0
            ]
        )

        return jsonify({

            "success": True,

            "message":
                "Video analyzed successfully",

            "total_faces_detected":
                total_faces_detected,

            "person_summary":
                person_summary,

            "processed_frames":
                sampled_frames,

            "total_frames":
                total_frames,

            "fps":
                fps
        })

    except Exception as e:

        print(
            "Recorded video error:",
            str(e)
        )

        return jsonify({

            "success": False,

            "message":
                "Video analysis failed",

            "error":
                str(e)
        }), 500

    finally:

        if cap is not None:

            cap.release()

        if (
            video_path
            and
            os.path.exists(video_path)
        ):

            try:

                os.remove(
                    video_path
                )

            except Exception as cleanup_error:

                print(
                    "Video cleanup error:",
                    cleanup_error
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

