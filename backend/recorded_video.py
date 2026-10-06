"""Recorded-video analysis.

Reuses the live pipeline (ai_processing.process_frame: YOLO person ->
face -> emotion + eye state) on frames sampled from the video, and then
turns the per-frame detections into per-student reports:

  * every face is tracked across frames, so one person = one student ID
    (before, detections from every sampled frame were simply added up, which
    is why a 3-person video reported dozens of "faces");
  * Drowsy / Sleeping are worked out on the VIDEO clock (how long the eyes
    were really closed in the video) instead of the wall clock;
  * engagement / attention use the same scoring as the Analytics page
    (analytics.py), via student_reports.py.
"""

from flask import Blueprint, request, jsonify
import os
import time
import uuid
import threading
import cv2
import numpy as np

from ai_processing import (
    process_frame
)
from eye_tracking import (
    BLINK_MAX_DURATION,
    SLEEPING_THRESHOLD,
    BLINK_DISPLAY_DURATION,
)
from student_reports import (
    StudentRegistry,
    box_iou,
)


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


def analyze_video_file(video_path, progress=None):
    """
    Analyse a video file and return the JSON-ready result.

    progress: optional callable(fraction_0_to_1, stage_text, students_found)
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

        registry = StudentRegistry(present_timeout=TRACK_TIMEOUT)
        registry.reset(0.0)

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

            results = process_frame(
                _shrink_if_large(frame),
                face_scale_factor=FACE_SCALE_FACTOR
            )

            if results is None:
                results = []

            results = _unique_faces(results)

            processed_frames += 1
            total_detections += len(results)

            detections = []

            for result in results:

                emotion = result["emotion"]

                emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1

                detections.append((
                    (
                        result["x"],
                        result["y"],
                        result["width"],
                        result["height"]
                    ),
                    {
                        "emotion": emotion,
                        "confidence": result["confidence"],
                        "eye_state": result["eye_state"],
                        "eye_confidence": result["eye_confidence"],
                    }
                ))

            registry.update(detections, now=t, face_hook=eye_hook)

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

            print(
                "Could not delete "
                "temporary video:",
                e
            )


def _video_job_worker(job_id, video_path):

    def progress(fraction, stage, students_found):

        with video_jobs_lock:

            job = video_jobs.get(job_id)

            if job is not None:

                job["progress"] = round(float(fraction), 3)
                job["stage"] = stage
                job["students_found"] = int(students_found)

    try:

        result = analyze_video_file(video_path, progress)

        with video_jobs_lock:

            video_jobs[job_id].update({
                "status": "done",
                "progress": 1.0,
                "stage": "Done",
                "result": result
            })

    except Exception as e:

        print("VIDEO ANALYSIS ERROR:", e)

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
                args=(job_id, video_path),
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
            analyze_video_file(video_path)
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

        print(
            "VIDEO ANALYSIS ERROR:",
            e
        )

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


print(
    "Recorded video module loaded successfully!"
)
