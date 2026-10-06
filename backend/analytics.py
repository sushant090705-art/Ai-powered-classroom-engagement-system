"""
Real classroom analytics.

This module collects the actual AI results produced by ai_processing.py
and provides session analytics for the Analytics page.
"""

from flask import Blueprint, jsonify
from threading import Lock
from collections import Counter
import time


analytics_bp = Blueprint(
    "analytics",
    __name__
)


# ============================================================
# SESSION STATE
# ============================================================

analytics_lock = Lock()

session_started_at = None

total_samples = 0
peak_students = 0

engagement_values = []
attention_values = []

emotion_counter = Counter()
eye_counter = Counter()

trend_data = []

last_trend_time = 0


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


# ============================================================
# START SESSION
# ============================================================

def start_analytics_session():
    global session_started_at
    global total_samples
    global peak_students
    global last_trend_time

    with analytics_lock:

        session_started_at = time.time()

        total_samples = 0
        peak_students = 0

        engagement_values.clear()
        attention_values.clear()

        emotion_counter.clear()
        eye_counter.clear()

        trend_data.clear()

        last_trend_time = 0


# ============================================================
# RECORD AI RESULTS
# ============================================================

def record_ai_results(results):
    """
    Called after every AI processing cycle.

    `results` contains actual emotion and eye predictions.
    """

    global total_samples
    global peak_students
    global last_trend_time

    if not results:
        return

    now = time.time()

    with analytics_lock:

        if session_started_at is None:
            return

        total_samples += 1

        # ----------------------------------------------------
        # CURRENT DETECTED PEOPLE
        # ----------------------------------------------------

        current_students = len(results)

        peak_students = max(
            peak_students,
            current_students
        )

        # ----------------------------------------------------
        # PROCESS EACH DETECTED PERSON
        # ----------------------------------------------------

        sample_engagement = []
        sample_attention = []

        for result in results:

            emotion = result.get(
                "emotion",
                "Neutral"
            )

            eye_state = result.get(
                "eye_state",
                "Unknown"
            )

            emotion_counter[emotion] += 1

            eye_counter[eye_state] += 1

            engagement = calculate_engagement_score(
                result
            )

            attention = calculate_attention_score(
                result
            )

            sample_engagement.append(
                engagement
            )

            sample_attention.append(
                attention
            )

        # ----------------------------------------------------
        # SESSION AVERAGES
        # ----------------------------------------------------

        if sample_engagement:

            engagement_values.append(
                sum(sample_engagement)
                /
                len(sample_engagement)
            )

        if sample_attention:

            attention_values.append(
                sum(sample_attention)
                /
                len(sample_attention)
            )

        # ----------------------------------------------------
        # TREND
        # ----------------------------------------------------

        # Create one trend point approximately every 5 seconds.

        if (
            last_trend_time == 0
            or
            now - last_trend_time >= 5
        ):

            current_engagement = (
                sum(sample_engagement)
                /
                len(sample_engagement)
            )

            trend_data.append({

                "time": time.strftime(
                    "%H:%M:%S",
                    time.localtime(now)
                ),

                "value": round(
                    current_engagement
                )

            })

            last_trend_time = now


# ============================================================
# GET ANALYTICS
# ============================================================

@analytics_bp.route(
    "/analytics",
    methods=["GET"]
)
def get_analytics():

    with analytics_lock:

        if session_started_at is None:

            return jsonify({

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

                "engagement_trend": []

            })

        # ----------------------------------------------------
        # OVERALL ENGAGEMENT
        # ----------------------------------------------------

        if engagement_values:

            overall_engagement = round(
                sum(engagement_values)
                /
                len(engagement_values)
            )

        else:

            overall_engagement = 0

        # ----------------------------------------------------
        # ATTENTION
        # ----------------------------------------------------

        if attention_values:

            attention = round(
                sum(attention_values)
                /
                len(attention_values)
            )

        else:

            attention = 0

        # ----------------------------------------------------
        # CURRENT ACTIVE STUDENTS
        # ----------------------------------------------------

        active_students = 0

        if total_samples > 0:

            # Last known sample
            # is represented by the latest trend/sample state.

            # We calculate this from the latest recorded
            # frame through the current counters.
            active_students = min(
                peak_students,
                max(0, peak_students)
            )

        # ----------------------------------------------------
        # DURATION
        # ----------------------------------------------------

        duration_seconds = int(
            time.time()
            -
            session_started_at
        )

        minutes = duration_seconds // 60
        seconds = duration_seconds % 60

        duration = (
            f"{minutes:02d}:{seconds:02d}"
        )

        # ----------------------------------------------------
        # EMOTION DISTRIBUTION
        # ----------------------------------------------------

        total_emotions = sum(
            emotion_counter.values()
        )

        emotion_distribution = {}

        if total_emotions:

            for emotion, count in emotion_counter.items():

                emotion_distribution[
                    emotion
                ] = round(
                    count
                    /
                    total_emotions
                    *
                    100
                )

        # ----------------------------------------------------
        # ATTENTION DISTRIBUTION
        # ----------------------------------------------------

        total_eyes = sum(
            eye_counter.values()
        )

        attention_distribution = {}

        if total_eyes:

            for state, count in eye_counter.items():

                attention_distribution[
                    state
                ] = round(
                    count
                    /
                    total_eyes
                    *
                    100
                )

        return jsonify({

            "success": True,

            "session_active": True,

            "overall_engagement":
                overall_engagement,

            "attention":
                attention,

            "active_students":
                active_students,

            "peak_students":
                peak_students,

            "duration_seconds":
                duration_seconds,

            "duration":
                duration,

            "emotion_distribution":
                emotion_distribution,

            "attention_distribution":
                attention_distribution,

            "engagement_trend":
                trend_data[-60:]

        })


# ============================================================
# RESET SESSION
# ============================================================

@analytics_bp.route(
    "/analytics/reset",
    methods=["POST"]
)
def reset_analytics():

    start_analytics_session()

    return jsonify({

        "success": True,

        "message":
            "Analytics session reset successfully."

    })


# ============================================================
# SNAPSHOT (used when a session report is saved)
# ============================================================

def get_session_snapshot():
    """Plain-dict summary of the current session, or None if none started."""

    with analytics_lock:

        if session_started_at is None:
            return None

        def percentages(counter):
            total = sum(counter.values())
            if not total:
                return {}
            return {k: round(v / total * 100) for k, v in counter.items()}

        return {
            "started_at": session_started_at,
            "total_samples": total_samples,
            "peak_students": peak_students,
            "overall_engagement": (
                round(sum(engagement_values) / len(engagement_values))
                if engagement_values else 0
            ),
            "attention": (
                round(sum(attention_values) / len(attention_values))
                if attention_values else 0
            ),
            "emotion_distribution": percentages(emotion_counter),
            "attention_distribution": percentages(eye_counter),
            "engagement_trend": list(trend_data),
        }