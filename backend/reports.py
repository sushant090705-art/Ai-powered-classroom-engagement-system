"""Saved session reports.

When a live session ends (camera stopped), save_session_report() stores a
final per-student report as a JSON file in backend/saved_reports/.
The routes below list, open and delete those reports. The live student
routes (/students/...) are here too.
"""

import json
import os
import re
import time
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request

from analytics import get_session_snapshot
from ai_processing import student_registry


reports_bp = Blueprint("reports", __name__)

REPORTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "saved_reports",
)

ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")

# A tracked person needs this many samples to count as a student.
MIN_STUDENT_SAMPLES = 3
MIN_SAMPLE_SHARE = 0.05


def _summary(report):

    return {
        "id": report["id"],
        "title": report["title"],
        "started_at": report["started_at"],
        "ended_at": report["ended_at"],
        "duration_seconds": report["duration_seconds"],
        "students_total": report["students_total"],
        "class_average_engagement": report["class_average_engagement"],
        "engagement_levels": report["engagement_levels"],
    }


def _path_for(report_id):

    if not ID_PATTERN.match(report_id or ""):
        return None

    return os.path.join(REPORTS_DIR, f"{report_id}.json")


def save_session_report():
    """Build and store the report for the session that just ended.

    Returns the report summary, or None when there is nothing to save
    (no session, or no student was detected).
    """

    snapshot = get_session_snapshot()

    if snapshot is None or snapshot["total_samples"] == 0:
        return None

    now = time.time()

    min_samples = max(
        MIN_STUDENT_SAMPLES,
        int(round(MIN_SAMPLE_SHARE * snapshot["total_samples"])),
    )

    class_report = student_registry.build_reports(
        now=now, min_samples=min_samples
    )

    if class_report["students_total"] == 0:
        return None

    students = sorted(
        class_report["students"],
        key=lambda s: s["engagement"]["overall_percent"],
        reverse=True,
    )

    levels = {"Engaged": 0, "Moderate": 0, "Low": 0}

    for student in students:
        level = student["engagement"]["level"]
        levels[level] = levels.get(level, 0) + 1

    report_id = uuid.uuid4().hex

    report = {
        "id": report_id,
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

    os.makedirs(REPORTS_DIR, exist_ok=True)

    final_path = _path_for(report_id)
    temp_path = final_path + ".tmp"

    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle)

    os.replace(temp_path, final_path)

    return _summary(report)


# ============================================================
# SAVED REPORT ROUTES
# ============================================================

@reports_bp.route("/reports", methods=["GET"])
def list_reports():

    summaries = []

    if os.path.isdir(REPORTS_DIR):

        for name in os.listdir(REPORTS_DIR):

            if not name.endswith(".json"):
                continue

            try:
                with open(
                    os.path.join(REPORTS_DIR, name), encoding="utf-8"
                ) as handle:
                    summaries.append(_summary(json.load(handle)))
            except Exception as e:
                print("Skipping unreadable report", name, e)

    summaries.sort(key=lambda r: r["ended_at"], reverse=True)

    return jsonify({"success": True, "reports": summaries})


@reports_bp.route("/reports/<report_id>", methods=["GET"])
def get_report(report_id):

    path = _path_for(report_id)

    if path is None or not os.path.exists(path):
        return jsonify({"success": False, "message": "Report not found"}), 404

    with open(path, encoding="utf-8") as handle:
        return jsonify({"success": True, "report": json.load(handle)})


@reports_bp.route("/reports/<report_id>", methods=["DELETE"])
def delete_report(report_id):

    path = _path_for(report_id)

    if path is None or not os.path.exists(path):
        return jsonify({"success": False, "message": "Report not found"}), 404

    os.remove(path)

    return jsonify({"success": True, "message": "Report deleted"})


# ============================================================
# LIVE STUDENT ROUTES (used by the Classroom page)
# ============================================================

@reports_bp.route("/students/report", methods=["GET"])
def live_student_report():

    return jsonify(
        student_registry.build_reports(min_samples=MIN_STUDENT_SAMPLES)
    )


@reports_bp.route("/students/<int:student_id>/rename", methods=["POST"])
def rename_student(student_id):

    name = ((request.get_json(silent=True) or {}).get("name") or "").strip()

    if not name or len(name) > 60:
        return jsonify({"success": False, "message": "Invalid name"}), 400

    if not student_registry.rename(student_id, name):
        return jsonify({"success": False, "message": "Student not found"}), 404

    return jsonify({"success": True})