"""Module 5: Alert & Recommendation Engine for Authorities.

Watches the live AI results (the same ones that feed analytics.py) against
institution-configured thresholds and raises alerts such as:

  * TEACHER_ABSENT    nobody was seen in the teacher area for N seconds
  * LOW_ENGAGEMENT    smoothed class engagement stayed below a threshold
  * CLASS_DROWSY      a large share of visible students look drowsy / asleep

Each alert carries rule-based instructional recommendations, and a live
recommendation list is also available while no alert is active.

How it plugs in
---------------
ai_processing.py calls, once per AI cycle (every ~0.5 s):

    evaluate_alerts(person_boxes, results, frame.shape)

and start_alert_session() / end_alert_session() when the camera session
starts / stops. camera.py calls draw_teacher_zone(frame) so the configured
zone is visible on the live video while it is being calibrated.

Design notes
------------
* An alert is raised only after the bad condition has lasted `hold` seconds
  and is cleared only after it has been good for CLEAR_SECONDS. A one-frame
  glitch can therefore neither raise nor clear an alert.
* Engagement is judged on a rolling average (smoothing_seconds), with a
  small margin (hysteresis) so a value hovering at the threshold does not
  flip-flop.
* YOLO only knows "person", not "teacher". Teacher presence is therefore
  decided by a configurable teacher ZONE (a rectangle in the camera view):
  a person whose box centre is inside the zone counts as the teacher.
* Settings are JSON files in backend/saved_alerts/ (one folder per class,
  the default class uses the folder itself). The alert HISTORY is stored in
  the SQLite database (storage.py); without a database the engine falls back
  to alerts.json, and with data_dir=None it keeps everything in memory
  (recorded-video analysis).
"""

import logging
import copy
import json
import os
import re
import smtplib
import threading
import time
import uuid
from collections import Counter, deque
from datetime import datetime
from email.message import EmailMessage

from flask import Blueprint, jsonify, request

from analytics import calculate_engagement_score
from class_id import DEFAULT_CLASS_ID, normalize_class_id
from storage import get_storage

logger = logging.getLogger(__name__)


alerts_bp = Blueprint("alerts", __name__)


# ============================================================
# CONSTANTS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("ALERTS_DATA_DIR") or os.path.join(
    BASE_DIR, "saved_alerts"
)

MAX_HISTORY = 500
CLEAR_SECONDS = 20          # how long a condition must be good to clear
HYSTERESIS_POINTS = 5       # engagement must recover this far above threshold

ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

DROWSY_STATES = ("Drowsy", "Sleeping")
NEGATIVE_EMOTIONS = ("Angry", "Fear", "Sad", "Disgust")

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}

# Which suggestions belong on which alert, so an alert only shows advice
# that is relevant to it (the full live list is shown separately).
RECOMMENDATIONS_FOR_ALERT = {
    "TEACHER_ABSENT": ("teacher-absent",),
    "LOW_ENGAGEMENT": (
        "low-engagement-activity",
        "low-engagement-pace",
        "confusion-check",
    ),
    "CLASS_DROWSY": ("stretch-break",),
}

DEFAULT_SETTINGS = {
    "enabled": True,

    # Teacher presence (needs a zone, so it is off until one is chosen)
    "teacher_check_enabled": False,
    "teacher_zone": None,               # {"x1","y1","x2","y2"} in 0..1
    "teacher_absent_seconds": 60,

    # Persistent class-wide disengagement
    "disengagement_threshold": 50,      # percent
    "disengagement_seconds": 120,

    # Drowsiness across the class
    "drowsy_share_threshold": 30,       # percent of visible students
    "drowsy_seconds": 60,

    # Student absence detection
    "students_absent_seconds": 30,

    "min_students": 2,                  # faces needed to judge the class
    "smoothing_seconds": 20,

    # Only raise alerts during scheduled lecture hours
    "schedule_enforced": False,
    "schedule": {
        "days": [0, 1, 2, 3, 4],        # Monday = 0
        "start": "09:00",
        "end": "17:00",
    },

    # Optional e-mail copy of every new alert
    "notify_email": "",
}

# key -> (min, max) for whole-number settings
INTEGER_LIMITS = {
    "teacher_absent_seconds": (10, 3600),
    "disengagement_threshold": (10, 90),
    "disengagement_seconds": (10, 3600),
    "drowsy_share_threshold": (5, 100),
    "drowsy_seconds": (10, 3600),
    "students_absent_seconds": (10, 3600),
    "min_students": (1, 200),
    "smoothing_seconds": (5, 120),
}

BOOLEAN_KEYS = ("enabled", "teacher_check_enabled", "schedule_enforced")


# ============================================================
# SMALL HELPERS
# ============================================================

def _fmt_duration(seconds):
    seconds = max(0, int(round(seconds)))
    minutes, secs = divmod(seconds, 60)

    if minutes and secs:
        return f"{minutes} min {secs} s"

    if minutes:
        return f"{minutes} min"

    return f"{secs} s"


def _mean(values):
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _atomic_write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    temp_path = path + ".tmp"

    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    os.replace(temp_path, path)


def _read_json(path, fallback):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return fallback


# ============================================================
# SETTINGS VALIDATION
# ============================================================

def _validate_zone(zone):
    if zone is None:
        return None

    if not isinstance(zone, dict):
        raise ValueError("Teacher zone must be an object with x1, y1, x2, y2.")

    try:
        x1, y1, x2, y2 = (float(zone[k]) for k in ("x1", "y1", "x2", "y2"))
    except (KeyError, TypeError, ValueError):
        raise ValueError("Teacher zone needs numeric x1, y1, x2 and y2.")

    if not all(0.0 <= v <= 1.0 for v in (x1, y1, x2, y2)):
        raise ValueError("Teacher zone values must be between 0 and 1.")

    if x2 - x1 < 0.05 or y2 - y1 < 0.05:
        raise ValueError("Teacher zone is too small.")

    return {
        "x1": round(x1, 4),
        "y1": round(y1, 4),
        "x2": round(x2, 4),
        "y2": round(y2, 4),
    }


def _validate_schedule(schedule):
    if not isinstance(schedule, dict):
        raise ValueError("Schedule must be an object.")

    days = schedule.get("days")

    if (
        not isinstance(days, list)
        or not days
        or not all(isinstance(d, int) and 0 <= d <= 6 for d in days)
    ):
        raise ValueError("Schedule needs at least one weekday (0 = Monday).")

    start = schedule.get("start", "")
    end = schedule.get("end", "")

    if not TIME_PATTERN.match(str(start)) or not TIME_PATTERN.match(str(end)):
        raise ValueError("Schedule times must look like 09:00.")

    if str(start) >= str(end):
        raise ValueError("Schedule start time must be before the end time.")

    return {
        "days": sorted(set(days)),
        "start": str(start),
        "end": str(end),
    }


def validate_settings(patch, current):
    """Return a new settings dict, or raise ValueError with a clear message."""

    if not isinstance(patch, dict):
        raise ValueError("Settings must be a JSON object.")

    merged = copy.deepcopy(current)

    for key, value in patch.items():

        if key in BOOLEAN_KEYS:

            if not isinstance(value, bool):
                raise ValueError(f"'{key}' must be true or false.")

            merged[key] = value

        elif key in INTEGER_LIMITS:

            low, high = INTEGER_LIMITS[key]

            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"'{key}' must be a number.")

            value = int(round(value))

            if not low <= value <= high:
                raise ValueError(f"'{key}' must be between {low} and {high}.")

            merged[key] = value

        elif key == "teacher_zone":
            merged[key] = _validate_zone(value)

        elif key == "schedule":
            merged[key] = _validate_schedule(value)

        elif key == "notify_email":

            value = str(value or "").strip()

            if value and not EMAIL_PATTERN.match(value):
                raise ValueError("That e-mail address does not look valid.")

            merged[key] = value

        else:
            raise ValueError(f"Unknown setting '{key}'.")

    if merged["teacher_check_enabled"] and merged["teacher_zone"] is None:
        raise ValueError(
            "Choose a teacher zone before turning on teacher-presence checks."
        )

    return merged


# ============================================================
# RECOMMENDATIONS (rule based)
# ============================================================

def _rec(rec_id, priority, title, detail, reason):
    return {
        "id": rec_id,
        "priority": priority,          # high | medium | low
        "title": title,
        "detail": detail,
        "reason": reason,
    }


def build_recommendations(
    engagement,
    drowsy_percent,
    negative_percent,
    teacher_absent_for,
    settings,
):
    """Turn the current class state into a short list of suggestions.

    These are suggestions for a human to judge, not verdicts: the signals
    behind them (expression + eye state) are only indirect evidence.
    """

    recs = []

    if teacher_absent_for:
        recs.append(_rec(
            "teacher-absent",
            "high",
            "Check on the scheduled faculty member",
            "Contact the teacher or the department coordinator, and arrange "
            "a substitute or supervision if the class is unattended.",
            f"No one was seen in the teacher area for "
            f"{_fmt_duration(teacher_absent_for)}.",
        ))

    if engagement is not None:

        threshold = settings["disengagement_threshold"]

        if engagement < threshold:
            recs.append(_rec(
                "low-engagement-activity",
                "high",
                "Switch to an interactive activity",
                "Run a quick poll, a think-pair-share, or ask a short "
                "question to bring attention back to the lesson.",
                f"Class engagement is {round(engagement)}%, below the "
                f"{threshold}% threshold.",
            ))
            recs.append(_rec(
                "low-engagement-pace",
                "medium",
                "Revisit the last concept or adjust the pace",
                "A short recap, a worked example, or a change of format "
                "(slides to board, lecture to discussion) often helps.",
                "Engagement has been low for a sustained period.",
            ))

        elif engagement < 65:
            recs.append(_rec(
                "check-in-question",
                "medium",
                "Add a check-in question",
                "Ask the class one quick question to confirm they are "
                "following before moving on.",
                f"Class engagement is {round(engagement)}%, which is "
                "moderate and slipping towards the threshold.",
            ))

        elif (
            engagement >= 75
            and (drowsy_percent or 0) < 10
            and (negative_percent or 0) < 25
        ):
            recs.append(_rec(
                "keep-going",
                "low",
                "Engagement looks healthy",
                "The current pace and format appear to be working. "
                "No action needed.",
                f"Class engagement is {round(engagement)}%.",
            ))

    # Suggest a break at 20% drowsy, or sooner if the institution set a
    # lower drowsiness alert threshold.
    break_level = min(20, settings["drowsy_share_threshold"])

    if drowsy_percent is not None and drowsy_percent >= break_level:
        recs.append(_rec(
            "stretch-break",
            "medium",
            "Offer a short stretch break",
            "A two-minute break, a change of posture, or fresh air can "
            "help when many students look tired.",
            f"{round(drowsy_percent)}% of visible students have drowsy "
            "or closed eyes.",
        ))

    if negative_percent is not None and negative_percent >= 35:
        recs.append(_rec(
            "confusion-check",
            "medium",
            "Pause and invite questions",
            "Many expressions read as confused, worried or unhappy. "
            "Ask whether the last point was clear.",
            f"{round(negative_percent)}% of detected expressions are "
            "negative (angry, fear, sad, disgust). Expression detection "
            "is approximate, so treat this as a prompt, not a conclusion.",
        ))

    priority_order = {"high": 0, "medium": 1, "low": 2}
    recs.sort(key=lambda r: priority_order[r["priority"]])

    return recs


# ============================================================
# CONDITION TIMER (hold / clear logic)
# ============================================================

class Condition:
    """Tracks one yes/no condition over time.

    update() is told whether the condition is currently:
      "bad"      the problem is happening
      "good"     it is clearly fine
      "neutral"  in the grey zone (neither raise nor clear progress)
      "unknown"  there is no data to judge (counts as fine for clearing,
                 never counts towards raising)
    and returns "raise", "clear" or None.
    """

    def __init__(self):
        self.bad_since = None
        self.good_since = None
        self.raised = False

    def update(self, state, now, hold, clear):

        if state == "bad":

            self.good_since = None

            if self.bad_since is None:
                self.bad_since = now

            if not self.raised and now - self.bad_since >= hold:
                self.raised = True
                return "raise"

        elif state in ("good", "unknown"):

            self.bad_since = None

            if self.good_since is None:
                self.good_since = now

            if self.raised and now - self.good_since >= clear:
                self.raised = False
                self.good_since = None
                return "clear"

        else:  # neutral

            self.good_since = None

            if not self.raised:
                self.bad_since = None

        return None


# ============================================================
# ENGINE
# ============================================================

ALERT_TYPES = (
    "TEACHER_ABSENT",
    "LOW_ENGAGEMENT",
    "CLASS_DROWSY",
    "STUDENTS_ABSENT",
)


class AlertEngine:

    def __init__(
        self,
        data_dir=DATA_DIR,
        notifier=None,
        store=None,
        class_id=DEFAULT_CLASS_ID,
        settings=None,
    ):
        """
        data_dir  folder for settings.json (and alerts.json when there is no
                  store). None = keep everything in memory.
        store     a storage.Storage: alert history goes to SQLite.
        class_id  the class / room this engine watches.
        settings  optional settings patch (used when data_dir is None).
        """

        self.data_dir = data_dir
        self.store = store
        self.class_id = class_id
        self.settings_path = (
            os.path.join(data_dir, "settings.json") if data_dir else None
        )
        self.history_path = (
            os.path.join(data_dir, "alerts.json") if data_dir else None
        )

        self.lock = threading.RLock()
        self.notifier = notifier or self._default_notifier

        self.settings = self._load_settings(settings)
        self.history = self._load_history()     # oldest first
        self.active = {}                        # alert type -> alert dict

        self.session_active = False
        self.session_id = None
        self._reset_runtime()

    # --------------------------------------------------------
    # persistence
    # --------------------------------------------------------

    def _load_settings(self, patch=None):

        if self.settings_path is None:
            return validate_settings(patch or {}, DEFAULT_SETTINGS)

        stored = _read_json(self.settings_path, {})

        try:
            return validate_settings(stored, DEFAULT_SETTINGS)
        except ValueError:
            return copy.deepcopy(DEFAULT_SETTINGS)

    def _load_history(self):

        if self.store is not None:
            self._import_legacy_history()
            stored = self.store.load_alerts(self.class_id, MAX_HISTORY)
        elif self.history_path is not None:
            stored = _read_json(self.history_path, {}).get("alerts", [])
        else:
            stored = []

        history = []

        for alert in stored:

            if not isinstance(alert, dict) or "id" not in alert:
                continue

            # An alert still "active" in the file means the server stopped
            # while it was open; close it so it does not stay stuck.
            if alert.get("status") == "active":
                alert["status"] = "resolved"
                alert["resolved_at"] = alert.get("resolved_at") or time.time()
                alert["resolved_reason"] = "server_restart"
                self._persist_alert(alert, history_loading=True)

            history.append(alert)

        return history[-MAX_HISTORY:]

    def _import_legacy_history(self):
        """Move an old alerts.json into the database, once."""

        if (
            self.history_path is None
            or not os.path.exists(self.history_path)
            or self.store.count_alerts(self.class_id) > 0
        ):
            return

        legacy = _read_json(self.history_path, {}).get("alerts", [])
        imported = self.store.import_legacy_alerts(legacy, self.class_id)

        if imported:
            logger.info(
                "Imported %d legacy alert(s) of class %s into SQLite",
                imported, self.class_id,
            )

    def _save_history(self):
        """JSON fallback (only used when there is no database)."""

        if self.store is None and self.history_path is not None:
            _atomic_write_json(self.history_path, {"alerts": self.history})

    def _persist_alert(self, alert, history_loading=False):
        """Write one new / changed alert to the database (or JSON)."""

        if self.store is not None:
            self.store.upsert_alert(alert, self.class_id)
        elif not history_loading:
            self._save_history()

    def _save_settings(self):

        if self.settings_path is not None:
            _atomic_write_json(self.settings_path, self.settings)

    # --------------------------------------------------------
    # runtime state
    # --------------------------------------------------------

    def _reset_runtime(self):

        self.conditions = {name: Condition() for name in ALERT_TYPES}
        self.samples = deque()      # (time, engagement, drowsy_share, n, emotions)
        self.session_started_at = None
        self.status = self._empty_status()

    def _empty_status(self):

        return {
            "teacher_monitored": False,
            "teacher_present": None,
            "teacher_absent_for": 0,
            "persons_in_view": 0,
            "students_in_view": 0,
            "engagement": None,
            "drowsy_percent": None,
            "negative_percent": None,
            "emotion_mix": {},
            "in_schedule": True,
            "monitoring": False,
            "last_update": None,
        }

    # --------------------------------------------------------
    # session lifecycle
    # --------------------------------------------------------

    def start_session(self, now=None, session_id=None):

        with self.lock:
            self._reset_runtime()
            self.session_active = True
            self.session_id = session_id
            self.session_started_at = time.time() if now is None else now

    def end_session(self, now=None):

        now = time.time() if now is None else now

        with self.lock:
            self._resolve_all("session_ended", now)
            self.session_active = False
            self._reset_runtime()

    # --------------------------------------------------------
    # schedule
    # --------------------------------------------------------

    def _within_schedule(self, now):

        settings = self.settings

        if not settings["schedule_enforced"]:
            return True

        moment = datetime.fromtimestamp(now)
        schedule = settings["schedule"]

        if moment.weekday() not in schedule["days"]:
            return False

        return schedule["start"] <= moment.strftime("%H:%M") < schedule["end"]

    # --------------------------------------------------------
    # evaluation (called every AI cycle)
    # --------------------------------------------------------

    @staticmethod
    def _teacher_in_zone(person_boxes, frame_shape, zone):

        height, width = frame_shape[0], frame_shape[1]

        if not height or not width:
            return False

        left, right = zone["x1"] * width, zone["x2"] * width
        top, bottom = zone["y1"] * height, zone["y2"] * height

        for x1, y1, x2, y2 in person_boxes:

            centre_x = (x1 + x2) / 2.0
            centre_y = (y1 + y2) / 2.0

            if left <= centre_x <= right and top <= centre_y <= bottom:
                return True

        return False

    def evaluate(self, person_boxes, results, frame_shape, now=None):
        """Check all rules for one AI cycle. Returns the events it caused,
        e.g. [("raise", "TEACHER_ABSENT")] (handy for tests)."""

        now = time.time() if now is None else now
        events = []

        with self.lock:

            if not self.session_active:
                return events

            settings = self.settings
            in_schedule = self._within_schedule(now)

            status = self.status
            status["in_schedule"] = in_schedule
            status["last_update"] = now
            status["persons_in_view"] = len(person_boxes)
            status["students_in_view"] = len(results)

            if not settings["enabled"] or not in_schedule:
                status["monitoring"] = False
                self._resolve_all(
                    "alerts_disabled" if not settings["enabled"]
                    else "outside_schedule",
                    now,
                )
                for condition in self.conditions.values():
                    condition.bad_since = None
                    condition.good_since = None
                return events

            status["monitoring"] = True

            # ---------------- teacher presence ----------------

            zone = settings["teacher_zone"]
            monitored = bool(settings["teacher_check_enabled"] and zone)

            status["teacher_monitored"] = monitored

            if monitored:
                present = self._teacher_in_zone(person_boxes, frame_shape, zone)
                status["teacher_present"] = present
                teacher_state = "good" if present else "bad"
            else:
                status["teacher_present"] = None
                teacher_state = "unknown"

            condition = self.conditions["TEACHER_ABSENT"]

            outcome = condition.update(
                teacher_state, now,
                hold=settings["teacher_absent_seconds"],
                clear=5,
            )

            status["teacher_absent_for"] = (
                now - condition.bad_since
                if condition.bad_since is not None else 0
            )

            if outcome:
                events.append(self._apply(outcome, "TEACHER_ABSENT", now))


            # ---------------- student absence ----------------

            students_absent = len(results) == 0

            condition = self.conditions["STUDENTS_ABSENT"]

            outcome = condition.update(
                "bad" if students_absent else "good",
                now,
                hold=settings["students_absent_seconds"],
                clear=5,
            )

            if outcome:
                events.append(
                    self._apply(outcome, "STUDENTS_ABSENT", now)
                )

            # ---------------- class metrics ----------------

            enough_faces = len(results) >= settings["min_students"]

            if enough_faces:

                emotions = Counter(
                    r.get("emotion", "Neutral") for r in results
                )

                self.samples.append((
                    now,
                    _mean(calculate_engagement_score(r) for r in results),
                    sum(
                        1 for r in results
                        if r.get("eye_state") in DROWSY_STATES
                    ) / len(results),
                    len(results),
                    emotions,
                ))

            cutoff = now - settings["smoothing_seconds"]

            while self.samples and self.samples[0][0] < cutoff:
                self.samples.popleft()

            if self.samples:

                engagement = _mean(s[1] for s in self.samples)
                drowsy_percent = _mean(s[2] for s in self.samples) * 100

                mix = Counter()

                for sample in self.samples:
                    mix.update(sample[4])

                total = sum(mix.values()) or 1

                negative_percent = (
                    sum(mix[e] for e in NEGATIVE_EMOTIONS) / total * 100
                )

                status["engagement"] = round(engagement, 1)
                status["drowsy_percent"] = round(drowsy_percent, 1)
                status["negative_percent"] = round(negative_percent, 1)
                status["emotion_mix"] = {
                    name: round(count / total * 100)
                    for name, count in mix.items()
                }

            else:
                engagement = drowsy_percent = negative_percent = None
                status["engagement"] = None
                status["drowsy_percent"] = None
                status["negative_percent"] = None
                status["emotion_mix"] = {}

            # ---------------- low engagement ----------------

            threshold = settings["disengagement_threshold"]

            if not enough_faces or engagement is None:
                state = "unknown"
            elif engagement < threshold:
                state = "bad"
            elif engagement >= threshold + HYSTERESIS_POINTS:
                state = "good"
            else:
                state = "neutral"

            outcome = self.conditions["LOW_ENGAGEMENT"].update(
                state, now,
                hold=settings["disengagement_seconds"],
                clear=CLEAR_SECONDS,
            )

            if outcome:
                events.append(self._apply(outcome, "LOW_ENGAGEMENT", now))

            # ---------------- drowsy class ----------------

            drowsy_limit = settings["drowsy_share_threshold"]

            if not enough_faces or drowsy_percent is None:
                state = "unknown"
            elif drowsy_percent >= drowsy_limit:
                state = "bad"
            elif drowsy_percent < drowsy_limit * 0.7:
                state = "good"
            else:
                state = "neutral"

            outcome = self.conditions["CLASS_DROWSY"].update(
                state, now,
                hold=settings["drowsy_seconds"],
                clear=CLEAR_SECONDS,
            )

            if outcome:
                events.append(self._apply(outcome, "CLASS_DROWSY", now))

        return events

    # --------------------------------------------------------
    # raising / resolving alerts
    # --------------------------------------------------------

    def _apply(self, outcome, alert_type, now):

        if outcome == "raise":
            self._raise(alert_type, now)
        else:
            self._resolve(alert_type, now, "recovered")

        return (outcome, alert_type)

    def _live_recommendations(self):

        status = self.status

        return build_recommendations(
            status["engagement"],
            status["drowsy_percent"],
            status["negative_percent"],
            status["teacher_absent_for"]
            if self.conditions["TEACHER_ABSENT"].raised else 0,
            self.settings,
        )

    def _raise(self, alert_type, now):

        settings = self.settings
        status = self.status

        if alert_type == "TEACHER_ABSENT":
            seconds = settings["teacher_absent_seconds"]
            severity = "critical"
            title = "Teacher not detected"
            message = (
                f"No one was detected in the teacher area for "
                f"{_fmt_duration(seconds)} while the class session was "
                f"running."
            )
            details = {"seconds": seconds}

        elif alert_type == "LOW_ENGAGEMENT":
            seconds = settings["disengagement_seconds"]
            severity = "warning"
            title = "Sustained low class engagement"
            message = (
                f"Class engagement stayed below "
                f"{settings['disengagement_threshold']}% for "
                f"{_fmt_duration(seconds)} (now about "
                f"{round(status['engagement'] or 0)}%)."
            )
            details = {
                "seconds": seconds,
                "engagement": status["engagement"],
                "threshold": settings["disengagement_threshold"],
            }

        elif alert_type == "STUDENTS_ABSENT":

            seconds = settings["students_absent_seconds"]
            severity = "critical"

            title = "No Students Detected"

            message = (
                f"No students were detected in the classroom "
                f"for {_fmt_duration(seconds)}."
            )

            details = {
                "seconds": seconds,
                "students_detected": 0,
            }

        else:  # CLASS_DROWSY
            seconds = settings["drowsy_seconds"]
            severity = "warning"
            title = "Many students look drowsy"
            message = (
                f"About {round(status['drowsy_percent'] or 0)}% of visible "
                f"students had drowsy or closed eyes for "
                f"{_fmt_duration(seconds)}."
            )
            details = {
                "seconds": seconds,
                "drowsy_percent": status["drowsy_percent"],
                "threshold": settings["drowsy_share_threshold"],
            }

        wanted = RECOMMENDATIONS_FOR_ALERT.get(alert_type, ())

        recommendations = [
            rec for rec in self._live_recommendations()
            if rec["id"] in wanted
        ]

        alert = {
            "id": uuid.uuid4().hex,
            "type": alert_type,
            "severity": severity,
            "title": title,
            "message": message,
            "details": details,
            "recommendations": recommendations,
            "status": "active",
            "started_at": now,
            "resolved_at": None,
            "resolved_reason": None,
            "acknowledged": False,
            "acknowledged_at": None,
            "session_started_at": self.session_started_at,
            "session_id": self.session_id,
            "class_id": self.class_id,
        }

        self.active[alert_type] = alert
        self._store(alert)
        self.notifier(copy.deepcopy(alert), settings["notify_email"])

        return alert

    def _store(self, alert):

        self.history.append(alert)
        self.history = self.history[-MAX_HISTORY:]
        self._persist_alert(alert)

    def _resolve(self, alert_type, now, reason):

        alert = self.active.pop(alert_type, None)

        if alert is None:
            return

        alert["status"] = "resolved"
        alert["resolved_at"] = now
        alert["resolved_reason"] = reason

        self._persist_alert(alert)

    def _resolve_all(self, reason, now):

        for alert_type in list(self.active):
            self._resolve(alert_type, now, reason)

        for condition in self.conditions.values():
            condition.raised = False

    # --------------------------------------------------------
    # public read / write API
    # --------------------------------------------------------

    def get_settings(self):

        with self.lock:
            return copy.deepcopy(self.settings)

    def update_settings(self, patch):

        with self.lock:
            self.settings = validate_settings(patch, self.settings)
            self._save_settings()
            return copy.deepcopy(self.settings)

    def get_alerts(self, limit=100):

        with self.lock:

            active = sorted(
                self.active.values(),
                key=lambda a: (SEVERITY_ORDER[a["severity"]], -a["started_at"]),
            )

            resolved = [
                a for a in reversed(self.history) if a["status"] != "active"
            ][:limit]

            return copy.deepcopy({"active": active, "history": resolved})

    def get_status(self):

        with self.lock:

            status = copy.deepcopy(self.status)

            status["session_active"] = self.session_active
            status["session_started_at"] = self.session_started_at
            status["active_alert_count"] = len(self.active)
            status["unacknowledged_count"] = sum(
                1 for a in self.active.values() if not a["acknowledged"]
            )
            status["recommendations"] = (
                self._live_recommendations() if self.session_active else []
            )

            return status

    def acknowledge(self, alert_id, now=None):

        now = time.time() if now is None else now

        with self.lock:

            for alert in self.history:

                if alert["id"] != alert_id:
                    continue

                alert["acknowledged"] = True
                alert["acknowledged_at"] = now

                # A manual test alert has no condition behind it, so
                # acknowledging it also closes it.
                if alert["type"] == "TEST" and alert["status"] == "active":
                    self._resolve("TEST", now, "acknowledged")
                else:
                    self._persist_alert(alert)

                return True

        return False

    def delete(self, alert_id):
        """Delete a resolved alert. Returns "ok", "active" or "missing"."""

        with self.lock:

            for index, alert in enumerate(self.history):

                if alert["id"] != alert_id:
                    continue

                if alert["status"] == "active":
                    return "active"

                del self.history[index]

                if self.store is not None:
                    self.store.delete_alert(alert_id)
                else:
                    self._save_history()

                return "ok"

        return "missing"

    def clear_resolved(self):

        with self.lock:

            before = len(self.history)
            self.history = [a for a in self.history if a["status"] == "active"]

            if self.store is not None:
                self.store.delete_resolved_alerts(self.class_id)
            else:
                self._save_history()

            return before - len(self.history)

    def send_test_alert(self, now=None):
        """Raise a harmless alert so the feed and e-mail can be checked
        without waiting for a real condition."""

        now = time.time() if now is None else now

        with self.lock:

            if "TEST" in self.active:
                self._resolve("TEST", now, "replaced")

            alert = {
                "id": uuid.uuid4().hex,
                "type": "TEST",
                "severity": "info",
                "title": "Test alert",
                "message": "This is a test alert. Acknowledge it to close it.",
                "details": {},
                "recommendations": [],
                "status": "active",
                "started_at": now,
                "resolved_at": None,
                "resolved_reason": None,
                "acknowledged": False,
                "acknowledged_at": None,
                "session_started_at": self.session_started_at,
                "session_id": self.session_id,
                "class_id": self.class_id,
            }

            self.active["TEST"] = alert
            self._store(alert)
            self.notifier(copy.deepcopy(alert), self.settings["notify_email"])

            return copy.deepcopy(alert)

    # --------------------------------------------------------
    # notifications
    # --------------------------------------------------------

    @staticmethod
    def _default_notifier(alert, email):

        logger.warning("[ALERT:%s] %s: %s", alert["severity"].upper(), alert["title"], alert["message"])

        if email:
            threading.Thread(
                target=_send_email, args=(email, alert), daemon=True
            ).start()


def _send_email(to_address, alert):
    """E-mail one alert. Does nothing unless SMTP is configured through
    environment variables (ALERT_SMTP_HOST, ALERT_SMTP_PORT,
    ALERT_SMTP_USER, ALERT_SMTP_PASSWORD, ALERT_FROM)."""

    host = os.environ.get("ALERT_SMTP_HOST")

    if not host:
        logger.info("Alert e-mail skipped: ALERT_SMTP_HOST is not set.")
        return

    try:
        port = int(os.environ.get("ALERT_SMTP_PORT", "587"))
        user = os.environ.get("ALERT_SMTP_USER", "")
        password = os.environ.get("ALERT_SMTP_PASSWORD", "")
        sender = os.environ.get("ALERT_FROM", user or "alerts@localhost")

        lines = [alert["message"], ""]

        if alert["recommendations"]:
            lines.append("Suggested actions:")
            lines += [
                f"- {r['title']}: {r['detail']}"
                for r in alert["recommendations"]
            ]

        message = EmailMessage()
        message["Subject"] = f"[ClassroomAI] {alert['title']}"
        message["From"] = sender
        message["To"] = to_address
        message.set_content("\n".join(lines))

        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()

            if user:
                server.login(user, password)

            server.send_message(message)

    except Exception as error:
        logger.error("Alert e-mail failed: %s", error)


# ============================================================
# MODULE-LEVEL ENGINE + FUNCTIONS USED BY OTHER MODULES
# ============================================================

_engines = {}
_engines_lock = threading.RLock()


def get_alert_engine(class_id=DEFAULT_CLASS_ID):
    """The AlertEngine of a class (created on first use). Every class has
    its own thresholds, runtime state and alert history."""

    with _engines_lock:

        found = _engines.get(class_id)

        if found is None:

            data_dir = (
                DATA_DIR if class_id == DEFAULT_CLASS_ID
                else os.path.join(DATA_DIR, "classes", class_id)
            )

            found = _engines[class_id] = AlertEngine(
                data_dir=data_dir,
                store=get_storage(),
                class_id=class_id,
            )

        return found


def start_alert_session(class_id=DEFAULT_CLASS_ID, session_id=None):
    get_alert_engine(class_id).start_session(session_id=session_id)


def end_alert_session(class_id=DEFAULT_CLASS_ID):
    get_alert_engine(class_id).end_session()


def evaluate_alerts(
    person_boxes, results, frame_shape, class_id=DEFAULT_CLASS_ID, now=None
):
    return get_alert_engine(class_id).evaluate(
        person_boxes, results, frame_shape, now=now
    )


def draw_teacher_zone(frame, class_id=DEFAULT_CLASS_ID):
    """Outline the teacher zone on a live frame (used while calibrating)."""

    settings = get_alert_engine(class_id).get_settings()

    if not settings["teacher_check_enabled"] or not settings["teacher_zone"]:
        return

    import cv2

    zone = settings["teacher_zone"]
    height, width = frame.shape[:2]

    top_left = (int(zone["x1"] * width), int(zone["y1"] * height))
    bottom_right = (int(zone["x2"] * width), int(zone["y2"] * height))

    cv2.rectangle(frame, top_left, bottom_right, (0, 165, 255), 2)
    cv2.putText(
        frame,
        "Teacher zone",
        (top_left[0] + 6, top_left[1] + 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 165, 255),
        2,
    )


# ============================================================
# ROUTES
# ============================================================

def _engine_for_request():
    """The AlertEngine for ?class_id=... (default class when omitted)."""

    return get_alert_engine(normalize_class_id(request.args.get("class_id")))


@alerts_bp.errorhandler(ValueError)
def _bad_class_id(error):
    return jsonify({"success": False, "message": str(error)}), 400


@alerts_bp.route("/alerts", methods=["GET"])
def list_alerts():

    data = _engine_for_request().get_alerts()

    return jsonify({"success": True, **data})


@alerts_bp.route("/alerts/status", methods=["GET"])
def alerts_status():

    return jsonify({"success": True, **_engine_for_request().get_status()})


@alerts_bp.route("/alerts/settings", methods=["GET"])
def get_alert_settings():

    return jsonify({"success": True, "settings": _engine_for_request().get_settings()})


@alerts_bp.route("/alerts/settings", methods=["PUT", "POST"])
def save_alert_settings():

    patch = request.get_json(silent=True)

    try:
        settings = _engine_for_request().update_settings(patch)
    except ValueError as error:
        return jsonify({"success": False, "message": str(error)}), 400

    return jsonify({"success": True, "settings": settings})


@alerts_bp.route("/alerts/<alert_id>/acknowledge", methods=["POST"])
def acknowledge_alert(alert_id):

    if not ID_PATTERN.match(alert_id) or not _engine_for_request().acknowledge(alert_id):
        return jsonify({"success": False, "message": "Alert not found"}), 404

    return jsonify({"success": True})


@alerts_bp.route("/alerts/<alert_id>", methods=["DELETE"])
def delete_alert(alert_id):

    if not ID_PATTERN.match(alert_id):
        return jsonify({"success": False, "message": "Alert not found"}), 404

    outcome = _engine_for_request().delete(alert_id)

    if outcome == "active":
        return jsonify({
            "success": False,
            "message": "An active alert cannot be deleted. "
                       "Acknowledge it and wait for it to resolve.",
        }), 409

    if outcome == "missing":
        return jsonify({"success": False, "message": "Alert not found"}), 404

    return jsonify({"success": True})


@alerts_bp.route("/alerts/clear-history", methods=["POST"])
def clear_alert_history():

    return jsonify({"success": True, "removed": _engine_for_request().clear_resolved()})


@alerts_bp.route("/alerts/test", methods=["POST"])
def create_test_alert():

    return jsonify({"success": True, "alert": _engine_for_request().send_test_alert()})


logger.debug("Alerts module loaded successfully!")