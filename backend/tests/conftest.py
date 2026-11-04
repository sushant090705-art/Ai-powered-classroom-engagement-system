"""Test setup: no TensorFlow, YOLO, camera or real folders needed.

* All data (SQLite database, alert settings) goes to a temp folder.
* `fake_models` replaces the AI models with tiny fakes, so process_frame()
  and the whole engine can run on a synthetic frame.
"""

import os
import sys
import tempfile
import types

import numpy as np
import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

# Must happen before any project module is imported.
_TMP = tempfile.mkdtemp(prefix="classroom-tests-")
os.environ["CLASSROOM_DB_PATH"] = os.path.join(_TMP, "classroom.db")
os.environ["ALERTS_DATA_DIR"] = os.path.join(_TMP, "saved_alerts")
os.environ["LOG_TO_FILE"] = "0"


# ------------------------------------------------------------
# helpers
# ------------------------------------------------------------

def make_result(eye="Open", emotion="Happy", x=10, y=10, w=60, h=60):
    """One face result as produced by process_frame()."""

    return {
        "emotion": emotion,
        "confidence": 90.0,
        "eye_state": eye,
        "eye_confidence": 90.0,
        "x": x, "y": y, "width": w, "height": h,
        "person_x": x, "person_y": y,
        "person_width": w, "person_height": h,
    }


def make_class(n, eye="Open", emotion="Happy"):
    """n faces that do not overlap."""

    return [make_result(eye, emotion, x=10 + i * 100) for i in range(n)]


class FakeClock:
    """Controllable clock for EyeTracker tests."""

    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def clock():
    return FakeClock()


# ------------------------------------------------------------
# fake AI models
# ------------------------------------------------------------

class _FakeBox:
    def __init__(self, xyxy):
        self.xyxy = [types.SimpleNamespace(tolist=lambda: list(xyxy))]


class _FakeYolo:
    """Always finds one big person."""

    def __init__(self):
        self.person = (5, 5, 315, 235)

    def __call__(self, frame, **kwargs):
        return [types.SimpleNamespace(boxes=[_FakeBox(self.person)])]


class _FakeEmotionModel:
    def predict(self, x, verbose=0):
        out = np.zeros((1, 7), dtype="float32")
        out[0, 3] = 0.9                      # index 3 = "Happy"
        return out


class _FakeFaceDetector:
    """Two non-overlapping faces inside the person crop."""

    def detectMultiScale(self, gray, **kwargs):
        return np.array([[10, 10, 60, 60], [150, 10, 60, 60]])


class _FakeEyeDetector:
    def detectMultiScale(self, gray, **kwargs):
        return np.empty((0, 4), dtype=int)   # forces the fallback eye crops


@pytest.fixture
def fake_models(monkeypatch):
    """Install fake `model_loader` and `eye_tracking` modules and import a
    fresh ai_processing / engine that uses them.

    The fake eye predictor says "Close" when the eye crop is bright
    (mean > 128) and "Open" otherwise, so a test video can encode the eye
    state in the picture brightness.
    """

    model_loader = types.ModuleType("model_loader")
    model_loader.yolo_model = _FakeYolo()
    model_loader.emotion_model = _FakeEmotionModel()
    model_loader.emotion_labels = [
        "Angry", "Disgust", "Fear", "Happy", "Sad", "Surprise", "Neutral",
    ]
    model_loader.face_detector = _FakeFaceDetector()
    model_loader.eye_detector = _FakeEyeDetector()

    eye_tracking = types.ModuleType("eye_tracking")

    def predict_eye_state(eye_image):
        return ("Close", 90.0) if float(np.mean(eye_image)) > 128 else ("Open", 90.0)

    eye_tracking.predict_eye_state = predict_eye_state

    monkeypatch.setitem(sys.modules, "model_loader", model_loader)
    monkeypatch.setitem(sys.modules, "eye_tracking", eye_tracking)
    sys.modules.pop("ai_processing", None)

    import ai_processing

    yield model_loader

    sys.modules.pop("ai_processing", None)
