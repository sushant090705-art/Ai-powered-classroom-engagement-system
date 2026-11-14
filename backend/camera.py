"""Camera routes: one independent camera per class (point 12).

Every route takes an optional class_id (query string or JSON body). A
request without one uses the default class, so the original single-camera
frontend keeps working. Each class has its own camera connection, AI thread,
students, analytics and alerts (see engine.py).

    POST /camera/connect      {"class_id": "grade-5a", "type": "webcam", "index": 0}
    GET  /camera/status?class_id=grade-5a
    POST /camera/disconnect   {"class_id": "grade-5a"}
    GET  /video_feed?class_id=grade-5a
    GET  /emotion-results?class_id=grade-5a
    GET  /classes             every class and its camera state
"""

import logging
import os
import threading
import time

import cv2
from flask import Blueprint, Response, jsonify, request

from alerts import draw_teacher_zone
from analytics import annotate_engagement
from class_id import DEFAULT_CLASS_ID, normalize_class_id
from engine import get_class_engine, list_class_engines
from reports import save_session_report

logger = logging.getLogger(__name__)

camera_bp = Blueprint("camera", __name__)

# Every connected camera needs CPU for the AI models. Refuse more than this
# many at the same time (set MAX_LIVE_CAMERAS to change it).
MAX_LIVE_CAMERAS = int(os.environ.get("MAX_LIVE_CAMERAS", "4"))


# ============================================================
# ONE CAMERA
# ============================================================

class CameraSource:
    """The camera of one class: what to open, and the open capture."""

    def __init__(self, class_id):

        self.class_id = class_id
        self.lock = threading.Lock()
        self.source = None          # int (webcam index) or URL string
        self.type = "none"          # "webcam" | "phone" | "none"
        self.capture = None

    @property
    def has_source(self):
        return self.source is not None and self.source != ""

    @property
    def is_open(self):
        return self.capture is not None and self.capture.isOpened()

    def configure(self, source, cam_type):
        """Release the old camera and remember the new source."""

        with self.lock:
            self._release()
            self.source = source
            self.type = cam_type

    def clear(self):
        """Forget the source (disconnect)."""

        with self.lock:
            self._release()
            self.source = None
            self.type = "none"

    def release_capture(self):
        """Drop a broken capture; get_capture() will reconnect."""

        with self.lock:
            self._release()

    def _release(self):

        if self.capture is not None:
            try:
                self.capture.release()
            except Exception:
                pass

        self.capture = None

    def get_capture(self):
        """The open capture, connecting first when needed (None = failed)."""

        if not self.has_source:
            return None

        with self.lock:

            if self.capture is not None and self.capture.isOpened():
                return self.capture

            logger.info(
                "Connecting to camera [%s] (%s): %s",
                self.class_id, self.type, self.source,
            )

            try:
                is_webcam = isinstance(self.source, int) or (
                    isinstance(self.source, str)
                    and self.source.strip().isdigit()
                )

                if is_webcam:
                    index = int(self.source)
                    self.capture = (
                        cv2.VideoCapture(index, cv2.CAP_DSHOW)
                        if os.name == "nt" else cv2.VideoCapture(index)
                    )
                else:
                    self.capture = cv2.VideoCapture(str(self.source))

            except Exception:
                logger.exception(
                    "Exception creating VideoCapture [%s]", self.class_id
                )
                self.capture = None
                return None

            try:
                self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass

            if self.capture.isOpened():
                logger.info(
                    "%s camera connected successfully [%s]!",
                    self.type.capitalize(), self.class_id,
                )
            else:
                logger.error(
                    "Could not connect to %s camera [%s].",
                    self.type, self.class_id,
                )
                self.capture = None

            return self.capture


_sources = {}
_sources_lock = threading.Lock()


def get_camera_source(class_id=DEFAULT_CLASS_ID):

    with _sources_lock:

        source = _sources.get(class_id)

        if source is None:
            source = _sources[class_id] = CameraSource(class_id)

        return source


def _connected_camera_count():

    with _sources_lock:
        return sum(1 for s in _sources.values() if s.has_source)


# ============================================================
# REQUEST HELPERS
# ============================================================

def _class_id(data=None):
    """class_id from the JSON body or the query string."""

    value = (data or {}).get("class_id") or request.args.get("class_id")

    return normalize_class_id(value)


@camera_bp.errorhandler(ValueError)
def _bad_class_id(error):
    return jsonify({"success": False, "message": str(error)}), 400


def _status_payload(class_id):

    camera = get_camera_source(class_id)

    return {
        "class_id": class_id,
        "connected": camera.has_source and camera.is_open,
        "type": camera.type,
        "source": str(camera.source) if camera.source is not None else "",
        "url": str(camera.source) if camera.source is not None else "",
    }


# ============================================================
# CONNECT / STATUS / DISCONNECT
# ============================================================

@camera_bp.route("/camera/connect", methods=["POST"])
def connect_camera():

    data = request.get_json(silent=True) or {}
    class_id = _class_id(data)

    cam_type = str(data.get("type", "phone")).lower()

    if cam_type == "webcam":

        try:
            cam_index = int(data.get("index", 0))
        except (ValueError, TypeError):
            cam_index = 0

        new_source = cam_index
        display_name = f"Webcam (Device {cam_index})"

    else:

        cam_type = "phone"
        new_url = str(data.get("url", "")).strip()

        if not new_url:
            return jsonify({
                "success": False,
                "message": "Camera URL cannot be empty for phone mode",
            }), 400

        new_source = new_url
        display_name = f"Phone Camera ({new_url})"

    camera = get_camera_source(class_id)

    if (
        not camera.has_source
        and _connected_camera_count() >= MAX_LIVE_CAMERAS
    ):
        return jsonify({
            "success": False,
            "message": (
                f"At most {MAX_LIVE_CAMERAS} cameras can run at the same "
                "time. Disconnect another class first."
            ),
        }), 409

    engine = get_class_engine(class_id)

    camera.configure(new_source, cam_type)

    engine.set_latest_frame(None)
    engine.clear_latest_results()
    engine.tracker.reset()
    engine.reset_person_tracker()

    logger.info(
        "Camera source updated [%s]: [%s] %s", class_id, cam_type, new_source
    )

    capture = camera.get_capture()

    if capture is None or not capture.isOpened():

        camera.clear()

        return jsonify({
            "success": False,
            "message": f"Could not connect to {display_name}",
        }), 500

    engine.start()

    return jsonify({
        "success": True,
        "message": f"{display_name} connected successfully",
        "class_id": class_id,
        "type": camera.type,
        "source": str(camera.source),
        "url": str(camera.source),
    })


@camera_bp.route("/camera/status", methods=["GET"])
def camera_status():

    return jsonify(_status_payload(_class_id()))


@camera_bp.route("/camera/disconnect", methods=["POST"])
def disconnect_camera():

    data = request.get_json(silent=True) or {}
    class_id = _class_id(data)

    engine = get_class_engine(class_id)
    camera = get_camera_source(class_id)

    engine.stop()

    # Build and store the final report for the session that just ended.
    try:
        saved_report = save_session_report(class_id)
    except Exception:
        logger.exception("Could not save session report [%s]", class_id)
        saved_report = None

    camera.clear()

    engine.set_latest_frame(None)
    engine.clear_latest_results()
    engine.tracker.reset()
    engine.reset_person_tracker()

    logger.info("Camera disconnected [%s]", class_id)

    return jsonify({
        "success": True,
        "message": "Camera disconnected",
        "class_id": class_id,
        "report": saved_report,
    })


@camera_bp.route("/classes", methods=["GET"])
def list_classes():
    """Every class that has a camera or a running engine."""

    with _sources_lock:
        class_ids = set(_sources)

    class_ids |= set(list_class_engines())
    class_ids.add(DEFAULT_CLASS_ID)

    classes = []

    for class_id in sorted(class_ids):

        payload = _status_payload(class_id)
        engine = list_class_engines().get(class_id)

        payload["session_active"] = bool(engine and engine.session_active)
        classes.append(payload)

    return jsonify({
        "success": True,
        "max_cameras": MAX_LIVE_CAMERAS,
        "classes": classes,
    })


# ============================================================
# VIDEO STREAM
# ============================================================

def generate_frames(class_id=DEFAULT_CLASS_ID):

    camera = get_camera_source(class_id)
    engine = get_class_engine(class_id)

    while True:

        capture = camera.get_capture()

        if capture is None or not capture.isOpened():
            time.sleep(1)
            continue

        success, frame = capture.read()

        if not success:

            logger.warning(
                "Could not read frame from camera [%s] (%s).",
                class_id, camera.type,
            )

            camera.release_capture()
            time.sleep(1)
            continue

        # mirror webcam
        if camera.type == "webcam":
            frame = cv2.flip(frame, 1)

        engine.set_latest_frame(frame)

        # draw the latest AI results
        for result in engine.get_latest_results():

            face_x, face_y = result["x"], result["y"]
            fw, fh = result["width"], result["height"]

            cv2.rectangle(
                frame, (face_x, face_y), (face_x + fw, face_y + fh),
                (0, 255, 0), 2,
            )

            cv2.putText(
                frame,
                f'{result["emotion"]}: {result["confidence"]:.1f}%',
                (face_x, max(face_y - 35, 20)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2,
            )

            cv2.putText(
                frame,
                f'Eyes: {result["eye_state"]}',
                (face_x, max(face_y - 10, 20)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2,
            )

        # teacher zone (only while the teacher check is on)
        try:
            draw_teacher_zone(frame, class_id)
        except Exception:
            pass

        success, buffer = cv2.imencode(".jpg", frame)

        if not success:
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + buffer.tobytes()
            + b"\r\n"
        )


@camera_bp.route("/video_feed")
def video_feed():

    return Response(
        generate_frames(_class_id()),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@camera_bp.route("/emotion-results")
def emotion_results():

    faces = annotate_engagement(
        get_class_engine(_class_id()).get_latest_results()
    )

    return jsonify({
        "success": True,
        "faces_detected": len(faces),
        "faces": faces,
    })