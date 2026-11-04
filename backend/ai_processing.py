"""AI detection pipeline for a single frame.

process_frame() is the only place where the YOLO / emotion / eye models are
run. It is used by the shared engine (engine.py), which feeds live-camera
frames AND recorded-video frames through the same code.

The functions below process_frame() are thin wrappers kept for older
callers; they forward to the ClassEngine of the requested class.
"""

import logging

import cv2
import numpy as np

from model_loader import (
    yolo_model,
    emotion_model,
    emotion_labels,
    face_detector,
    eye_detector,
)
from eye_state import EyeTracker
from eye_tracking import predict_eye_state
from class_id import DEFAULT_CLASS_ID
from engine import AI_INTERVAL, get_class_engine  # noqa: F401

logger = logging.getLogger(__name__)

# Used only when process_frame() is called without a tracker.
_fallback_tracker = EyeTracker()


# ------------------------------------------------------------
# wrappers around the per-class engine
# ------------------------------------------------------------

def set_latest_frame(frame, class_id=DEFAULT_CLASS_ID):
    get_class_engine(class_id).set_latest_frame(frame)


def get_latest_results(class_id=DEFAULT_CLASS_ID):
    return get_class_engine(class_id).get_latest_results()


def clear_latest_results(class_id=DEFAULT_CLASS_ID):
    get_class_engine(class_id).clear_latest_results()


def start_ai_thread(class_id=DEFAULT_CLASS_ID):
    return get_class_engine(class_id).start()


def stop_ai_thread(class_id=DEFAULT_CLASS_ID):
    get_class_engine(class_id).stop()


def process_frame(
    frame, face_scale_factor=1.3, tracker=None, person_boxes=None
):
    """Detect people, faces, emotions and eye states in ONE frame.

    tracker       the EyeTracker of this camera / class (a shared fallback
                  is used when omitted).
    person_boxes  optional list that is filled with the YOLO person boxes
                  (x1, y1, x2, y2) - used by the teacher-presence alert.

    Returns one result dict per face. The frame is annotated in place.
    """

    if tracker is None:
        tracker = _fallback_tracker

    if person_boxes is None:
        person_boxes = []

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
            person_boxes.append((x1, y1, x2, y2))

            # =================================================
            # 3. FACE DETECTION
            # =================================================

            gray_person = cv2.cvtColor(
                person_crop,
                cv2.COLOR_BGR2GRAY
            )

            faces = face_detector.detectMultiScale(
                gray_person,
                scaleFactor=face_scale_factor,
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

                    track_id = tracker.get_track_id(
                        face_center_x,
                        face_center_y
                    )

                    # =================================================
                    # 10. CONVERT TO DISPLAY STATE
                    # =================================================

                    eye_state = (
                        tracker.update_display_state(
                            track_id,
                            raw_eye_state
                        )
                    )
                    logger.debug("Track %s | Raw Eye: %s | Display Eye: %s", track_id, raw_eye_state, eye_state)

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

        logger.exception("Process frame error")

    return results
