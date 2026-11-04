"""Condition + AlertEngine rules (hold times, hysteresis, thresholds)."""

import pytest

import alerts
from alerts import AlertEngine, Condition, DEFAULT_SETTINGS, validate_settings
from conftest import make_class, make_result
from storage import Storage

FRAME = (480, 640, 3)


# ============================================================
# Condition
# ============================================================

def test_condition_raises_only_after_hold_seconds():
    c = Condition()
    assert c.update("bad", 0, hold=10, clear=5) is None
    assert c.update("bad", 9.9, hold=10, clear=5) is None
    assert c.update("bad", 10, hold=10, clear=5) == "raise"
    assert c.update("bad", 11, hold=10, clear=5) is None      # only once


def test_condition_clears_only_after_clear_seconds_of_good():
    c = Condition()
    c.update("bad", 0, 10, 5)
    c.update("bad", 10, 10, 5)
    assert c.update("good", 11, 10, 5) is None
    assert c.update("good", 15.9, 10, 5) is None
    assert c.update("good", 16, 10, 5) == "clear"


def test_a_bad_glitch_resets_the_clear_timer():
    c = Condition()
    c.update("bad", 0, 10, 5)
    c.update("bad", 10, 10, 5)
    c.update("good", 11, 10, 5)
    c.update("bad", 14, 10, 5)
    assert c.update("good", 15, 10, 5) is None
    assert c.update("good", 19, 10, 5) is None
    assert c.update("good", 20, 10, 5) == "clear"


def test_one_good_frame_resets_the_raise_timer():
    c = Condition()
    c.update("bad", 0, 10, 5)
    c.update("good", 5, 10, 5)
    assert c.update("bad", 8, 10, 5) is None
    assert c.update("bad", 17.9, 10, 5) is None
    assert c.update("bad", 18, 10, 5) == "raise"


def test_neutral_does_not_raise_and_unknown_never_counts_as_bad():
    c = Condition()
    for t in range(0, 100, 5):
        assert c.update("neutral", t, 10, 5) is None
        assert c.update("unknown", t, 10, 5) is None


def test_neutral_does_not_clear_a_raised_condition():
    c = Condition()
    c.update("bad", 0, 10, 5)
    c.update("bad", 10, 10, 5)
    for t in range(11, 200):
        assert c.update("neutral", t, 10, 5) is None
    assert c.raised


# ============================================================
# helpers
# ============================================================

def new_engine(patch=None, **kwargs):
    """In-memory engine (data_dir=None) with quick thresholds."""

    settings = {
        "disengagement_seconds": 10,
        "drowsy_seconds": 10,
        "teacher_absent_seconds": 10,
        "smoothing_seconds": 5,
        "min_students": 2,
    }
    settings.update(patch or {})

    engine = AlertEngine(
        data_dir=None, notifier=lambda alert, email: None,
        settings=settings, **kwargs,
    )
    engine.start_session(now=0.0)
    return engine


def run(engine, results, start, stop, step=1.0, boxes=(), frame=FRAME):
    """Feed the same results every `step` seconds. Returns all events."""

    events = []
    t = start
    while t <= stop + 1e-9:
        events += [
            (round(t, 1), *e) for e in engine.evaluate(list(boxes), results, frame, now=t)
        ]
        t += step
    return events


def kinds(events):
    return [(kind, alert_type) for _t, kind, alert_type in events]


# ============================================================
# low engagement (threshold 50 %)
# ============================================================

def test_low_engagement_raises_after_hold_time():
    engine = new_engine()
    events = run(engine, make_class(3, eye="Close", emotion="Sad"), 0, 15)

    assert kinds(events) == [("raise", "LOW_ENGAGEMENT")]
    assert events[0][0] == 10                    # exactly after 10 s


def test_engagement_exactly_at_threshold_is_not_low():
    # eye Unknown (50) + emotion Unknown (50) -> score exactly 50
    engine = new_engine({"disengagement_threshold": 50})
    results = make_class(3, eye="Unknown", emotion="Unknown")

    assert run(engine, results, 0, 60) == []
    assert engine.get_status()["engagement"] == 50


def test_engagement_just_below_threshold_is_low():
    # Close + Neutral = 47
    engine = new_engine({"disengagement_threshold": 50})
    events = run(engine, make_class(3, eye="Close", emotion="Neutral"), 0, 15)

    assert kinds(events) == [("raise", "LOW_ENGAGEMENT")]


def test_high_engagement_never_alerts():
    engine = new_engine()
    assert run(engine, make_class(3), 0, 120) == []


def test_hysteresis_engagement_must_recover_5_points_to_clear():
    engine = new_engine({"disengagement_threshold": 50, "smoothing_seconds": 5})
    run(engine, make_class(3, eye="Close", emotion="Sad"), 0, 12)
    assert engine.get_status()["active_alert_count"] == 1

    # 52 %: above the threshold but inside the 5-point margin -> stays active
    in_margin = make_class(3, eye="Close", emotion="Happy")     # 22.75+29.75 = 52.5
    events = run(engine, in_margin, 13, 100)
    assert events == []
    assert engine.get_status()["active_alert_count"] == 1

    # 85 % for CLEAR_SECONDS (20 s) -> resolves
    events = run(engine, make_class(3), 101, 140)
    assert kinds(events) == [("clear", "LOW_ENGAGEMENT")]


def test_not_enough_students_means_no_judgement():
    engine = new_engine({"min_students": 2})
    one_sleeping = make_class(1, eye="Close", emotion="Sad")

    assert run(engine, one_sleeping, 0, 120) == []
    assert engine.get_status()["engagement"] is None


# ============================================================
# drowsy class (threshold 30 %)
# ============================================================

def drowsy_class(total, drowsy):
    return (
        make_class(drowsy, eye="Drowsy", emotion="Happy")
        + [make_result("Open", "Happy", x=10 + (drowsy + i) * 100) for i in range(total - drowsy)]
    )


def test_drowsy_share_raises_at_the_threshold():
    engine = new_engine({"drowsy_share_threshold": 30})
    events = run(engine, drowsy_class(10, 3), 0, 15)      # exactly 30 %

    assert ("raise", "CLASS_DROWSY") in kinds(events)


def test_drowsy_share_below_threshold_is_fine():
    engine = new_engine({"drowsy_share_threshold": 30})
    events = run(engine, drowsy_class(10, 2), 0, 60)      # 20 %

    assert kinds(events) == []


def test_sleeping_counts_as_drowsy():
    engine = new_engine()
    events = run(engine, make_class(4, eye="Sleeping"), 0, 15)

    assert ("raise", "CLASS_DROWSY") in kinds(events)


# ============================================================
# teacher presence
# ============================================================

ZONE = {"x1": 0.0, "y1": 0.0, "x2": 0.5, "y2": 1.0}   # left half of the frame
IN_ZONE = (10, 10, 100, 200)                          # centre x = 55 < 320
OUT_OF_ZONE = (400, 10, 500, 200)                     # centre x = 450 > 320


def teacher_engine():
    return new_engine({"teacher_check_enabled": True, "teacher_zone": ZONE})


def test_teacher_absent_raises_after_the_configured_time():
    engine = teacher_engine()
    events = run(engine, make_class(3), 0, 15, boxes=[OUT_OF_ZONE])

    assert ("raise", "TEACHER_ABSENT") in kinds(events)
    first = next(e for e in events if e[2] == "TEACHER_ABSENT")
    assert first[0] == 10


def test_person_in_zone_counts_as_teacher():
    engine = teacher_engine()
    assert run(engine, make_class(3), 0, 60, boxes=[IN_ZONE]) == []
    assert engine.get_status()["teacher_present"] is True


def test_empty_classroom_still_raises_teacher_absent():
    engine = teacher_engine()
    events = run(engine, [], 0, 15, boxes=[])

    assert kinds(events) == [("raise", "TEACHER_ABSENT")]


def test_teacher_returning_clears_after_5_seconds():
    engine = teacher_engine()
    run(engine, make_class(3), 0, 12, boxes=[])
    events = run(engine, make_class(3), 13, 30, boxes=[IN_ZONE])

    assert kinds(events) == [("clear", "TEACHER_ABSENT")]
    assert events[0][0] == 18


def test_teacher_check_is_off_by_default():
    engine = new_engine()
    assert run(engine, [], 0, 120, boxes=[]) == []


# ============================================================
# switches, schedule, sessions
# ============================================================

def test_no_events_without_an_active_session():
    engine = new_engine()
    engine.end_session(now=1)
    assert run(engine, make_class(3, eye="Sleeping"), 0, 60) == []


def test_disabled_engine_never_alerts():
    engine = new_engine({"enabled": False})
    assert run(engine, make_class(3, eye="Sleeping"), 0, 60) == []
    assert engine.get_status()["monitoring"] is False


def test_outside_schedule_no_alerts():
    # 1970-01-01 is a Thursday (3); only Monday is scheduled
    engine = new_engine({
        "schedule_enforced": True,
        "schedule": {"days": [0], "start": "09:00", "end": "17:00"},
    })
    assert run(engine, make_class(3, eye="Sleeping"), 0, 60) == []
    assert engine.get_status()["in_schedule"] is False


def test_ending_the_session_resolves_active_alerts():
    engine = new_engine()
    run(engine, make_class(3, eye="Close", emotion="Sad"), 0, 15)
    assert engine.get_status()["active_alert_count"] >= 1

    engine.end_session(now=20)

    assert engine.get_status()["active_alert_count"] == 0
    assert all(a["status"] == "resolved" for a in engine.get_alerts()["history"])


# ============================================================
# alert management
# ============================================================

def test_acknowledge_delete_and_clear():
    engine = new_engine()
    run(engine, make_class(3, eye="Close", emotion="Sad"), 0, 15)
    alert = engine.get_alerts()["active"][0]

    assert engine.delete(alert["id"]) == "active"          # cannot delete active
    assert engine.acknowledge(alert["id"]) is True
    assert engine.acknowledge("0" * 32) is False

    engine.end_session(now=30)
    assert engine.delete(alert["id"]) == "ok"
    assert engine.delete(alert["id"]) == "missing"

    run_engine = new_engine()
    run_engine.send_test_alert(now=1)
    run_engine.end_session(now=2)
    assert run_engine.clear_resolved() >= 1


def test_test_alert_closes_when_acknowledged():
    engine = new_engine()
    alert = engine.send_test_alert(now=5)
    engine.acknowledge(alert["id"], now=6)

    assert engine.get_alerts()["active"] == []


def test_every_alert_carries_class_and_session():
    engine = new_engine(class_id="room-7")
    run(engine, make_class(3, eye="Close", emotion="Sad"), 0, 15)
    alert = engine.get_alerts()["active"][0]

    assert alert["class_id"] == "room-7"
    assert alert["session_started_at"] == 0.0


# ============================================================
# persistence: SQLite and the JSON fallback
# ============================================================

def test_history_survives_a_restart_in_sqlite(tmp_path):
    store = Storage(str(tmp_path / "db.sqlite"))

    first = AlertEngine(
        data_dir=str(tmp_path / "a"), store=store, class_id="c1",
        notifier=lambda *a: None,
    )
    first.update_settings({
        "disengagement_seconds": 10, "smoothing_seconds": 5, "min_students": 1,
    })
    first.start_session(now=0.0, session_id="s" * 32)
    run(first, make_class(3, eye="Close", emotion="Sad"), 0, 12)

    # the server stops while the alert is still active
    second = AlertEngine(
        data_dir=str(tmp_path / "a"), store=store, class_id="c1",
        notifier=lambda *a: None,
    )
    history = second.get_alerts()["history"]

    assert len(history) >= 1
    assert history[0]["resolved_reason"] == "server_restart"
    assert history[0]["session_id"] == "s" * 32
    # settings come from settings.json
    assert second.get_settings()["disengagement_seconds"] == 10


def test_classes_do_not_share_alert_history(tmp_path):
    store = Storage(str(tmp_path / "db.sqlite"))
    a = AlertEngine(data_dir=None, store=store, class_id="a", notifier=lambda *x: None)
    b = AlertEngine(data_dir=None, store=store, class_id="b", notifier=lambda *x: None)

    a.send_test_alert(now=1)

    assert len(store.load_alerts("a")) == 1
    assert store.load_alerts("b") == []
    assert b.get_alerts()["active"] == []


def test_json_fallback_without_a_store(tmp_path):
    first = AlertEngine(data_dir=str(tmp_path), notifier=lambda *a: None)
    first.start_session(now=0)
    first.send_test_alert(now=1)

    second = AlertEngine(data_dir=str(tmp_path), notifier=lambda *a: None)
    assert len(second.get_alerts()["history"]) == 1


def test_legacy_alerts_json_is_imported_into_sqlite_once(tmp_path):
    legacy = AlertEngine(data_dir=str(tmp_path), notifier=lambda *a: None)
    legacy.start_session(now=0)
    legacy.send_test_alert(now=1)
    legacy.end_session(now=2)

    store = Storage(str(tmp_path / "db.sqlite"))
    migrated = AlertEngine(data_dir=str(tmp_path), store=store, notifier=lambda *a: None)

    assert len(migrated.get_alerts()["history"]) == 1
    assert store.count_alerts("default") == 1

    again = AlertEngine(data_dir=str(tmp_path), store=store, notifier=lambda *a: None)
    assert store.count_alerts("default") == 1


# ============================================================
# settings validation
# ============================================================

def test_default_thresholds_are_the_agreed_values():
    assert DEFAULT_SETTINGS["disengagement_threshold"] == 50
    assert DEFAULT_SETTINGS["disengagement_seconds"] == 120
    assert DEFAULT_SETTINGS["drowsy_share_threshold"] == 30
    assert DEFAULT_SETTINGS["teacher_absent_seconds"] == 60
    assert alerts.HYSTERESIS_POINTS == 5
    assert alerts.CLEAR_SECONDS == 20


@pytest.mark.parametrize("patch, message", [
    ({"enabled": "yes"}, "true or false"),
    ({"disengagement_threshold": 5}, "between 10 and 90"),
    ({"disengagement_threshold": 95}, "between 10 and 90"),
    ({"drowsy_seconds": "10"}, "must be a number"),
    ({"drowsy_seconds": True}, "must be a number"),
    ({"nope": 1}, "Unknown setting"),
    ({"notify_email": "not-an-email"}, "e-mail"),
    ({"teacher_check_enabled": True}, "teacher zone"),
    ({"teacher_zone": {"x1": 0.6, "y1": 0, "x2": 0.4, "y2": 1}}, ""),
])
def test_invalid_settings_are_rejected(patch, message):
    with pytest.raises(ValueError) as error:
        validate_settings(patch, DEFAULT_SETTINGS)
    assert message in str(error.value)


def test_valid_settings_are_merged_and_rounded():
    merged = validate_settings(
        {"disengagement_threshold": 49.6, "notify_email": " a@b.co "},
        DEFAULT_SETTINGS,
    )
    assert merged["disengagement_threshold"] == 50
    assert merged["notify_email"] == "a@b.co"
    assert DEFAULT_SETTINGS["disengagement_threshold"] == 50   # not mutated


def test_non_object_patch_is_rejected():
    with pytest.raises(ValueError):
        validate_settings([1, 2], DEFAULT_SETTINGS)
