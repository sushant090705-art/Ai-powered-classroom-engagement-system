"""
Per-student reports for the live classroom session.

This module is ADDITIVE. It does not touch YOLO, emotion detection or eye
tracking. It only *consumes* what app.py's AI loop already produces:

  * the YOLO person boxes of the latest frame, and
  * the per-face results (emotion, eye state, confidences).

From those it keeps a running record for every student seen during the
current camera session and exposes it through:

  GET  /students/report            -> full report for every detected student
  POST /students/<id>/rename       -> give a student a real name
  POST /students/reset             -> start a fresh session

Identity note
-------------
There is no face recognition in this project, so a "student" is a tracked
person: the same seat/position keeps the same ID (Student 1, Student 2, ...)
for the whole session, including after a short absence. Use the rename
endpoint (or the pencil icon in the dashboard) to attach a real name.
"""

import threading
import time

from flask import Blueprint, jsonify, request


students_bp = Blueprint("students", __name__)


# ============================================================
# SETTINGS
# ============================================================

# A student counts as "Present" if seen within this many seconds.
PRESENT_TIMEOUT = 3.0

# When adding up presence time, never credit more than this per update,
# so a long gap (student left the frame) is not counted as present.
MAX_PRESENCE_GAP = 2.0

# Forget students not seen for this long (keeps memory bounded).
FORGET_AFTER_SECONDS = 30 * 60

# Eye states that count as "paying attention".
ATTENTIVE_EYE_STATES = ("Open", "Blink")

MAX_NAME_LENGTH = 40


# ============================================================
# SESSION STATE
# ============================================================

_students = {}
_next_student_id = 1
_session_start = None
_lock = threading.Lock()


def reset_student_registry(now=None):
    """Start a fresh session (called when the camera connects/disconnects)."""

    global _next_student_id
    global _session_start

    with _lock:

        _students.clear()
        _next_student_id = 1
        _session_start = now if now is not None else time.time()


# ============================================================
# ENGAGEMENT SCORE
# ============================================================

def engagement_score(emotion, emotion_confidence, eye_state, eye_confidence):
    """
    Instantaneous engagement score, 0-100.

    This is a direct port of getIndividualEngagement() from
    frontend/src/pages/Classroom.jsx so the live cards and the new
    reports always agree.
    """

    emotion_name = str(emotion or "").lower()
    eye_name = str(eye_state or "").lower()

    emo_conf = max(0.0, min(100.0, float(emotion_confidence or 0)))
    eye_conf = max(0.0, min(100.0, float(eye_confidence or 0)))

    score = 50.0

    if eye_name == "open":
        score += 25
    elif eye_name == "blink":
        score += 18
    elif eye_name == "close":
        score -= 20
    elif eye_name == "drowsy":
        score -= 30
    elif eye_name == "sleeping":
        score -= 40

    if emotion_name == "happy":
        score += 15
    elif emotion_name == "neutral":
        score += 10
    elif emotion_name == "surprise":
        score += 3
    elif emotion_name in ("fear", "angry"):
        score -= 5
    elif emotion_name == "sad":
        score -= 12
    elif emotion_name == "disgust":
        score -= 8

    score += ((emo_conf + eye_conf) / 2.0 - 50.0) * 0.10

    return int(round(max(0.0, min(100.0, score))))


def engagement_level(score):

    if score >= 75:
        return "Engaged"

    if score >= 50:
        return "Moderate"

    return "Low"


def attention_level(percent, has_data):

    if not has_data:
        return "Unknown"

    if percent >= 75:
        return "High"

    if percent >= 50:
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

def _iou(a, b):

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
    Score how likely `box` is the same person as `previous_box`.
    Returns None when they are not a plausible match.

    strict=True is used for students who are currently absent: they only
    match if they reappear in (nearly) the same place, so a new person
    walking past does not inherit someone else's history.
    """

    iou = _iou(box, previous_box)
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


# ============================================================
# UPDATE FROM THE AI LOOP
# ============================================================

def _new_record(student_id, box, now):

    return {
        "id": student_id,
        "name": f"Student {student_id}",

        "first_seen": now,
        "last_seen": now,
        "last_update": now,
        "box": box,

        "present_seconds": 0.0,

        "samples": 0,
        "face_samples": 0,

        "emotion_counts": {},
        "eye_counts": {},

        "engagement_sum": 0.0,
        "engagement_samples": 0,
        "current_engagement": 0,

        "current_emotion": "Unknown",
        "current_eye_state": "Unknown",
        "face_visible": False,

        "previous_eye_state": "Unknown",
        "drowsy_events": 0,
        "sleeping_events": 0,
    }


def update_student_registry(person_boxes, face_results, now=None):
    """
    Feed one AI cycle into the registry.

    person_boxes: list of (x1, y1, x2, y2) YOLO person boxes for the frame.
    face_results: the list of result dicts process_frame() returned.

    Presence comes from the YOLO person boxes (robust even when a student
    looks down and the face detector loses them); emotion / eye data comes
    from the face results.
    """

    global _next_student_id
    global _session_start

    if now is None:
        now = time.time()

    # ---- pair each person box with its largest detected face ----------

    detections = []

    for x1, y1, x2, y2 in person_boxes:

        box = (int(x1), int(y1), int(x2 - x1), int(y2 - y1))

        if box[2] <= 0 or box[3] <= 0:
            continue

        best_face = None

        for face in face_results:

            if (
                face.get("person_x") == box[0]
                and face.get("person_y") == box[1]
                and face.get("person_width") == box[2]
                and face.get("person_height") == box[3]
            ):

                area = face.get("width", 0) * face.get("height", 0)

                if (
                    best_face is None
                    or area > best_face.get("width", 0) * best_face.get("height", 0)
                ):
                    best_face = face

        detections.append((box, best_face))

    with _lock:

        if _session_start is None:
            _session_start = now

        # ---- forget very old students ---------------------------------

        for student_id in [
            sid for sid, rec in _students.items()
            if now - rec["last_seen"] > FORGET_AFTER_SECONDS
        ]:
            del _students[student_id]

        # ---- match detections to known students (one-to-one) ----------

        candidates = []

        for det_index, (box, _face) in enumerate(detections):

            for student_id, rec in _students.items():

                is_present = (now - rec["last_seen"]) <= PRESENT_TIMEOUT

                score = _match_score(box, rec["box"], strict=not is_present)

                if score is not None:
                    candidates.append((score, det_index, student_id))

        candidates.sort(reverse=True)

        assigned_detections = {}
        used_students = set()

        for _score, det_index, student_id in candidates:

            if det_index in assigned_detections or student_id in used_students:
                continue

            assigned_detections[det_index] = student_id
            used_students.add(student_id)

        # ---- apply each detection -------------------------------------

        for det_index, (box, face) in enumerate(detections):

            student_id = assigned_detections.get(det_index)

            if student_id is None:

                student_id = _next_student_id
                _next_student_id += 1

                _students[student_id] = _new_record(student_id, box, now)

            else:

                gap = now - _students[student_id]["last_update"]

                _students[student_id]["present_seconds"] += min(
                    max(gap, 0.0),
                    MAX_PRESENCE_GAP
                )

            rec = _students[student_id]

            rec["box"] = box
            rec["last_seen"] = now
            rec["last_update"] = now
            rec["samples"] += 1

            if face is None:

                rec["face_visible"] = False
                rec["current_emotion"] = "Unknown"
                rec["current_eye_state"] = "Unknown"

                continue

            rec["face_visible"] = True
            rec["face_samples"] += 1

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

            score = engagement_score(
                emotion,
                face.get("confidence", 0),
                eye_state,
                face.get("eye_confidence", 0)
            )

            rec["engagement_sum"] += score
            rec["engagement_samples"] += 1
            rec["current_engagement"] = score


# ============================================================
# BUILD REPORTS
# ============================================================

def _percent(part, whole):

    return round(100.0 * part / whole, 1) if whole else 0.0


def _build_report(rec, now, session_seconds):

    # ---- attendance ---------------------------------------------------

    seen_ago = now - rec["last_seen"]
    present = seen_ago <= PRESENT_TIMEOUT

    attendance_percent = (
        min(100.0, _percent(rec["present_seconds"], session_seconds))
        if session_seconds > 0
        else 0.0
    )

    # ---- emotion ------------------------------------------------------

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

    dominant_emotion = distribution[0]["emotion"] if distribution else "Unknown"

    # ---- eyes / attention ---------------------------------------------

    eye_counts = rec["eye_counts"]
    eye_total = sum(eye_counts.values())

    attentive = sum(eye_counts.get(s, 0) for s in ATTENTIVE_EYE_STATES)

    attention_percent = _percent(attentive, eye_total)

    # ---- engagement ---------------------------------------------------

    if rec["engagement_samples"]:

        overall = round(rec["engagement_sum"] / rec["engagement_samples"])

    else:

        overall = 0

    has_engagement = rec["engagement_samples"] > 0

    return {

        "student_id": rec["id"],
        "name": rec["name"],

        "attendance": {
            "status": "Present" if present else "Left",
            "present_seconds": round(rec["present_seconds"], 1),
            "attendance_percent": attendance_percent,
            "first_seen_seconds": round(
                rec["first_seen"] - (now - session_seconds), 1
            ) if session_seconds > 0 else 0.0,
            "last_seen_seconds_ago": round(seen_ago, 1),
        },

        "emotion": {
            "current": rec["current_emotion"] if present else "Unknown",
            "dominant": dominant_emotion,
            "distribution": distribution,
        },

        "attention": {
            "percent": attention_percent,
            "level": attention_level(attention_percent, eye_total > 0),
        },

        "eyes": {
            "current": rec["current_eye_state"] if present else "Unknown",
            "status": eye_status_label(
                rec["current_eye_state"] if present else "Unknown"
            ),
            "drowsy_percent": _percent(eye_counts.get("Drowsy", 0), eye_total),
            "sleeping_percent": _percent(eye_counts.get("Sleeping", 0), eye_total),
            "drowsy_events": rec["drowsy_events"],
            "sleeping_events": rec["sleeping_events"],
            "counts": dict(eye_counts),
        },

        "engagement": {
            "current": rec["current_engagement"] if present else 0,
            "overall_percent": overall,
            "level": (
                engagement_level(overall) if has_engagement else "Unknown"
            ),
        },

        "face_visibility_percent": _percent(rec["face_samples"], rec["samples"]),
        "samples": rec["samples"],
    }


def build_student_reports(now=None):

    if now is None:
        now = time.time()

    with _lock:

        session_seconds = (
            max(0.0, now - _session_start) if _session_start else 0.0
        )

        reports = [
            _build_report(rec, now, session_seconds)
            for _sid, rec in sorted(_students.items())
        ]

    scored = [
        r["engagement"]["overall_percent"]
        for r in reports
        if r["samples"] > 0 and r["face_visibility_percent"] > 0
    ]

    return {

        "success": True,

        "session_seconds": round(session_seconds, 1),

        "students_total": len(reports),

        "students_present": sum(
            1 for r in reports if r["attendance"]["status"] == "Present"
        ),

        "class_average_engagement": (
            round(sum(scored) / len(scored)) if scored else 0
        ),

        "students": reports,
    }


# ============================================================
# ROUTES
# ============================================================

@students_bp.route("/students/report", methods=["GET"])
def students_report():

    return jsonify(build_student_reports())


@students_bp.route("/students/<int:student_id>/rename", methods=["POST"])
def rename_student(student_id):

    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()

    if not name:

        return jsonify({
            "success": False,
            "message": "Name cannot be empty"
        }), 400

    with _lock:

        rec = _students.get(student_id)

        if rec is None:

            return jsonify({
                "success": False,
                "message": "Student not found"
            }), 404

        rec["name"] = name[:MAX_NAME_LENGTH]

        saved_name = rec["name"]

    return jsonify({
        "success": True,
        "student_id": student_id,
        "name": saved_name
    })


@students_bp.route("/students/reset", methods=["POST"])
def reset_students():

    reset_student_registry()

    return jsonify({
        "success": True,
        "message": "Student session reset"
    })
