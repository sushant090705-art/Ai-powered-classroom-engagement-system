"""The shared engine: live and recorded video use the same code (point 13),
and several classes run independently (point 12). The AI models are fakes
(see conftest.fake_models)."""

import os
import sys

import cv2
import numpy as np
import pytest

from conftest import make_class, make_result

# ------------------------------------------------------------
# detection pipeline
# ------------------------------------------------------------

def test_process_frame_finds_faces_and_person_boxes(fake_models):
    import ai_processing
    from eye_state import EyeTracker

    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    boxes = []

    results = ai_processing.process_frame(
        frame, tracker=EyeTracker(), person_boxes=boxes
    )

    assert boxes == [(5, 5, 315, 235)]
    assert len(results) == 2
    assert results[0]["emotion"] == "Happy"
    assert results[0]["eye_state"] == "Open"
    assert results[0]["x"] == 15 and results[0]["y"] == 15      # crop + face offset


def test_each_tracker_has_its_own_tracks(fake_models):
    import ai_processing
    from eye_state import EyeTracker

    a, b = EyeTracker(), EyeTracker()
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    ai_processing.process_frame(frame, tracker=a)

    assert len(a.tracks) == 2
    assert b.tracks == {}


# ------------------------------------------------------------
# ClassEngine.ingest
# ------------------------------------------------------------

def video_engine(**settings):
    from engine import ClassEngine

    base = {"drowsy_seconds": 10, "disengagement_seconds": 10,
            "smoothing_seconds": 5, "min_students": 2}
    base.update(settings)
    engine = ClassEngine.video(alert_settings=base)
    engine.start_session(now=0.0)
    return engine


def test_ingest_feeds_students_analytics_and_alerts():
    engine = video_engine()

    for t in range(0, 15):
        engine.ingest(make_class(3, eye="Close", emotion="Sad"),
                      [], (480, 640, 3), now=float(t))

    assert engine.registry.build_reports(min_samples=1)["students_total"] == 3
    assert engine.analytics.snapshot()["total_samples"] == 15
    types = {a["type"] for a in engine.alert_engine.get_alerts()["active"]}
    assert "LOW_ENGAGEMENT" in types


def test_face_hook_can_rewrite_the_eye_state_before_alerts():
    engine = video_engine()

    def hook(student_id, face, now):
        face["eye_state"] = "Sleeping"

    for t in range(0, 15):
        out = engine.ingest(make_class(3), [], (480, 640, 3), now=float(t), face_hook=hook)

    assert all(r["eye_state"] == "Sleeping" for r in out)
    types = {a["type"] for a in engine.alert_engine.get_alerts()["active"]}
    assert "CLASS_DROWSY" in types


def test_video_engine_ignores_the_wall_clock_schedule():
    engine = video_engine(schedule_enforced=True,
                          schedule={"days": [0], "start": "00:00", "end": "00:01"})
    assert engine.alert_engine.get_settings()["schedule_enforced"] is False


def test_video_engine_never_writes_to_the_database():
    engine = video_engine()
    assert engine.store is None


# ------------------------------------------------------------
# several classes at once
# ------------------------------------------------------------

def test_classes_have_separate_engines_students_and_alerts():
    import engine as engine_module
    from alerts import get_alert_engine

    one = engine_module.get_class_engine("room-1")
    two = engine_module.get_class_engine("room-2")
    assert one is not two
    assert engine_module.get_class_engine("room-1") is one

    one.start_session()
    two.start_session()

    for i in range(20):
        one.ingest(make_class(3, eye="Close", emotion="Sad"), [], (480, 640, 3), now=float(i))
        two.ingest(make_class(3), [], (480, 640, 3), now=float(i))

    assert one.analytics.snapshot()["overall_engagement"] < 50
    assert two.analytics.snapshot()["overall_engagement"] > 80
    assert one.registry is not two.registry
    assert get_alert_engine("room-1") is not get_alert_engine("room-2")
    assert get_alert_engine("room-2").get_alerts()["active"] == []

    one.stop()
    two.stop()


def test_live_samples_are_written_to_sqlite_every_few_seconds():
    import engine as engine_module
    from storage import get_storage

    live = engine_module.get_class_engine("sampled")
    live.start_session()

    for i in range(0, 21):
        live.ingest(make_class(2), [], (480, 640, 3), now=1000.0 + i)

    samples = get_storage().get_samples(live.session_id)
    assert [s["ts"] for s in samples] == [1000.0, 1005.0, 1010.0, 1015.0, 1020.0]
    assert samples[0]["students"] == 2
    live.stop()


def test_invalid_class_ids_are_rejected():
    from class_id import normalize_class_id

    assert normalize_class_id(None) == "default"
    assert normalize_class_id("  ") == "default"
    assert normalize_class_id("grade-5_A") == "grade-5_A"

    for bad in ("../etc", "a b", "x" * 41, "a/b", "ä"):
        with pytest.raises(ValueError):
            normalize_class_id(bad)


# ------------------------------------------------------------
# recorded video through the shared engine
# ------------------------------------------------------------

def write_test_video(path, seconds=40, fps=10, closed_from=2.0):
    """A video whose frames are black (eyes open) and, from `closed_from`
    seconds on, white (the fake eye model reads bright crops as closed)."""

    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), fps, (320, 240))

    if not writer.isOpened():
        pytest.skip("OpenCV cannot write test videos here")

    for i in range(seconds * fps):
        value = 255 if i / fps >= closed_from else 128
        writer.write(np.full((240, 320, 3), value, dtype=np.uint8))

    writer.release()


def test_recorded_video_uses_the_same_pipeline_and_raises_alerts(fake_models, tmp_path):
    import recorded_video

    from alerts import get_alert_engine

    # The class's own thresholds are applied to the video (default is 60 s).
    get_alert_engine("lecture").update_settings({
        "drowsy_seconds": 10, "smoothing_seconds": 5,
        "drowsy_share_threshold": 30,
    })

    path = str(tmp_path / "lecture.avi")
    write_test_video(path)

    result = recorded_video.analyze_video_file(path, class_id="lecture")

    # per-student reports (as before)
    assert result["total_students"] == 2
    assert result["processed_frames"] > 40

    # eyes closed from 2 s on -> Sleeping after 3 s (video clock), so more than
    # 30 % of the class looks drowsy for longer than 10 s
    alert_types = {a["type"] for a in result["alerts"]}
    assert "CLASS_DROWSY" in alert_types

    drowsy = next(a for a in result["alerts"] if a["type"] == "CLASS_DROWSY")
    assert 5 < drowsy["started_at"] < 35          # video seconds, not epoch
    assert result["class_analytics"]["total_samples"] > 0



def test_recorded_video_of_awake_students_raises_nothing(fake_models, tmp_path):
    import recorded_video

    path = str(tmp_path / "awake.avi")
    write_test_video(path, seconds=30, closed_from=10_000)

    result = recorded_video.analyze_video_file(path)

    assert result["alerts"] == []
    assert result["total_students"] == 2


def test_recorded_video_does_not_disturb_a_running_live_class(fake_models, tmp_path):
    import engine as engine_module
    import recorded_video

    live = engine_module.get_class_engine("live-during-video")
    live.start_session()
    before = live.analytics.snapshot()["total_samples"]

    path = str(tmp_path / "v.avi")
    write_test_video(path, seconds=10)
    recorded_video.analyze_video_file(path, class_id="live-during-video")

    assert live.analytics.snapshot()["total_samples"] == before
    assert live.tracker.tracks == {}
    live.stop()
