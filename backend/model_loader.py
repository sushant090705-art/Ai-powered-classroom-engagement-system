import logging
import os
import cv2
import tensorflow as tf
from ultralytics import YOLO

logger = logging.getLogger(__name__)


# ==========================================
# Project Base Directory
# ==========================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)


# ==========================================
# YOLO Model
# ==========================================

logger.info("Loading YOLO model...")

YOLO_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "yolov8n.pt"
)

yolo_model = YOLO(YOLO_MODEL_PATH)

logger.info("YOLO model loaded successfully!")


# ==========================================
# Emotion Model
# ==========================================

logger.info("Loading emotion model...")

EMOTION_MODEL_PATH = os.path.join(
    BASE_DIR,
    "ai-model",
    "models",
    "emotion_model.keras"
)

emotion_model = tf.keras.models.load_model(
    EMOTION_MODEL_PATH
)

logger.info("Emotion model loaded successfully!")


# ==========================================
# Emotion Labels
# ==========================================

emotion_labels = [
    "Angry",
    "Disgust",
    "Fear",
    "Happy",
    "Neutral",
    "Sad",
    "Surprise"
]


# ==========================================
# Face Detector
# ==========================================

face_detector = cv2.CascadeClassifier(
    cv2.data.haarcascades +
    "haarcascade_frontalface_default.xml"
)


# ==========================================
# Eye Detector
# ==========================================

eye_detector = cv2.CascadeClassifier(
    cv2.data.haarcascades +
    "haarcascade_eye.xml"
)

logger.info("Model loader initialized successfully!")