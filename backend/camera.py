from flask import Blueprint, request, jsonify, Response

import os
import cv2
import threading
import time

from eye_tracking import (
    eye_tracks,
    eye_tracks_lock
)

from ai_processing import (
    start_ai_thread,
    stop_ai_thread,
    set_latest_frame,
    get_latest_results,
    clear_latest_results
)


# ============================================================
# CAMERA BLUEPRINT
# ============================================================

camera_bp = Blueprint(
    "camera",
    __name__
)


# ============================================================
# CAMERA VARIABLES
# ============================================================

CAMERA_SOURCE = None
CAMERA_TYPE = "none"
MOBILE_CAMERA_URL = ""

camera = None

camera_lock = threading.Lock()


# ============================================================
# GET CAMERA
# ============================================================

def get_camera():

    global camera
    global CAMERA_SOURCE
    global CAMERA_TYPE
    global MOBILE_CAMERA_URL

    source = (
        CAMERA_SOURCE
        if CAMERA_SOURCE is not None
        else (
            MOBILE_CAMERA_URL
            if MOBILE_CAMERA_URL
            else None
        )
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
                f"Connecting to camera "
                f"({CAMERA_TYPE}): {source}"
            )

            try:

                # ====================================================
                # WEBCAM
                # ====================================================

                if (
                    isinstance(source, int)
                    or
                    (
                        isinstance(source, str)
                        and
                        source.strip().isdigit()
                    )
                ):

                    cam_idx = int(source)

                    if os.name == "nt":

                        camera = cv2.VideoCapture(
                            cam_idx,
                            cv2.CAP_DSHOW
                        )

                    else:

                        camera = cv2.VideoCapture(
                            cam_idx
                        )

                # ====================================================
                # PHONE / IP CAMERA
                # ====================================================

                else:

                    camera = cv2.VideoCapture(
                        str(source)
                    )

            except Exception as e:

                print(
                    "Exception creating "
                    f"VideoCapture: {e}"
                )

                camera = None

                return None

            # ========================================================
            # REDUCE CAMERA BUFFER
            # ========================================================

            try:

                camera.set(
                    cv2.CAP_PROP_BUFFERSIZE,
                    1
                )

            except Exception:

                pass

            # ========================================================
            # CHECK CONNECTION
            # ========================================================

            if (
                camera is not None
                and
                camera.isOpened()
            ):

                print(
                    f"{CAMERA_TYPE.capitalize()} "
                    "camera connected successfully!"
                )

            else:

                print(
                    f"ERROR: Could not connect "
                    f"to {CAMERA_TYPE} camera."
                )

                camera = None

        return camera


# ============================================================
# CAMERA CONNECT API
# ============================================================

@camera_bp.route(
    "/camera/connect",
    methods=["POST"]
)
def connect_camera():

    global CAMERA_SOURCE
    global CAMERA_TYPE
    global MOBILE_CAMERA_URL
    global camera

    data = request.get_json() or {}

    cam_type = (
        data.get(
            "type",
            "phone"
        )
        .lower()
    )

    # ========================================================
    # WEBCAM
    # ========================================================

    if cam_type == "webcam":

        cam_index = data.get(
            "index",
            0
        )

        try:

            cam_index = int(
                cam_index
            )

        except (
            ValueError,
            TypeError
        ):

            cam_index = 0

        new_source = cam_index

        display_name = (
            f"Webcam "
            f"(Device {cam_index})"
        )

    # ========================================================
    # PHONE CAMERA
    # ========================================================

    else:

        cam_type = "phone"

        new_url = (
            data.get(
                "url",
                ""
            )
            .strip()
        )

        if not new_url:

            return jsonify({

                "success": False,

                "message":
                    "Camera URL cannot be "
                    "empty for phone mode"

            }), 400

        new_source = new_url

        display_name = (
            f"Phone Camera "
            f"({new_url})"
        )

    # ========================================================
    # RELEASE OLD CAMERA
    # ========================================================

    with camera_lock:

        if camera is not None:

            try:

                camera.release()

            except Exception:

                pass

            camera = None

        CAMERA_SOURCE = new_source
        CAMERA_TYPE = cam_type

        MOBILE_CAMERA_URL = str(
            new_source
        )

    # ========================================================
    # RESET AI DATA
    # ========================================================

    set_latest_frame(None)

    clear_latest_results()

    with eye_tracks_lock:

        eye_tracks.clear()

    print("--------------------------------")

    print(
        f"Camera source updated: "
        f"[{CAMERA_TYPE}] "
        f"{new_source}"
    )

    print("--------------------------------")

    # ========================================================
    # ACTUALLY OPEN CAMERA
    # ========================================================

    cap = get_camera()

    if (
        cap is None
        or
        not cap.isOpened()
    ):

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

        return jsonify({

            "success": False,

            "message":
                f"Could not connect to "
                f"{display_name}"

        }), 500

    # ========================================================
    # START AI
    # ========================================================

    start_ai_thread()

    return jsonify({

        "success": True,

        "message":
            f"{display_name} "
            "connected successfully",

        "type":
            CAMERA_TYPE,

        "source":
            str(CAMERA_SOURCE),

        "url":
            MOBILE_CAMERA_URL

    })


# ============================================================
# CAMERA STATUS
# ============================================================

@camera_bp.route(
    "/camera/status",
    methods=["GET"]
)
def camera_status():

    global CAMERA_SOURCE
    global CAMERA_TYPE
    global MOBILE_CAMERA_URL
    global camera

    has_source = (
        CAMERA_SOURCE is not None
    ) or (
        MOBILE_CAMERA_URL != ""
    )

    is_open = (
        camera is not None
        and
        camera.isOpened()
    )

    connected = (
        has_source
        and
        is_open
    )

    return jsonify({

        "connected":
            connected,

        "type":
            CAMERA_TYPE,

        "source":
            (
                str(CAMERA_SOURCE)
                if CAMERA_SOURCE is not None
                else ""
            ),

        "url":
            MOBILE_CAMERA_URL

    })


# ============================================================
# CAMERA DISCONNECT
# ============================================================

@camera_bp.route(
    "/camera/disconnect",
    methods=["POST"]
)
def disconnect_camera():

    global CAMERA_SOURCE
    global CAMERA_TYPE
    global MOBILE_CAMERA_URL
    global camera

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

    set_latest_frame(None)

    clear_latest_results()

    with eye_tracks_lock:

        eye_tracks.clear()

    print(
        "Camera disconnected"
    )

    return jsonify({

        "success": True,

        "message":
            "Camera disconnected"

    })


# ============================================================
# CAMERA FRAME GENERATOR
# ============================================================

def generate_frames():

    global camera

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
                "Could not read frame "
                f"from camera ({CAMERA_TYPE})."
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

        # ====================================================
        # MIRROR WEBCAM
        # ====================================================

        if CAMERA_TYPE == "webcam":

            frame = cv2.flip(
                frame,
                1
            )

        # ====================================================
        # SAVE LATEST FRAME
        # ====================================================

        set_latest_frame(
            frame
        )

        # ====================================================
        # GET AI RESULTS
        # ====================================================

        results_copy = (
            get_latest_results()
        )

        if results_copy is None:

            results_copy = []

        # ====================================================
        # DRAW AI RESULTS
        # ====================================================

        for result in results_copy:

            face_x = result[
                "x"
            ]

            face_y = result[
                "y"
            ]

            fw = result[
                "width"
            ]

            fh = result[
                "height"
            ]

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

        # ====================================================
        # ENCODE JPEG
        # ====================================================

        success, buffer = cv2.imencode(
            ".jpg",
            frame
        )

        if not success:

            continue

        frame_bytes = (
            buffer.tobytes()
        )

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

@camera_bp.route(
    "/video_feed"
)
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

@camera_bp.route(
    "/emotion-results"
)
def emotion_results():

    results_copy = (
        get_latest_results()
    )

    if results_copy is None:

        results_copy = []

    return jsonify({

        "success":
            True,

        "faces_detected":
            len(results_copy),

        "faces":
            results_copy

    })


print(
    "Camera module loaded successfully!"
)