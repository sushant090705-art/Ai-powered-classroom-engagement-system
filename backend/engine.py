"""Shared classroom engine (points 12 and 13).

One ClassEngine = everything that belongs to ONE class / camera:

    eye tracker  -> per-face Open / Blink / Drowsy / Sleeping state
    registry     -> one record per tracked student (student reports)
    analytics    -> live engagement / attention / emotion statistics
    alert engine -> teacher absent / low engagement / drowsy class alerts
    storage      -> engagement samples written to SQLite (live only)

Both input sources go through the SAME code path:

    live camera      ClassEngine.live(class_id).start()  -> background thread
                     calls detect() + ingest() twice a second
    recorded video   ClassEngine.video(...)              -> recorded_video.py
                     calls detect() + ingest() for sampled frames, with
                     `now` = position in the video (seconds)

so a recorded lecture produces the same analytics, student reports AND
alerts as a live one. Several classes run side by side: each has its own
ClassEngine, looked up by class id (get_class_engine).

This module does not import the AI models at import time (detect() loads
ai_processing lazily), so everything here can be unit tested without
TensorFlow / YOLO.
"""

import logging
import os
import threading
import time
import uuid

from alerts import DROWSY_STATES, AlertEngine, get_alert_engine
from analytics import (
    AnalyticsSession,
    calculate_attention_score,
    calculate_engagement_score,
    get_analytics_session,
)
from class_id import DEFAULT_CLASS_ID, normalize_class_id
from eye_state import EyeTracker
from storage import get_storage
from student_reports import StudentRegistry

logger = logging.getLogger(__name__)

# The AI loop of a live class runs this often.
AI_INTERVAL = 0.5

# Engagement is written to the database about this often (seconds).
SAMPLE_INTERVAL = 5.0

# YOLO / Keras models are shared by every class. Inference is serialised so
# two cameras never call the same model object at the same moment.
inference_lock = threading.Lock()


def _no_notification(alert, email):
    """Notifier for recorded-video analysis: never send e-mails."""


class ClassEngine:

    def __init__(
        self,
        class_id,
        analytics,
        alert_engine,
        registry,
        tracker,
        store=None,
        kind="live",
    ):

        self.class_id = class_id
        self.analytics = analytics
        self.alert_engine = alert_engine
        self.registry = registry
        self.tracker = tracker
        self.store = store
        self.kind = kind

        self.session_id = None
        self.session_active = False

        self._last_sample_at = None

        # Live camera state
        self._frame = None
        self._results = []
        self._frame_lock = threading.Lock()
        self._results_lock = threading.Lock()
        self._thread_lock = threading.Lock()
        self._thread = None
        self._generation = 0
        self.running = False

    # --------------------------------------------------------
    # constructors
    # --------------------------------------------------------

    @classmethod
    def live(cls, class_id=DEFAULT_CLASS_ID):
        """Engine of a live camera: global per-class analytics + alerts."""

        return cls(
            class_id,
            analytics=get_analytics_session(class_id),
            alert_engine=get_alert_engine(class_id),
            registry=StudentRegistry(),
            tracker=EyeTracker(),
            store=get_storage(),
            kind="live",
        )

    @classmethod
    def video(cls, alert_settings=None, present_timeout=None):
        """Throw-away engine for ONE recorded video.

        Uses the video clock for everything, keeps nothing on disk and
        never sends e-mail.
        """

        settings = dict(alert_settings or {})
        settings["schedule_enforced"] = False
        settings["notify_email"] = ""

        registry = (
            StudentRegistry(present_timeout=present_timeout)
            if present_timeout is not None else StudentRegistry()
        )

        return cls(
            "video",
            analytics=AnalyticsSession("video", wall_clock=False),
            alert_engine=AlertEngine(
                data_dir=None,
                notifier=_no_notification,
                class_id="video",
                settings=settings,
            ),
            registry=registry,
            tracker=EyeTracker(),
            store=None,
            kind="recorded",
        )

    # --------------------------------------------------------
    # session lifecycle
    # --------------------------------------------------------

    def start_session(self, now=None):
        """Reset all per-session state."""

        self.session_id = uuid.uuid4().hex
        self._last_sample_at = None

        self.analytics.start(now)
        self.registry.reset(now)
        self.tracker.reset()
        self.alert_engine.start_session(
            now=now,
            session_id=self.session_id
        )

        if self.store is not None:
            try:
                self.store.create_session(
                    self.session_id,
                    self.class_id,
                    time.time() if now is None else now,
                    self.kind,
                )
            except Exception:
                logger.exception("Could not open session in the database")

        self.session_active = True

    def end_session(self, now=None):
        """Stop alert monitoring while keeping report data."""

        self.alert_engine.end_session(now)
        self.session_active = False

    # --------------------------------------------------------
    # the shared pipeline
    # --------------------------------------------------------

    def detect(self, frame, face_scale_factor=1.3):
        """Run the AI models on one frame."""

        from ai_processing import process_frame

        person_boxes = []

        with inference_lock:
            results = process_frame(
                frame,
                face_scale_factor=face_scale_factor,
                tracker=self.tracker,
                person_boxes=person_boxes,
            )

        return results or [], person_boxes

    def ingest(
        self,
        results,
        person_boxes,
        frame_shape,
        now=None,
        face_hook=None,
        frame=None,
        snapshot_scale=1.0,
    ):
        """Feed one AI cycle into students, analytics and alerts."""

        clock = time.time() if now is None else now

        # ---- students ----------------------------------------

        detections = [
            (
                (r["x"], r["y"], r["width"], r["height"]),
                {
                    "emotion": r["emotion"],
                    "confidence": r["confidence"],
                    "eye_state": r["eye_state"],
                    "eye_confidence": r["eye_confidence"],
                },
            )
            for r in results
        ]
        
        try:
            student_ids = self.registry.update(
                detections,
                now=now,
                face_hook=face_hook
            )

            # Save clean face crops for live and recorded sessions.
            if (
                frame is not None
                and self.session_id
                and self.kind in ("live", "recorded")
            ):
                try:
                    from student_snapshots import save_clear_face_snapshot

                    snapshot_root = os.path.join(
                        os.path.dirname(os.path.abspath(__file__)),
                        "data",
                        "student_photos",
                        self.class_id,
                        self.session_id,
                    )

                    for student_id, (box, _face) in zip(
                        student_ids, detections
                    ):
                        destination = os.path.join(
                            snapshot_root,
                            f"student_{student_id}.jpg"
                        )

                        os.makedirs(
                            snapshot_root,
                            exist_ok=True
                        )

                        quality = save_clear_face_snapshot(
                            frame,
                            box,
                            destination + ".tmp.jpg",
                            scale=snapshot_scale
                        )

                        if quality is not None:
                            current = self.registry.photo_quality(
                                student_id
                            )

                            if quality > current:
                                os.replace(
                                    destination + ".tmp.jpg",
                                    destination
                                )

                                photo_url = (
                                    f"/student-photos/{self.class_id}/"
                                    f"{self.session_id}/"
                                    f"student_{student_id}.jpg"
                                )

                                self.registry.set_photo(
                                    student_id,
                                    photo_url,
                                    quality
                                )
                            else:
                                try:
                                    os.remove(destination + ".tmp.jpg")
                                except OSError:
                                    pass

                except Exception:
                    logger.exception(
                        "Student snapshot capture failed [class %s]",
                        self.class_id,
                    )

            results = [
                dict(result, eye_state=face["eye_state"])
                for result, (_box, face) in zip(results, detections)
            ]

        except Exception:
            logger.exception(
                "Student registry update failed [class %s]",
                self.class_id
            )

        # ---- analytics ----------------------------------------

        try:
            self.analytics.record(results, clock)
        except Exception:
            logger.exception(
                "Analytics update failed [class %s]",
                self.class_id
            )

        # ---- alerts -------------------------------------------

        try:
            self.alert_engine.evaluate(
                list(person_boxes),
                results,
                frame_shape,
                now=clock
            )
        except Exception:
            logger.exception(
                "Alert evaluation failed [class %s]",
                self.class_id
            )

        # ---- time series storage ------------------------------

        self._maybe_store_sample(results, clock)

        return results

    def _maybe_store_sample(self, results, clock):

        if self.store is None or self.session_id is None:
            return

        if (
            self._last_sample_at is not None
            and clock - self._last_sample_at < SAMPLE_INTERVAL
        ):
            return

        self._last_sample_at = clock

        if results:
            engagement = sum(
                calculate_engagement_score(r) for r in results
            ) / len(results)

            attention = sum(
                calculate_attention_score(r) for r in results
            ) / len(results)

            drowsy = 100.0 * sum(
                1 for r in results
                if r.get("eye_state") in DROWSY_STATES
            ) / len(results)
        else:
            engagement = attention = drowsy = None

        try:
            self.store.add_sample(
                self.session_id,
                clock,
                len(results),
                engagement,
                attention,
                drowsy,
            )
        except Exception:
            logger.exception("Could not store engagement sample")

    # --------------------------------------------------------
    # live camera: latest frame / results, background AI thread
    # --------------------------------------------------------

    def set_latest_frame(self, frame):

        with self._frame_lock:
            self._frame = None if frame is None else frame.copy()

    def get_latest_results(self):

        with self._results_lock:
            return list(self._results)

    def clear_latest_results(self):

        with self._results_lock:
            self._results = []

    def start(self):
        """Start a live session and its AI thread."""

        with self._thread_lock:

            if self.running:
                return False

            self.start_session()

            self._generation += 1
            self.running = True

            self._thread = threading.Thread(
                target=self._loop,
                args=(self._generation,),
                name=f"ai-{self.class_id}",
                daemon=True,
            )

            self._thread.start()

            return True

    def stop(self):
        """Stop the AI thread and the alert session."""

        with self._thread_lock:

            was_running = self.running
            self.running = False
            self._generation += 1

        if was_running or self.session_active:
            self.end_session()

    def _loop(self, generation):

        logger.info(
            "AI processing thread started [class %s].",
            self.class_id
        )

        last_cycle = 0.0

        while self.running and generation == self._generation:

            current = time.time()

            if current - last_cycle < AI_INTERVAL:
                time.sleep(0.01)
                continue

            # Get the latest camera frame.
            with self._frame_lock:
                frame = (
                    None if self._frame is None
                    else self._frame.copy()
                )

            if frame is None:
                time.sleep(0.05)
                continue

            last_cycle = current

            try:
                # IMPORTANT:
                # Keep an untouched frame for student photo snapshots.
                original_frame = frame.copy()

                # Detection may draw boxes and labels on `frame`.
                results, person_boxes = self.detect(frame)

                # Pass the untouched frame to ingest().
                # Student snapshots will therefore have no detection boxes.
                results = self.ingest(
                    results,
                    person_boxes,
                    original_frame.shape,
                    frame=original_frame
                )

            except Exception:
                logger.exception(
                    "AI cycle failed [class %s]",
                    self.class_id
                )
                time.sleep(AI_INTERVAL)
                continue

            with self._results_lock:
                self._results = results

        logger.info(
            "AI processing thread stopped [class %s].",
            self.class_id
        )


# ============================================================
# ENGINES PER CLASS
# ============================================================

_engines = {}
_engines_lock = threading.RLock()


def get_class_engine(class_id=DEFAULT_CLASS_ID):
    """The live ClassEngine of a class (created on first use)."""

    class_id = normalize_class_id(class_id)

    with _engines_lock:

        found = _engines.get(class_id)

        if found is None:
            found = _engines[class_id] = ClassEngine.live(class_id)

        return found


def list_class_engines():
    """Every class that has been used since the server started."""

    with _engines_lock:
        return dict(_engines)