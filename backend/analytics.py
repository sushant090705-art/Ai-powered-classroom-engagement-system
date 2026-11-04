"""
Real classroom analytics.

This module collects the actual AI results produced by the AI pipeline
and provides session analytics for the Analytics page.

Each class / camera has its own AnalyticsSession (point 12). The module
level functions and routes still work without a class id: they use the
default class.
"""

import time
from collections import Counter
from threading import Lock, RLock

from flask import Blueprint, jsonify, request

from class_id import DEFAULT_CLASS_ID, normalize_class_id


analytics_bp = Blueprint(
    "analytics",
    __name__
)


# ============================================================
# SCORE CALCULATIONS
# ============================================================

def calculate_engagement_score(result):
    """
    Calculate an engagement indicator from the actual
    emotion + eye state detected by the AI.

    This is an analytical indicator, not a separately
    trained engagement model.
    """

    eye_state = result.get(
        "eye_state",
        "Unknown"
    )

    emotion = result.get(
        "emotion",
        "Neutral"
    )

    eye_scores = {
        "Open": 85,
        "Blink": 70,
        "Close": 35,
        "Drowsy": 20,
        "Sleeping": 5,
        "Unknown": 50
    }

    emotion_scores = {
        "Happy": 85,
        "Neutral": 70,
        "Surprise": 65,
        "Fear": 45,
        "Angry": 40,
        "Sad": 35,
        "Disgust": 35
    }

    eye_score = eye_scores.get(
        eye_state,
        50
    )

    emotion_score = emotion_scores.get(
        emotion,
        50
    )

    score = (
        eye_score * 0.65
        +
        emotion_score * 0.35
    )

    return round(
        max(0, min(100, score))
    )


def calculate_attention_score(result):
    """
    Attention is primarily based on eye state.
    """

    eye_state = result.get(
        "eye_state",
        "Unknown"
    )

    scores = {
        "Open": 100,
        "Blink": 85,
        "Close": 35,
        "Drowsy": 15,
        "Sleeping": 0,
        "Unknown": 50
    }

    return scores.get(
        eye_state,
        50
    )


def engagement_level(score):
    """Engaged / Moderate / Low - same cut-offs everywhere in the app."""

    if score >= 75:
        return "Engaged"

    if score >= 50:
        return "Moderate"

    return "Low"


def annotate_engagement(faces):
    """Return copies of the face results with 'engagement' (0-100) and
    'engagement_level' added, so the frontend never has to re-implement
    the formula. The shared results list is left untouched."""

    annotated = []

    for face in faces or []:

        item = dict(face)
        score = calculate_engagement_score(item)

        item["engagement"] = score
        item["engagement_level"] = engagement_level(score)

        annotated.append(item)

    return annotated


# ============================================================
# ONE ANALYTICS SESSION (per class)
# ============================================================

TREND_INTERVAL_SECONDS = 5


class AnalyticsSession:
    """Running statistics of one class session.

    wall_clock=True  : `now` values are time.time() (live camera).
    wall_clock=False : `now` is a position in a recorded video (seconds);
                       trend labels are then mm:ss of the video.
    """

    def __init__(self, class_id=DEFAULT_CLASS_ID, wall_clock=True):

        self.class_id = class_id
        self.wall_clock = wall_clock
        self.lock = Lock()
        self.session_started_at = None
        self._clear()

    def _clear(self):

        self.total_samples = 0
        self.peak_students = 0
        self.current_students = 0     # faces in the most recent AI cycle
        self.engagement_values = []
        self.attention_values = []
        self.emotion_counter = Counter()
        self.eye_counter = Counter()
        self.trend_data = []
        self.last_trend_time = None

    # --------------------------------------------------------

    def start(self, now=None):

        with self.lock:
            self.session_started_at = time.time() if now is None else now
            self._clear()

    def _label(self, now):

        if self.wall_clock:
            return time.strftime("%H:%M:%S", time.localtime(now))

        return f"{int(now // 60):02d}:{int(now % 60):02d}"

    def record(self, results, now=None):
        """Add one AI cycle. Called after every processing cycle."""

        if not results:
            # Nobody visible: the live count drops to 0, averages stay.
            with self.lock:
                self.current_students = 0
            return

        now = time.time() if now is None else now

        with self.lock:

            if self.session_started_at is None:
                return

            self.total_samples += 1
            self.current_students = len(results)
            self.peak_students = max(self.peak_students, len(results))

            sample_engagement = []
            sample_attention = []

            for result in results:

                self.emotion_counter[result.get("emotion", "Neutral")] += 1
                self.eye_counter[result.get("eye_state", "Unknown")] += 1

                sample_engagement.append(calculate_engagement_score(result))
                sample_attention.append(calculate_attention_score(result))

            mean_engagement = sum(sample_engagement) / len(sample_engagement)
            mean_attention = sum(sample_attention) / len(sample_attention)

            self.engagement_values.append(mean_engagement)
            self.attention_values.append(mean_attention)

            # One trend point about every TREND_INTERVAL_SECONDS.
            if (
                self.last_trend_time is None
                or now - self.last_trend_time >= TREND_INTERVAL_SECONDS
            ):
                self.trend_data.append({
                    "time": self._label(now),
                    "value": round(mean_engagement),
                })
                self.last_trend_time = now

    # --------------------------------------------------------

    @staticmethod
    def _percentages(counter):

        total = sum(counter.values())

        if not total:
            return {}

        return {k: round(v / total * 100) for k, v in counter.items()}

    @staticmethod
    def _average(values):
        return round(sum(values) / len(values)) if values else 0

    def snapshot(self):
        """Plain-dict summary of the session, or None if none started."""

        with self.lock:

            if self.session_started_at is None:
                return None

            return {
                "started_at": self.session_started_at,
                "total_samples": self.total_samples,
                "peak_students": self.peak_students,
                "overall_engagement": self._average(self.engagement_values),
                "attention": self._average(self.attention_values),
                "emotion_distribution": self._percentages(self.emotion_counter),
                "attention_distribution": self._percentages(self.eye_counter),
                "engagement_trend": list(self.trend_data),
            }

    def payload(self):
        """The JSON shown on the Analytics page."""

        with self.lock:

            if self.session_started_at is None:
                return {
                    "success": True,
                    "session_active": False,
                    "overall_engagement": 0,
                    "attention": 0,
                    "active_students": 0,
                    "peak_students": 0,
                    "duration_seconds": 0,
                    "duration": "00:00",
                    "emotion_distribution": {},
                    "attention_distribution": {},
                    "engagement_trend": [],
                }

            duration_seconds = int(
                (time.time() if self.wall_clock else self.last_trend_time or 0)
                - self.session_started_at
            )

            return {
                "success": True,
                "session_active": True,
                "overall_engagement": self._average(self.engagement_values),
                "attention": self._average(self.attention_values),
                "active_students": self.current_students,
                "peak_students": self.peak_students,
                "duration_seconds": duration_seconds,
                "duration": (
                    f"{duration_seconds // 60:02d}:"
                    f"{duration_seconds % 60:02d}"
                ),
                "emotion_distribution": self._percentages(self.emotion_counter),
                "attention_distribution": self._percentages(self.eye_counter),
                "engagement_trend": self.trend_data[-60:],
            }


# ============================================================
# SESSIONS PER CLASS
# ============================================================

_sessions = {}
_sessions_lock = RLock()


def get_analytics_session(class_id=DEFAULT_CLASS_ID):
    """The AnalyticsSession of a class (created on first use)."""

    with _sessions_lock:

        session = _sessions.get(class_id)

        if session is None:
            session = _sessions[class_id] = AnalyticsSession(class_id)

        return session


# Module-level helpers kept for existing callers (default class).

def start_analytics_session(class_id=DEFAULT_CLASS_ID):
    get_analytics_session(class_id).start()


def record_ai_results(results, class_id=DEFAULT_CLASS_ID, now=None):
    get_analytics_session(class_id).record(results, now)


def get_session_snapshot(class_id=DEFAULT_CLASS_ID):
    return get_analytics_session(class_id).snapshot()


# ============================================================
# ROUTES
# ============================================================

def _requested_class_id():
    return normalize_class_id(request.args.get("class_id"))


@analytics_bp.route("/analytics", methods=["GET"])
def get_analytics():

    try:
        class_id = _requested_class_id()
    except ValueError as error:
        return jsonify({"success": False, "message": str(error)}), 400

    return jsonify(get_analytics_session(class_id).payload())


@analytics_bp.route("/analytics/reset", methods=["POST"])
def reset_analytics():

    try:
        class_id = _requested_class_id()
    except ValueError as error:
        return jsonify({"success": False, "message": str(error)}), 400

    start_analytics_session(class_id)

    return jsonify({
        "success": True,
        "message": "Analytics session reset successfully.",
    })
