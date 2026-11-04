"""SQLite storage (point 11): sessions, students, samples and alerts.

Replaces the loose JSON files (saved_reports/*.json, saved_alerts/alerts.json)
so analytics survive a restart and sessions of a class can be compared over
time. Only the standard library is used (no server to install).

Tables
------
classes    one row per class / room
sessions   one row per class session (live or recorded video), with the
           summary numbers as columns and the full report as JSON
students   one row per tracked student of a session
samples    the class engagement measured during a session (about one row
           every few seconds) - the time series behind trend charts
alerts     every alert ever raised, per class

Configuration: CLASSROOM_DB_PATH (default backend/data/classroom.db).

The database could be swapped for PostgreSQL later: all SQL is in this file
and only touches plain tables.
"""

import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager

from class_id import DEFAULT_CLASS_ID

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data",
    "classroom.db",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS classes (
    class_id   TEXT PRIMARY KEY,
    name       TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id                       TEXT PRIMARY KEY,
    class_id                 TEXT NOT NULL,
    kind                     TEXT NOT NULL DEFAULT 'live',
    title                    TEXT,
    started_at               REAL NOT NULL,
    ended_at                 REAL,
    duration_seconds         INTEGER,
    students_total           INTEGER,
    class_average_engagement REAL,
    overall_engagement       REAL,
    attention                REAL,
    peak_students            INTEGER,
    engagement_levels        TEXT,
    report_json              TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_class
    ON sessions (class_id, started_at);

CREATE TABLE IF NOT EXISTS students (
    session_id         TEXT NOT NULL
                       REFERENCES sessions (id) ON DELETE CASCADE,
    student_id         INTEGER NOT NULL,
    name               TEXT,
    engagement_percent REAL,
    engagement_level   TEXT,
    report_json        TEXT NOT NULL,
    PRIMARY KEY (session_id, student_id)
);

CREATE TABLE IF NOT EXISTS samples (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     TEXT NOT NULL
                   REFERENCES sessions (id) ON DELETE CASCADE,
    ts             REAL NOT NULL,
    students       INTEGER,
    engagement     REAL,
    attention      REAL,
    drowsy_percent REAL
);
CREATE INDEX IF NOT EXISTS idx_samples_session
    ON samples (session_id, ts);

CREATE TABLE IF NOT EXISTS alerts (
    id           TEXT PRIMARY KEY,
    class_id     TEXT NOT NULL,
    session_id   TEXT,
    type         TEXT,
    severity     TEXT,
    status       TEXT,
    started_at   REAL,
    resolved_at  REAL,
    acknowledged INTEGER NOT NULL DEFAULT 0,
    alert_json   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alerts_class
    ON alerts (class_id, started_at);
"""


def _dumps(value):
    return json.dumps(value, separators=(",", ":"))


class Storage:
    """Small thread-safe wrapper around one SQLite file."""

    def __init__(self, path=None):

        self.path = path or os.environ.get("CLASSROOM_DB_PATH") or DEFAULT_DB_PATH
        self._lock = threading.RLock()

        directory = os.path.dirname(self.path)

        if directory:
            os.makedirs(directory, exist_ok=True)

        conn = self._connect()

        try:
            conn.executescript(SCHEMA)
        finally:
            conn.close()

        logger.info("SQLite storage ready: %s", self.path)

    # --------------------------------------------------------

    def _connect(self):

        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")

        return conn

    @contextmanager
    def _txn(self):
        """One locked transaction: commit on success, roll back on error,
        and always close the connection."""

        with self._lock:

            conn = self._connect()

            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _run(self, sql, params=()):
        """Run one write statement in its own transaction."""

        with self._txn() as conn:
            conn.execute(sql, params)

    def _query(self, sql, params=()):

        with self._lock:
            conn = self._connect()
            try:
                return [dict(row) for row in conn.execute(sql, params)]
            finally:
                conn.close()

    # --------------------------------------------------------
    # classes
    # --------------------------------------------------------

    def ensure_class(self, class_id, name=None):

        self._run(
            "INSERT OR IGNORE INTO classes (class_id, name, created_at) "
            "VALUES (?, ?, ?)",
            (class_id, name or class_id, time.time()),
        )

    def list_classes(self):
        return self._query("SELECT * FROM classes ORDER BY created_at")

    # --------------------------------------------------------
    # sessions
    # --------------------------------------------------------

    def create_session(self, session_id, class_id, started_at, kind="live"):
        """Open a session row so samples can be attached while it runs."""

        self.ensure_class(class_id)

        self._run(
            "INSERT OR REPLACE INTO sessions "
            "(id, class_id, kind, started_at) VALUES (?, ?, ?, ?)",
            (session_id, class_id, kind, started_at),
        )

    def discard_session(self, session_id):
        """Remove a session (and its samples / students) - e.g. when the
        session ended without detecting anybody."""

        self._run("DELETE FROM sessions WHERE id = ?", (session_id,))

    def finish_session(self, report, class_id=DEFAULT_CLASS_ID, kind="live"):
        """Store the final report. report["id"] is the session id."""

        self.ensure_class(class_id)

        with self._txn() as conn:

            conn.execute(
                "INSERT INTO sessions (id, class_id, kind, title, started_at, "
                "ended_at, duration_seconds, students_total, "
                "class_average_engagement, overall_engagement, attention, "
                "peak_students, engagement_levels, report_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET "
                "class_id=excluded.class_id, kind=excluded.kind, "
                "title=excluded.title, started_at=excluded.started_at, "
                "ended_at=excluded.ended_at, "
                "duration_seconds=excluded.duration_seconds, "
                "students_total=excluded.students_total, "
                "class_average_engagement=excluded.class_average_engagement, "
                "overall_engagement=excluded.overall_engagement, "
                "attention=excluded.attention, "
                "peak_students=excluded.peak_students, "
                "engagement_levels=excluded.engagement_levels, "
                "report_json=excluded.report_json",
                (
                    report["id"], class_id, kind, report.get("title"),
                    report["started_at"], report.get("ended_at"),
                    report.get("duration_seconds"),
                    report.get("students_total"),
                    report.get("class_average_engagement"),
                    report.get("overall_engagement"),
                    report.get("attention"),
                    report.get("peak_students"),
                    _dumps(report.get("engagement_levels") or {}),
                    _dumps(report),
                ),
            )

            conn.execute(
                "DELETE FROM students WHERE session_id = ?", (report["id"],)
            )

            conn.executemany(
                "INSERT INTO students (session_id, student_id, name, "
                "engagement_percent, engagement_level, report_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        report["id"],
                        student.get("id", index),
                        student.get("name"),
                        (student.get("engagement") or {}).get("overall_percent"),
                        (student.get("engagement") or {}).get("level"),
                        _dumps(student),
                    )
                    for index, student in enumerate(
                        report.get("students", []), start=1
                    )
                ],
            )

    def list_sessions(self, class_id=None, kind=None, limit=500):
        """Finished sessions, newest first (summary columns only)."""

        sql = (
            "SELECT id, class_id, kind, title, started_at, ended_at, "
            "duration_seconds, students_total, class_average_engagement, "
            "overall_engagement, attention, peak_students, engagement_levels "
            "FROM sessions WHERE ended_at IS NOT NULL"
        )
        params = []

        if class_id:
            sql += " AND class_id = ?"
            params.append(class_id)

        if kind:
            sql += " AND kind = ?"
            params.append(kind)

        sql += " ORDER BY ended_at DESC LIMIT ?"
        params.append(int(limit))

        rows = self._query(sql, params)

        for row in rows:
            row["engagement_levels"] = json.loads(
                row["engagement_levels"] or "{}"
            )

        return rows

    def get_session_report(self, session_id):
        """The full report dict, or None."""

        rows = self._query(
            "SELECT report_json, class_id FROM sessions WHERE id = ? "
            "AND report_json IS NOT NULL",
            (session_id,),
        )

        if not rows:
            return None

        report = json.loads(rows[0]["report_json"])
        report.setdefault("class_id", rows[0]["class_id"])

        return report

    def delete_session(self, session_id):
        """Delete a stored session. Returns True if it existed."""

        with self._txn() as conn:
            cursor = conn.execute(
                "DELETE FROM sessions WHERE id = ?", (session_id,)
            )
            return cursor.rowcount > 0

    def rename_student(self, session_id, student_id, name):

        self._run(
            "UPDATE students SET name = ? WHERE session_id = ? "
            "AND student_id = ?",
            (name, session_id, student_id),
        )

    # --------------------------------------------------------
    # samples (engagement over time)
    # --------------------------------------------------------

    def add_sample(
        self, session_id, ts, students, engagement, attention, drowsy_percent
    ):

        self._run(
            "INSERT INTO samples (session_id, ts, students, engagement, "
            "attention, drowsy_percent) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, ts, students, engagement, attention, drowsy_percent),
        )

    def get_samples(self, session_id):

        return self._query(
            "SELECT ts, students, engagement, attention, drowsy_percent "
            "FROM samples WHERE session_id = ? ORDER BY ts",
            (session_id,),
        )

    def compare_sessions(self, class_id=None, limit=30):
        """Engagement per finished session, oldest first, for trend charts
        ("is this class getting more or less engaged over the weeks?")."""

        sql = (
            "SELECT s.id, s.class_id, s.title, s.started_at, s.ended_at, "
            "s.students_total, s.class_average_engagement, "
            "s.overall_engagement, s.attention, s.peak_students, "
            "(SELECT COUNT(*) FROM alerts a WHERE a.session_id = s.id) "
            "AS alert_count, "
            "(SELECT AVG(m.drowsy_percent) FROM samples m "
            "WHERE m.session_id = s.id) AS avg_drowsy_percent "
            "FROM sessions s WHERE s.ended_at IS NOT NULL"
        )
        params = []

        if class_id:
            sql += " AND s.class_id = ?"
            params.append(class_id)

        sql += " ORDER BY s.started_at DESC LIMIT ?"
        params.append(int(limit))

        return list(reversed(self._query(sql, params)))

    # --------------------------------------------------------
    # alerts
    # --------------------------------------------------------

    def upsert_alert(self, alert, class_id=DEFAULT_CLASS_ID):

        self.ensure_class(class_id)

        self._run(
            "INSERT INTO alerts (id, class_id, session_id, type, severity, "
            "status, started_at, resolved_at, acknowledged, alert_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET status=excluded.status, "
            "resolved_at=excluded.resolved_at, "
            "acknowledged=excluded.acknowledged, "
            "alert_json=excluded.alert_json",
            (
                alert["id"], class_id, alert.get("session_id"),
                alert.get("type"), alert.get("severity"),
                alert.get("status"), alert.get("started_at"),
                alert.get("resolved_at"),
                1 if alert.get("acknowledged") else 0,
                _dumps(alert),
            ),
        )

    def load_alerts(self, class_id=DEFAULT_CLASS_ID, limit=500):
        """The newest `limit` alerts of a class, oldest first."""

        rows = self._query(
            "SELECT alert_json FROM alerts WHERE class_id = ? "
            "ORDER BY started_at DESC LIMIT ?",
            (class_id, int(limit)),
        )

        return [json.loads(row["alert_json"]) for row in reversed(rows)]

    def count_alerts(self, class_id=DEFAULT_CLASS_ID):

        return self._query(
            "SELECT COUNT(*) AS n FROM alerts WHERE class_id = ?",
            (class_id,),
        )[0]["n"]

    def delete_alert(self, alert_id):

        self._run("DELETE FROM alerts WHERE id = ?", (alert_id,))

    def delete_resolved_alerts(self, class_id=DEFAULT_CLASS_ID):
        """Returns how many rows were removed."""

        with self._txn() as conn:
            cursor = conn.execute(
                "DELETE FROM alerts WHERE class_id = ? AND status != 'active'",
                (class_id,),
            )
            return cursor.rowcount

    # --------------------------------------------------------
    # one-time import of the old JSON files
    # --------------------------------------------------------

    def import_legacy_alerts(self, alerts, class_id=DEFAULT_CLASS_ID):
        """Copy alerts from the old alerts.json. Returns how many."""

        imported = 0

        for alert in alerts:
            if isinstance(alert, dict) and alert.get("id"):
                self.upsert_alert(alert, class_id)
                imported += 1

        return imported

    def import_legacy_reports(self, reports_dir, class_id=DEFAULT_CLASS_ID):
        """Copy saved_reports/*.json that are not in the database yet."""

        if not os.path.isdir(reports_dir):
            return 0

        known = {
            row["id"] for row in self._query("SELECT id FROM sessions")
        }
        imported = 0

        for name in sorted(os.listdir(reports_dir)):

            if not name.endswith(".json"):
                continue

            try:
                with open(
                    os.path.join(reports_dir, name), encoding="utf-8"
                ) as handle:
                    report = json.load(handle)

                if report["id"] in known:
                    continue

                self.finish_session(report, class_id)
                imported += 1

            except Exception as error:
                logger.warning("Skipping legacy report %s: %s", name, error)

        if imported:
            logger.info("Imported %d legacy report(s) into SQLite", imported)

        return imported


# ============================================================
# SHARED INSTANCE
# ============================================================

_storage = None
_storage_lock = threading.Lock()


def get_storage():
    """The process-wide Storage (created on first use)."""

    global _storage

    with _storage_lock:

        if _storage is None:
            _storage = Storage()

        return _storage


def reset_storage_for_tests():
    """Forget the shared instance (tests point CLASSROOM_DB_PATH elsewhere)."""

    global _storage

    with _storage_lock:
        _storage = None
