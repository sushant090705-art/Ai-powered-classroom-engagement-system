"""Recorded-video analysis.

Runs the SAME engine as the live camera (engine.py: detect() + ingest()) on
frames sampled from the video, so a recorded lecture also gets analytics and
the alert rules (teacher absent / low engagement / drowsy class) - measured
on the video clock - and then turns the per-frame detections into
per-student reports:

  * every face is tracked across frames, so one person = one student ID
    (before, detections from every sampled frame were simply added up, which
    is why a 3-person video reported dozens of "faces");
  * Drowsy / Sleeping are worked out on the VIDEO clock (how long the eyes
    were really closed in the video) instead of the wall clock;
  * engagement / attention use the same scoring as the Analytics page
    (analytics.py), via student_reports.py.
"""

import logging
from flask import Blueprint, request, jsonify
import os
import time
import uuid
import threading
import cv2
import numpy as np

from alerts import get_alert_engine
from class_id import DEFAULT_CLASS_ID, normalize_class_id
from engine import ClassEngine
from eye_state import (
    BLINK_MAX_DURATION,
    SLEEPING_THRESHOLD,
    BLINK_DISPLAY_DURATION,
)
from student_reports import box_iou

logger = logging.getLogger(__name__)


# ============================================================
# RECORDED VIDEO BLUEPRINT
# ============================================================

recorded_video_bp = Blueprint(
    "recorded_video",
    __name__
)


# ============================================================
# SETTINGS
# ============================================================

# Frames analysed per second of video. Higher = better eye-closure timing
# but slower. Long videos are sampled less often (MAX_SAMPLES).
SAMPLE_FPS = 2.0
MAX_SAMPLES = 400

# Very large frames are shrunk so the longest side is at most this.
MAX_FRAME_SIDE = 1920

# Haar face-detector scale factor for recorded video. Live camera keeps
# its default (1.3); a smaller value finds faces more reliably in video.
FACE_SCALE_FACTOR = 1.1

# A student is only reported if seen in at least this many sampled frames
# (or this share of all sampled frames, whichever is larger). This removes
# one-off false detections.
MIN_SAMPLES = 3
MIN_SAMPLE_SHARE = 0.05

# How long (video seconds) a student can be missing and still be matched
# loosely; after that they must reappear in the same place.
TRACK_TIMEOUT = 4.0

# If a face is missing for longer than this, its eye timeline restarts.
EYE_TIMELINE_GAP = 2.0


# ============================================================
# BACKGROUND JOBS (so the page can show progress)
# ============================================================

video_jobs = {}
video_jobs_lock = threading.Lock()


# ============================================================
# EYE STATE ON THE VIDEO CLOCK
# ============================================================

def raw_eye_state(display_state):
    """
    process_frame() returns the live display state. The raw Open / Close
    reading is recoverable from it: Close, Drowsy and Sleeping all come
    from a raw Close; Open and Blink come from a raw Open.
    """

    if display_state in ("Close", "Drowsy", "Sleeping"):
        return "Close"

    if display_state in ("Open", "Blink"):
        return "Open"

    return "Unknown"


class VideoEyeTimeline:
    """
    Same Open / Blink / Close / Drowsy / Sleeping rules and thresholds as
    eye_tracking.update_eye_display_state(), but measured in video seconds.
    """

    def __init__(self):

        self.previous_raw = "Unknown"
        self.closed_since = None
        self.blink_until = 0.0
        self.was_sleeping = False
        self.last_time = None

    def update(self, raw, t):

        if (
            self.last_time is not None
            and t - self.last_time > EYE_TIMELINE_GAP
        ):
            self.closed_since = None
            self.previous_raw = "Unknown"
            self.was_sleeping = False

        self.last_time = t

        if raw == "Close":

            if self.previous_raw != "Close":
                self.closed_since = t

            self.previous_raw = "Close"

            closed_for = t - (
                self.closed_since if self.closed_since is not None else t
            )

            if closed_for >= SLEEPING_THRESHOLD:
                self.was_sleeping = True
                return "Sleeping"

            if closed_for >= BLINK_MAX_DURATION:
                return "Drowsy"

            return "Close"

        if raw == "Open":

            closed_for = (
                t - self.closed_since
                if self.closed_since is not None
                else 0.0
            )

            self.previous_raw = "Open"
            self.closed_since = None

            if self.was_sleeping:
                self.was_sleeping = False
                self.blink_until = 0.0
                return "Open"

            if 0 < closed_for < BLINK_MAX_DURATION:
                self.blink_until = t + BLINK_DISPLAY_DURATION
                return "Blink"

            if t < self.blink_until:
                return "Blink"

            return "Open"

        return "Unknown"


# ============================================================
# ANALYSE A VIDEO FILE
# ============================================================

def _shrink_if_large(frame):

    height, width = frame.shape[:2]
    longest = max(height, width)

    if longest <= MAX_FRAME_SIDE:
        return frame

    scale = MAX_FRAME_SIDE / float(longest)

    return cv2.resize(
        frame,
        (int(width * scale), int(height * scale)),
        interpolation=cv2.INTER_AREA
    )


def _unique_faces(results):
    """Drop duplicate detections of the same face (keep the larger one)."""

    ordered = sorted(
        results,
        key=lambda r: r["width"] * r["height"],
        reverse=True
    )

    unique = []

    for result in ordered:

        box = (result["x"], result["y"], result["width"], result["height"])

        if all(
            box_iou(
                box,
                (k["x"], k["y"], k["width"], k["height"])
            ) < 0.4
            for k in unique
        ):
            unique.append(result)

    return unique


def analyze_video_file(video_path, progress=None, class_id=DEFAULT_CLASS_ID):
    """
    Analyse a video file and return the JSON-ready result.

    progress: optional callable(fraction_0_to_1, stage_text, students_found)
    class_id: whose alert thresholds (and teacher zone) are applied.
    """

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise ValueError("Could not open video")

    try:

        # ====================================================
        # VIDEO INFORMATION
        # ====================================================

        fps = float(cap.get(cv2.CAP_PROP_FPS))

        if not np.isfinite(fps) or fps <= 0:
            fps = 25.0

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if total_frames < 0:
            total_frames = 0

        video_duration = total_frames / fps if total_frames else 0.0

        sample_fps = min(SAMPLE_FPS, fps)

        if video_duration > 0:
            sample_fps = min(
                sample_fps,
                max(0.5, MAX_SAMPLES / video_duration)
            )

        frame_step = max(1, int(round(fps / sample_fps)))

        # ====================================================
        # TRACKING STATE
        # ====================================================

        # Same engine as the live camera, running on the video clock.
        engine = ClassEngine.video(
            alert_settings=get_alert_engine(class_id).get_settings(),
            present_timeout=TRACK_TIMEOUT,
        )
        engine.start_session(now=0.0)

        registry = engine.registry

        timelines = {}

        def eye_hook(student_id, face, t):

            timeline = timelines.setdefault(student_id, VideoEyeTimeline())

            face["eye_state"] = timeline.update(
                raw_eye_state(face["eye_state"]),
                t
            )

        emotion_counts = {}
        total_detections = 0
        processed_frames = 0
        last_time = 0.0

        frame_index = -1

        # ====================================================
        # PROCESS VIDEO
        # ====================================================

        while True:

            if not cap.grab():
                break

            frame_index += 1

            if frame_index % frame_step != 0:
                continue

            success, frame = cap.retrieve()

            if not success or frame is None:
                continue

            t = frame_index / fps
            last_time = t

            small_frame = _shrink_if_large(frame)

            # Keep a clean frame BEFORE detect(): process_frame() draws face/person
            # rectangles directly onto the frame it receives. Snapshot crops must
            # use this untouched copy so boxes never become part of student photos.
            clean_frame = small_frame.copy()

            results, person_boxes = engine.detect(
                small_frame,
                face_scale_factor=FACE_SCALE_FACTOR
            )

            results = _unique_faces(results)

            processed_frames += 1

            # Students + analytics + alerts, with the eye state turned
            # into Blink / Drowsy / Sleeping on the VIDEO clock.
            results = engine.ingest(
                results,
                person_boxes,
                clean_frame.shape,
                now=t,
                face_hook=eye_hook,
                frame=clean_frame
            )

            total_detections += len(results)

            for result in results:

                emotion = result["emotion"]

                emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1

            if progress is not None and processed_frames % 3 == 0:

                progress(
                    min(0.99, frame_index / total_frames)
                    if total_frames
                    else 0.0,
                    "Analyzing frames",
                    registry.build_reports(
                        now=t, min_samples=MIN_SAMPLES
                    )["students_total"]
                )

        # ====================================================
        # ALERTS RAISED DURING THE VIDEO (video seconds)
        # ====================================================

        engine.end_session(now=last_time)

        alert_data = engine.alert_engine.get_alerts(limit=500)

        alerts = [
            {
                "type": alert["type"],
                "severity": alert["severity"],
                "title": alert["title"],
                "message": alert["message"],
                "started_at": round(alert["started_at"], 1),
                "resolved_at": (
                    round(alert["resolved_at"], 1)
                    if alert["resolved_at"] is not None else None
                ),
                "details": alert["details"],
            }
            for alert in sorted(
                alert_data["active"] + alert_data["history"],
                key=lambda a: a["started_at"]
            )
        ]

        # ====================================================
        # FINAL REPORT
        # ====================================================

        min_samples = max(
            MIN_SAMPLES,
            int(round(MIN_SAMPLE_SHARE * processed_frames))
        )

        report = registry.build_reports(
            now=last_time,
            min_samples=min_samples
        )

        ignored = (
            registry.build_reports(now=last_time, min_samples=1)[
                "students_total"
            ]
            - report["students_total"]
        )

        notes = []

        if processed_frames and sample_fps < SAMPLE_FPS - 0.01:

            notes.append(
                f"Long video: analysed about {sample_fps:.1f} frame(s) per "
                "second so it finishes in reasonable time."
            )

        if ignored > 0:

            notes.append(
                f"{ignored} very brief detection(s) were ignored as "
                "false detections."
            )

        if report["students_total"] == 0:

            notes.append(
                "No faces were found. Use a video where faces are clearly "
                "visible, well lit and not too small."
            )

        most_common_emotion = "Unknown"

        if emotion_counts:

            most_common_emotion = max(
                emotion_counts,
                key=emotion_counts.get
            )

        return {

            "success": True,

            "message": "Video analyzed successfully",

            "duration_seconds": round(video_duration, 2),
            "total_frames": total_frames,
            "processed_frames": processed_frames,
            "fps": fps,
            "sample_fps": round(sample_fps, 2),

            # Unique students (this used to be the SUM of detections over
            # all sampled frames, which inflated the count).
            "total_faces_detected": report["students_total"],
            "total_students": report["students_total"],

            # Raw number of face detections across all sampled frames.
            "total_detections": total_detections,

            "students": report["students"],
            "class_average_engagement": report["class_average_engagement"],

            "emotion_counts": emotion_counts,
            "most_common_emotion": most_common_emotion,

            "notes": notes,
            # Same alert rules as the live camera, on the video clock
            # (times are seconds into the video).
            "alerts": alerts,
            "class_analytics": engine.analytics.snapshot(),
        }

    finally:

        cap.release()


# ============================================================
# HELPERS
# ============================================================

def _remove_file(path):

    if path and os.path.exists(path):

        try:

            os.remove(path)

        except Exception as e:

            logger.warning("Could not delete temporary video: %s", e)


def _video_job_worker(job_id, video_path, class_id=DEFAULT_CLASS_ID):

    def progress(fraction, stage, students_found):

        with video_jobs_lock:

            job = video_jobs.get(job_id)

            if job is not None:

                job["progress"] = round(float(fraction), 3)
                job["stage"] = stage
                job["students_found"] = int(students_found)

    try:

        result = analyze_video_file(video_path, progress, class_id)

        with video_jobs_lock:

            video_jobs[job_id].update({
                "status": "done",
                "progress": 1.0,
                "stage": "Done",
                "result": result
            })

    except Exception as e:

        logger.exception("Video analysis error")

        with video_jobs_lock:

            video_jobs[job_id].update({
                "status": "error",
                "error": str(e)
            })

    finally:

        _remove_file(video_path)


# ============================================================
# ANALYZE RECORDED VIDEO
# ============================================================

@recorded_video_bp.route(
    "/analyze-video",
    methods=["POST"]
)
def analyze_video():

    video_path = None
    started_background_job = False

    try:

        # Whose alert thresholds apply (form field or query string).
        class_id = normalize_class_id(
            request.form.get("class_id") or request.args.get("class_id")
        )

        # ====================================================
        # CHECK VIDEO
        # ====================================================

        if "video" not in request.files:

            return jsonify({
                "success": False,
                "message":
                    "No video received"
            }), 400

        video_file = (
            request.files["video"]
        )

        if (
            video_file.filename
            == ""
        ):

            return jsonify({
                "success": False,
                "message":
                    "No video selected"
            }), 400

        # ====================================================
        # UPLOAD FOLDER
        # ====================================================

        upload_folder = os.path.join(
            os.path.dirname(
                os.path.abspath(
                    __file__
                )
            ),
            "uploads"
        )

        os.makedirs(
            upload_folder,
            exist_ok=True
        )

        filename = (
            f"uploaded_"
            f"{uuid.uuid4().hex}.mp4"
        )

        video_path = os.path.join(
            upload_folder,
            filename
        )

        video_file.save(
            video_path
        )

        # ====================================================
        # BACKGROUND MODE (the web page uses this so it can show
        # a progress bar)
        # ====================================================

        if request.form.get("async") == "1":

            job_id = uuid.uuid4().hex

            with video_jobs_lock:

                # forget jobs older than one hour
                for old_id in [
                    jid for jid, job in video_jobs.items()
                    if time.time() - job["created"] > 3600
                ]:
                    del video_jobs[old_id]

                video_jobs[job_id] = {
                    "status": "running",
                    "progress": 0.0,
                    "stage": "Starting",
                    "students_found": 0,
                    "created": time.time()
                }

            threading.Thread(
                target=_video_job_worker,
                args=(job_id, video_path, class_id),
                daemon=True
            ).start()

            started_background_job = True

            return jsonify({
                "success": True,
                "job_id": job_id
            })

        # ====================================================
        # CLASSIC MODE: analyse and return the result
        # ====================================================

        return jsonify(
            analyze_video_file(video_path, class_id=class_id)
        )

    # ========================================================
    # ERROR
    # ========================================================

    except ValueError as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 400

    except Exception as e:

        logger.exception("Video analysis error")

        return jsonify({
            "success":
                False,
            "message":
                str(e)
        }), 500

    # ========================================================
    # CLEANUP
    # ========================================================

    finally:

        # A background job deletes the file itself when it finishes.
        if not started_background_job:

            _remove_file(video_path)


# ============================================================
# BACKGROUND JOB STATUS
# ============================================================

@recorded_video_bp.route(
    "/analyze-video/status/<job_id>",
    methods=["GET"]
)
def analyze_video_status(job_id):

    with video_jobs_lock:

        job = video_jobs.get(job_id)

        if job is None:

            return jsonify({
                "success": False,
                "message": "Unknown or expired analysis job"
            }), 404

        return jsonify({
            "success": True,
            **{k: v for k, v in job.items() if k != "created"}
        })


logger.debug("Recorded video module loaded successfully!")
