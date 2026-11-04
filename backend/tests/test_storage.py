"""SQLite storage (point 11)."""

import json

import pytest

from storage import Storage


@pytest.fixture
def store(tmp_path):
    return Storage(str(tmp_path / "test.db"))


def report(session_id, engagement=70, started=1000.0, students=2):
    return {
        "id": session_id,
        "title": "Class session",
        "started_at": started,
        "ended_at": started + 600,
        "duration_seconds": 600,
        "students_total": students,
        "class_average_engagement": engagement,
        "overall_engagement": engagement,
        "attention": 80,
        "peak_students": students,
        "engagement_levels": {"Engaged": 1, "Moderate": 1, "Low": 0},
        "students": [
            {"id": i + 1, "name": f"S{i + 1}",
             "engagement": {"overall_percent": engagement, "level": "Moderate"}}
            for i in range(students)
        ],
    }


def test_session_round_trip(store):
    store.finish_session(report("a" * 32), "c1")

    full = store.get_session_report("a" * 32)
    assert full["class_id"] == "c1"
    assert len(full["students"]) == 2

    rows = store.list_sessions()
    assert rows[0]["id"] == "a" * 32
    assert rows[0]["engagement_levels"] == {"Engaged": 1, "Moderate": 1, "Low": 0}


def test_list_sessions_filters_by_class_and_orders_newest_first(store):
    store.finish_session(report("a" * 32, started=1000), "c1")
    store.finish_session(report("b" * 32, started=5000), "c1")
    store.finish_session(report("c" * 32, started=3000), "c2")

    assert [r["id"][0] for r in store.list_sessions("c1")] == ["b", "a"]
    assert [r["id"][0] for r in store.list_sessions("c2")] == ["c"]
    assert len(store.list_sessions()) == 3


def test_open_sessions_are_not_listed_until_finished(store):
    store.create_session("d" * 32, "c1", 1000.0)
    assert store.list_sessions() == []
    assert store.get_session_report("d" * 32) is None


def test_delete_cascades_to_students_and_samples(store):
    sid = "a" * 32
    store.create_session(sid, "c1", 1000.0)
    store.add_sample(sid, 1001.0, 3, 70.0, 80.0, 0.0)
    store.finish_session(report(sid), "c1")

    assert store.delete_session(sid) is True
    assert store.delete_session(sid) is False
    assert store.get_samples(sid) == []
    assert store._query("SELECT * FROM students") == []


def test_discard_removes_an_empty_session(store):
    store.create_session("e" * 32, "c1", 1.0)
    store.add_sample("e" * 32, 2.0, 0, None, None, None)
    store.discard_session("e" * 32)

    assert store._query("SELECT * FROM sessions") == []
    assert store._query("SELECT * FROM samples") == []


def test_samples_are_returned_in_time_order(store):
    sid = "a" * 32
    store.create_session(sid, "c1", 0)
    store.add_sample(sid, 20.0, 3, 60.0, 70.0, 10.0)
    store.add_sample(sid, 10.0, 3, 80.0, 90.0, 0.0)

    assert [s["ts"] for s in store.get_samples(sid)] == [10.0, 20.0]


def test_compare_sessions_is_oldest_first_with_alert_counts(store):
    for sid, started, eng in (("a", 1000, 60), ("b", 2000, 70), ("c", 3000, 80)):
        store.create_session(sid * 32, "c1", started)
        store.add_sample(sid * 32, started, 2, eng, eng, 20.0)
        store.finish_session(report(sid * 32, eng, started), "c1")

    store.upsert_alert(
        {"id": "x" * 32, "type": "LOW_ENGAGEMENT", "status": "resolved",
         "started_at": 1001, "session_id": "b" * 32}, "c1")

    rows = store.compare_sessions("c1")

    assert [r["overall_engagement"] for r in rows] == [60, 70, 80]
    assert [r["alert_count"] for r in rows] == [0, 1, 0]
    assert rows[0]["avg_drowsy_percent"] == 20.0


def test_alert_upsert_update_and_delete(store):
    alert = {"id": "1" * 32, "type": "TEST", "status": "active",
             "started_at": 1.0, "acknowledged": False}
    store.upsert_alert(alert, "c1")

    alert.update(status="resolved", resolved_at=5.0, acknowledged=True)
    store.upsert_alert(alert, "c1")

    loaded = store.load_alerts("c1")
    assert len(loaded) == 1 and loaded[0]["status"] == "resolved"
    assert store.delete_resolved_alerts("c1") == 1
    assert store.load_alerts("c1") == []


def test_load_alerts_returns_the_newest_limit_oldest_first(store):
    for i in range(5):
        store.upsert_alert({"id": f"{i}" * 32, "status": "resolved",
                            "started_at": float(i)}, "c1")

    assert [a["started_at"] for a in store.load_alerts("c1", limit=3)] == [2.0, 3.0, 4.0]


def test_legacy_reports_are_imported_once(store, tmp_path):
    folder = tmp_path / "saved_reports"
    folder.mkdir()
    (folder / "x.json").write_text(json.dumps(report("f" * 32)))
    (folder / "broken.json").write_text("{not json")

    assert store.import_legacy_reports(str(folder)) == 1
    assert store.import_legacy_reports(str(folder)) == 0
    assert store.get_session_report("f" * 32)["students_total"] == 2


def test_data_survives_reopening_the_database(tmp_path):
    path = str(tmp_path / "keep.db")
    Storage(path).finish_session(report("a" * 32), "c1")

    assert Storage(path).get_session_report("a" * 32) is not None
