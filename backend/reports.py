"""Saved session reports (stored in SQLite, see storage.py).

When a live session ends (camera stopped), save_session_report() stores a
final per-student report. The routes below list, open and delete the saved
reports, compare sessions over time, and serve the live student routes
(/students/...).

Every route takes an optional ?class_id=... (point 12). Without it the
live routes use the default class and the report list shows all classes.
"""

import logging
import os
import re
import threading
import time
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request

from analytics import get_session_snapshot
from class_id import DEFAULT_CLASS_ID, normalize_class_id
from engine import get_class_engine
from storage import get_storage

logger = logging.getLogger(__name__)


reports_bp = Blueprint("reports", __name__)

# Folder of the old JSON reports; imported into the database once.
LEGACY_REPORTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "saved_reports",
)

ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")

# A tracked person needs this many samples to count as a student.
MIN_STUDENT_SAMPLES = 3
MIN_SAMPLE_SHARE = 0.05

_legacy_lock = threading.Lock()
_legacy_checked = False


def _ensure_legacy_imported():
    """Copy old saved_reports/*.json into SQLite (once per process)."""

    global _legacy_checked

    with _legacy_lock:

        if _legacy_checked:
            return

        _legacy_checked = True

        try:
            get_storage().import_legacy_reports(LEGACY_REPORTS_DIR)
        except Exception:
            logger.exception("Legacy report import failed")


def _summary(report):

    return {
        "id": report["id"],
        "class_id": report.get("class_id", DEFAULT_CLASS_ID),
        "title": report["title"],
        "started_at": report["started_at"],
        "ended_at": report["ended_at"],
        "duration_seconds": report["duration_seconds"],
        "students_total": report["students_total"],
        "class_average_engagement": report["class_average_engagement"],
        "engagement_levels": report["engagement_levels"],
    }


def save_session_report(class_id=DEFAULT_CLASS_ID):
    """Build and store the report for the session that just ended.

    Returns the report summary, or None when there is nothing to save
    (no session, or no student was detected).
    """

    engine = get_class_engine(class_id)
    store = get_storage()
    session_id = engine.session_id

    snapshot = get_session_snapshot(class_id)

    def nothing_to_save():
        if session_id:
            store.discard_session(session_id)
        return None

    if snapshot is None or snapshot["total_samples"] == 0:
        return nothing_to_save()

    now = time.time()

    min_samples = max(
        MIN_STUDENT_SAMPLES,
        int(round(MIN_SAMPLE_SHARE * snapshot["total_samples"])),
    )

    class_report = engine.registry.build_reports(
        now=now, min_samples=min_samples
    )

    if class_report["students_total"] == 0:
        return nothing_to_save()

    students = sorted(
        class_report["students"],
        key=lambda s: s["engagement"]["overall_percent"],
        reverse=True,
    )

    levels = {"Engaged": 0, "Moderate": 0, "Low": 0}

    for student in students:
        level = student["engagement"]["level"]
        levels[level] = levels.get(level, 0) + 1

    report = {
        # The report id IS the session id, so samples and alerts recorded
        # during the session can be joined to it.
        "id": session_id or uuid.uuid4().hex,
        "class_id": class_id,
        "title": "Class session, " + datetime.fromtimestamp(
            snapshot["started_at"]
        ).strftime("%d %b %Y, %I:%M %p"),
        "started_at": snapshot["started_at"],
        "ended_at": now,
        "duration_seconds": int(now - snapshot["started_at"]),
        "students_total": class_report["students_total"],
        "class_average_engagement": class_report["class_average_engagement"],
        "overall_engagement": snapshot["overall_engagement"],
        "attention": snapshot["attention"],
        "peak_students": snapshot["peak_students"],
        "engagement_levels": levels,
        "emotion_distribution": snapshot["emotion_distribution"],
        "attention_distribution": snapshot["attention_distribution"],
        "engagement_trend": snapshot["engagement_trend"],
        "students": students,
    }

    store.finish_session(report, class_id, kind="live")

    return _summary(report)


# ============================================================
# HELPERS
# ============================================================

def _optional_class_id():
    """?class_id=... or None (= all classes)."""

    raw = request.args.get("class_id")

    return normalize_class_id(raw) if raw else None


@reports_bp.errorhandler(ValueError)
def _bad_class_id(error):
    return jsonify({"success": False, "message": str(error)}), 400


# ============================================================
# SAVED REPORT ROUTES
# ============================================================

@reports_bp.route("/reports", methods=["GET"])
def list_reports():

    _ensure_legacy_imported()

    rows = get_storage().list_sessions(class_id=_optional_class_id())

    return jsonify({
        "success": True,
        "reports": [_summary(row | {"title": row["title"] or ""}) for row in rows],
    })


@reports_bp.route("/reports/<report_id>", methods=["GET"])
def get_report(report_id):

    _ensure_legacy_imported()

    report = (
        get_storage().get_session_report(report_id)
        if ID_PATTERN.match(report_id) else None
    )

    if report is None:
        return jsonify({"success": False, "message": "Report not found"}), 404

    return jsonify({"success": True, "report": report})


@reports_bp.route("/reports/<report_id>", methods=["DELETE"])
def delete_report(report_id):

    if (
        not ID_PATTERN.match(report_id)
        or not get_storage().delete_session(report_id)
    ):
        return jsonify({"success": False, "message": "Report not found"}), 404

    return jsonify({"success": True, "message": "Report deleted"})


# ============================================================
# HISTORY (compare sessions over time)
# ============================================================

@reports_bp.route("/history/sessions", methods=["GET"])
def session_history():
    """Engagement of every finished session, oldest first, so a chart can
    show how a class develops over weeks."""

    _ensure_legacy_imported()

    try:
        limit = max(1, min(int(request.args.get("limit", 30)), 200))
    except ValueError:
        limit = 30

    return jsonify({
        "success": True,
        "sessions": get_storage().compare_sessions(
            _optional_class_id(), limit
        ),
    })


@reports_bp.route("/history/sessions/<session_id>/samples", methods=["GET"])
def session_samples(session_id):
    """The engagement time series recorded during one session."""

    if not ID_PATTERN.match(session_id):
        return jsonify({"success": False, "message": "Session not found"}), 404

    return jsonify({
        "success": True,
        "samples": get_storage().get_samples(session_id),
    })


# ============================================================
# LIVE STUDENT ROUTES (used by the Classroom page)
# ============================================================

@reports_bp.route("/students/report", methods=["GET"])
def live_student_report():

    registry = get_class_engine(
        normalize_class_id(request.args.get("class_id"))
    ).registry

    return jsonify(registry.build_reports(min_samples=MIN_STUDENT_SAMPLES))


@reports_bp.route("/students/<int:student_id>/rename", methods=["POST"])
def rename_student(student_id):

    name = ((request.get_json(silent=True) or {}).get("name") or "").strip()

    if not name or len(name) > 60:
        return jsonify({"success": False, "message": "Invalid name"}), 400

    registry = get_class_engine(
        normalize_class_id(request.args.get("class_id"))
    ).registry

    if not registry.rename(student_id, name):
        return jsonify({"success": False, "message": "Student not found"}), 404

    return jsonify({"success": True})
