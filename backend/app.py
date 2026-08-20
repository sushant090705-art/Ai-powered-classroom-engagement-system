from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient

import os
import cv2
import numpy as np
import tensorflow as tf

app = Flask(__name__)
CORS(app)

# MongoDB Atlas connection
client = MongoClient("mongodb+srv://suryamsaini3_db_user:DziKLc2JFeoaX4dK@cluster0.yfd6kld.mongodb.net/?appName=Cluster0")

db = client["classroom_engagement"]
users = db["users"]

print("MongoDB connected successfully!")
# =========================
# LOAD FER EMOTION MODEL
# =========================

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

# Emotion labels
emotion_labels = [
    "Angry",
    "Disgust",
    "Fear",
    "Happy",
    "Sad",
    "Surprise",
    "Neutral"
]

# Face detector
face_detector = cv2.CascadeClassifier(
    cv2.data.haarcascades +
    "haarcascade_frontalface_default.xml"
)

@app.route("/")
def home():
    return "Classroom Engagement AI Backend Running!"

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

    existing_user = users.find_one({"email": email})

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
@app.route("/predict-emotion", methods=["POST"])
def predict_emotion():

    try:
        # Check if image was received
        if "image" not in request.files:
            return jsonify({
                "success": False,
                "message": "No image received"
            }), 400

        image_file = request.files["image"]

        # Read image
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

            # Resize to model input
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

            # Predict emotion
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

            results.append({
                "emotion": emotion,
                "confidence": round(
                    confidence,
                    2
                ),
                "x": int(x),
                "y": int(y),
                "width": int(w),
                "height": int(h)
            })

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


if __name__ == "__main__":
    app.run(debug=True)
    