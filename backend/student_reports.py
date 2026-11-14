"""
Per-student tracking and reports.

Takes the detections the existing AI pipeline already produces (a face box
plus emotion / eye state) and keeps one running record per student, so a
person who shows up in many frames is ONE student, not many detections.

Scoring is NOT re-implemented here: engagement and attention come from
analytics.py (calculate_engagement_score / calculate_attention_score), so
per-student numbers use the same formulas as the Analytics page.

There is no face recognition in this project, so a "student" is a tracked
person (Student 1, 2, 3 ...). The id comes from ByteTrack (person_tracker.py):
every YOLO person gets a stable `person_id`, and this registry maps each
person_id to ONE student for the whole session. If ByteTrack is not
available (person_id is None) the old box-overlap matching is used instead.
There is deliberately no attendance concept in these reports.
"""

import threading
import time

from analytics import (
    calculate_attention_score,
    calculate_engagement_score,
)


# ============================================================
# SETTINGS
# ============================================================

# If a student has not been seen for this long (in the clock the caller
# passes as `now`), they may only be re-matched at (nearly) the same place.
PRESENT_TIMEOUT = 3.0

# A NEW ByteTrack id may be linked back to an absent student by clothes
# colour (not only by seat) when that student was lost at most this long ago.
RELINK_WINDOW = 30.0

# Histogram intersection (0..1) needed for that. Raise it if different
# students get merged (e.g. same uniform), lower it if one student still
# splits in two.
APPEARANCE_RELINK_MIN = 0.70


# ============================================================
# LEVELS
# ============================================================

def engagement_level(score):

    if score >= 75:
        return "Engaged"

    if score >= 50:
        return "Moderate"

    return "Low"


def attention_level(score, has_data):

    if not has_data:
        return "Unknown"

    if score >= 75:
        return "High"

    if score >= 50:
        return "Medium"

    return "Low"


def eye_status_label(eye_state):

    if eye_state == "Sleeping":
        return "Sleeping"

    if eye_state == "Drowsy":
        return "Drowsy"

    if eye_state in ("Open", "Blink", "Close"):
        return "Alert"

    return "Unknown"


# ============================================================
# BOX MATCHING  (x, y, w, h)
# ============================================================

def box_iou(a, b):

    ax, ay, aw, ah = a
    bx, by, bw, bh = b

    inter_w = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    inter_h = max(0, min(ay + ah, by + bh) - max(ay, by))

    inter = inter_w * inter_h

    union = max(0, aw) * max(0, ah) + max(0, bw) * max(0, bh) - inter

    return inter / union if union > 0 else 0.0


def _normalized_center_distance(a, b):

    ax, ay, aw, ah = a
    bx, by, bw, bh = b

    dx = (ax + aw / 2.0) - (bx + bw / 2.0)
    dy = (ay + ah / 2.0) - (by + bh / 2.0)

    distance = (dx * dx + dy * dy) ** 0.5

    scale = max(1.0, (aw + ah + bw + bh) / 4.0)

    return distance / scale


def _match_score(box, previous_box, strict):
    """
    How likely `box` is the same person as `previous_box` (None = no match).

    strict=True is used for students who have not been seen recently: they
    only match if they reappear in (nearly) the same place, so a new person
    does not inherit someone else's history.
    """

    iou = box_iou(box, previous_box)
    distance = _normalized_center_distance(box, previous_box)

    area_a = max(1, box[2] * box[3])
    area_b = max(1, previous_box[2] * previous_box[3])
    area_ratio = min(area_a, area_b) / max(area_a, area_b)

    if iou >= (0.35 if strict else 0.20):

        return (
            0.70 * iou
            + 0.20 * max(0.0, 1.0 - distance / 2.5)
            + 0.10 * area_ratio
        )

    if not strict and distance <= 1.8 and area_ratio >= 0.45:

        return (
            0.70 * max(0.0, 1.0 - distance / 1.8)
            + 0.30 * area_ratio
        )

    return None


def appearance_similarity(a, b):
    """Histogram intersection of two colour fingerprints (0..1)."""

    if not a or not b or len(a) != len(b):
        return 0.0

    return float(sum(min(x, y) for x, y in zip(a, b)))


# ============================================================
# STUDENT RECORD
# ============================================================

def _new_record(student_id, box, now):

    return {
        "id": student_id,
        "name": f"Student {student_id}",

        "last_seen": now,
        "box": box,
        "appearance": None,

        "samples": 0,

        "emotion_counts": {},
        "eye_counts": {},

        "engagement_sum": 0.0,
        "attention_sum": 0.0,
        "current_engagement": 0,

        "current_emotion": "Unknown",
        "current_eye_state": "Unknown",

        "previous_eye_state": "Unknown",
        "drowsy_events": 0,
        "sleeping_events": 0,

        # URL is served by Flask; no image bytes are stored in SQLite.
        "photo_url": None,
        "photo_quality": 0,
    }


def _apply_sample(rec, face):
    """Add one observation (emotion + eye state) to a student record."""

    rec["samples"] += 1

    emotion = face.get("emotion", "Unknown")
    eye_state = face.get("eye_state", "Unknown")

    rec["current_emotion"] = emotion
    rec["current_eye_state"] = eye_state

    if emotion and emotion != "Unknown":

        rec["emotion_counts"][emotion] = (
            rec["emotion_counts"].get(emotion, 0) + 1
        )

    if eye_state and eye_state != "Unknown":

        rec["eye_counts"][eye_state] = (
            rec["eye_counts"].get(eye_state, 0) + 1
        )

    # Count each drowsy / sleeping episode once (on entry).
    previous = rec["previous_eye_state"]

    if eye_state == "Drowsy" and previous not in ("Drowsy", "Sleeping"):
        rec["drowsy_events"] += 1

    if eye_state == "Sleeping" and previous != "Sleeping":
        rec["sleeping_events"] += 1

    rec["previous_eye_state"] = eye_state

    engagement = calculate_engagement_score(face)

    rec["engagement_sum"] += engagement
    rec["attention_sum"] += calculate_attention_score(face)
    rec["current_engagement"] = engagement


def _percent(part, whole):

    return round(100.0 * part / whole, 1) if whole else 0.0


# ============================================================
# REGISTRY
# ============================================================

class StudentRegistry:
    """
    Keeps one record per tracked student.

    `now` is whatever clock the caller uses; recorded-video analysis passes
    video timestamps in seconds.
    """

    def __init__(self, present_timeout=PRESENT_TIMEOUT):

        self.present_timeout = present_timeout

        self._lock = threading.Lock()

        self._students = {}
        self._next_id = 1
        self._session_start = None

        # ByteTrack person_id -> student id
        self._person_to_student = {}

    # --------------------------------------------------------

    def reset(self, now=None):

        with self._lock:

            self._students.clear()
            self._person_to_student.clear()
            self._next_id = 1
            self._session_start = now if now is not None else time.time()

    # --------------------------------------------------------

    def update(
        self, detections, now=None, face_hook=None, person_ids=None
    ):
        """
        detections: list of ((x, y, w, h), face_dict)
                    face_dict has at least emotion and eye_state.
        face_hook:  optional callable(student_id, face_dict, now) that may
                    adjust the face dict (e.g. turn a raw eye reading into
                    Blink / Drowsy / Sleeping on the video clock) before it
                    is recorded.

        person_ids: optional ByteTrack person id of every detection (same
                    order). None / a None entry = not tracked: that
                    detection is matched by box overlap like before.

        Returns the student id of every detection, in order.
        """

        if now is None:
            now = time.time()

        if person_ids is None:
            person_ids = [None] * len(detections)

        with self._lock:

            if self._session_start is None:
                self._session_start = now

            assigned = {}
            used_students = set()

            # ---- 1. ByteTrack: same person_id = same student ----------

            for det_index, person_id in enumerate(person_ids):

                if person_id is None:
                    continue

                student_id = self._person_to_student.get(person_id)

                if student_id is None or student_id in used_students:
                    continue

                assigned[det_index] = student_id
                used_students.add(student_id)

            # ---- 2. the rest: match to known students by box ----------
            #
            # * detections WITHOUT a person_id: old matching.
            # * a NEW person_id: ByteTrack lost the person and gave a
            #   fresh id. Re-link to a student who is absent right now:
            #   by seat (strict box match) or, if the student was lost
            #   only a short while ago, by clothes colour.

            candidates = []

            for det_index, (box, _face) in enumerate(detections):

                if det_index in assigned:
                    continue

                tracked = person_ids[det_index] is not None
                appearance = detections[det_index][1].get("appearance")

                for student_id, rec in self._students.items():

                    if student_id in used_students:
                        continue

                    recently_seen = (
                        (now - rec["last_seen"]) <= self.present_timeout
                    )

                    score = _match_score(
                        box,
                        rec["box"],
                        strict=tracked or not recently_seen
                    )

                    # New ByteTrack id, student gone only a short while:
                    # same clothes colour = same student, even if the
                    # person moved to another place.
                    if tracked and (now - rec["last_seen"]) <= RELINK_WINDOW:

                        similarity = appearance_similarity(
                            appearance, rec.get("appearance")
                        )

                        if similarity >= APPEARANCE_RELINK_MIN:
                            score = max(score or 0.0, 0.5 * similarity)

                    if score is not None:
                        candidates.append((score, det_index, student_id))

            candidates.sort(reverse=True)

            for _score, det_index, student_id in candidates:

                if det_index in assigned or student_id in used_students:
                    continue

                assigned[det_index] = student_id
                used_students.add(student_id)

            # ---- apply each detection ---------------------------------

            result_ids = []

            for det_index, (box, face) in enumerate(detections):

                student_id = assigned.get(det_index)

                if student_id is None:

                    student_id = self._next_id
                    self._next_id += 1

                    self._students[student_id] = _new_record(
                        student_id, box, now
                    )

                rec = self._students[student_id]

                # Remember: this ByteTrack id belongs to this student.
                person_id = person_ids[det_index]

                if person_id is not None:

                    for old_pid in [
                        pid for pid, sid in self._person_to_student.items()
                        if sid == student_id and pid != person_id
                    ]:
                        del self._person_to_student[old_pid]

                    self._person_to_student[person_id] = student_id

                rec["box"] = box
                rec["last_seen"] = now
                result_ids.append(student_id)

                # running average of the clothes colour fingerprint
                appearance = face.get("appearance")

                if appearance:
                    old = rec.get("appearance")
                    rec["appearance"] = (
                        list(appearance)
                        if not old or len(old) != len(appearance)
                        else [0.9 * o + 0.1 * n for o, n in zip(old, appearance)]
                    )

                if face_hook is not None:
                    face_hook(student_id, face, now)

                _apply_sample(rec, face)

            return result_ids

    # --------------------------------------------------------

    def rename(self, student_id, name):

        with self._lock:

            rec = self._students.get(student_id)

            if rec is None:
                return False

            rec["name"] = name
            return True

    # --------------------------------------------------------

    def photo_quality(self, student_id):
        """Return the quality score of the currently stored student photo."""

        with self._lock:
            rec = self._students.get(student_id)
            return rec.get("photo_quality", 0) if rec else 0

    def set_photo(self, student_id, photo_url, quality):
        """Keep only the best acceptable snapshot for this tracked student."""

        with self._lock:
            rec = self._students.get(student_id)
            if rec is None or quality <= rec.get("photo_quality", 0):
                return False

            rec["photo_url"] = photo_url
            rec["photo_quality"] = int(quality)
            return True

    # --------------------------------------------------------

    def _build_report(self, rec):

        # ---- emotion ------------------------------------------------

        emotion_total = sum(rec["emotion_counts"].values())

        distribution = sorted(
            (
                {
                    "emotion": name,
                    "percent": _percent(count, emotion_total)
                }
                for name, count in rec["emotion_counts"].items()
            ),
            key=lambda item: item["percent"],
            reverse=True
        )

        dominant_emotion = (
            distribution[0]["emotion"] if distribution else "Unknown"
        )

        # ---- eyes ---------------------------------------------------

        eye_counts = rec["eye_counts"]
        eye_total = sum(eye_counts.values())

        # ---- attention / engagement (analytics.py scores) -----------

        samples = rec["samples"]

        attention = round(rec["attention_sum"] / samples) if samples else 0
        overall = round(rec["engagement_sum"] / samples) if samples else 0

        return {

            "student_id": rec["id"],
            "name": rec["name"],
            "photo_url": rec.get("photo_url"),

            # Live presence is not tracked; None = "summary of a recording".
            "in_view": None,

            "emotion": {
                "current": rec["current_emotion"],
                "dominant": dominant_emotion,
                "distribution": distribution,
            },

            "attention": {
                "percent": attention,
                "level": attention_level(attention, samples > 0),
            },

            "eyes": {
                "current": rec["current_eye_state"],
                "status": eye_status_label(rec["current_eye_state"]),
                "drowsy_percent": _percent(
                    eye_counts.get("Drowsy", 0), eye_total
                ),
                "sleeping_percent": _percent(
                    eye_counts.get("Sleeping", 0), eye_total
                ),
                "drowsy_events": rec["drowsy_events"],
                "sleeping_events": rec["sleeping_events"],
                "counts": dict(eye_counts),
            },

            "engagement": {
                "current": rec["current_engagement"],
                "overall_percent": overall,
                "level": engagement_level(overall) if samples else "Unknown",
            },

            "samples": samples,
            "face_samples": samples,
            "face_visibility_percent": 100.0 if samples else 0.0,
        }

    # --------------------------------------------------------

    def build_reports(self, now=None, min_samples=0, min_photo_quality=0):
        """
        Full report for every student.

        min_samples drops "ghost" tracks that were seen too few times to be
        a real person.

        min_photo_quality drops tracks whose best photo is below this score
        (0 = keep everyone). Recorded video uses it to remove detections
        that never showed a confirmed face (walls, posters, ...).
        """

        if now is None:
            now = time.time()

        with self._lock:

            session_seconds = (
                max(0.0, now - self._session_start)
                if self._session_start is not None
                else 0.0
            )

            reports = [
                self._build_report(rec)
                for _sid, rec in sorted(self._students.items())
                if rec["samples"] >= min_samples
                and rec.get("photo_quality", 0) >= min_photo_quality
            ]

        return {

            "success": True,

            "session_seconds": round(session_seconds, 1),

            "students_total": len(reports),

            "class_average_engagement": (
                round(
                    sum(r["engagement"]["overall_percent"] for r in reports)
                    / len(reports)
                )
                if reports
                else 0
            ),

            "students": reports,
        }