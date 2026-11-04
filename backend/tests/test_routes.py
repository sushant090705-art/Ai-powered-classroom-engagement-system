"""HTTP API: several cameras / classes at once (point 12), reports in SQLite
(point 11). OpenCV capture and the AI models are fakes."""

import time

import numpy as np
import pytest
from flask import Flask

from conftest import make_class


class FakeCapture:
    def __init__(self, *args, **kwargs):
        self.opened = True

    def isOpened(self):
        return self.opened

    def read(self):
        return True, np.zeros((240, 320, 3), dtype=np.uint8)

    def set(self, *args):
        return True

    def release(self):
        self.opened = False


@pytest.fixture
def client(fake_models, monkeypatch):
    import camera
    from alerts import alerts_bp
    from analytics import analytics_bp
    from reports import reports_bp
    from recorded_video import recorded_video_bp

    monkeypatch.setattr(camera.cv2, "VideoCapture", FakeCapture)
    camera._sources.clear()

    app = Flask(__name__)
    for blueprint in (camera.camera_bp, alerts_bp, analytics_bp,
                      reports_bp, recorded_video_bp):
        app.register_blueprint(blueprint)

    yield app.test_client()

    for class_id in list(camera._sources):
        app.test_client().post("/camera/disconnect", json={"class_id": class_id})


def connect(client, class_id=None, index=0):
    body = {"type": "webcam", "index": index}
    if class_id:
        body["class_id"] = class_id
    return client.post("/camera/connect", json=body)


# ------------------------------------------------------------
# cameras
# ------------------------------------------------------------

def test_original_single_camera_api_still_works_without_class_id(client):
    response = connect(client)

    assert response.status_code == 200
    assert response.get_json()["class_id"] == "default"

    status = client.get("/camera/status").get_json()
    assert status["connected"] is True
    assert status["type"] == "webcam"

    assert client.post("/camera/disconnect").get_json()["success"] is True
    assert client.get("/camera/status").get_json()["connected"] is False


def test_two_cameras_run_independently(client):
    assert connect(client, "room-a", 0).status_code == 200
    assert connect(client, "room-b", 1).status_code == 200

    classes = {c["class_id"]: c for c in client.get("/classes").get_json()["classes"]}
    assert classes["room-a"]["connected"] and classes["room-b"]["connected"]
    assert classes["room-a"]["session_active"] and classes["room-b"]["session_active"]

    client.post("/camera/disconnect", json={"class_id": "room-a"})

    assert client.get("/camera/status?class_id=room-a").get_json()["connected"] is False
    assert client.get("/camera/status?class_id=room-b").get_json()["connected"] is True


def test_camera_limit_is_enforced(client, monkeypatch):
    import camera
    monkeypatch.setattr(camera, "MAX_LIVE_CAMERAS", 1)

    assert connect(client, "one").status_code == 200
    refused = connect(client, "two", 1)

    assert refused.status_code == 409
    assert "At most 1" in refused.get_json()["message"]
    # reconnecting the SAME class is still allowed
    assert connect(client, "one").status_code == 200


def test_bad_class_id_is_a_400(client):
    assert connect(client, "../evil").status_code == 400
    assert client.get("/camera/status?class_id=a%20b").status_code == 400
    assert client.get("/analytics?class_id=a/b").status_code == 400
    assert client.get("/alerts?class_id=a/b").status_code == 400


def test_failed_connection_reports_500_and_forgets_the_source(client, monkeypatch):
    import camera

    class Broken(FakeCapture):
        def __init__(self, *a, **k):
            self.opened = False

    monkeypatch.setattr(camera.cv2, "VideoCapture", Broken)

    assert connect(client, "bad").status_code == 500
    assert client.get("/camera/status?class_id=bad").get_json()["connected"] is False


# ------------------------------------------------------------
# per-class analytics and alerts through the API
# ------------------------------------------------------------

def test_analytics_and_alerts_are_per_class(client):
    import engine as engine_module

    connect(client, "math", 0)

    math = engine_module.get_class_engine("math")
    for i in range(10):
        math.analytics.record(make_class(2), now=time.time() + i)

    assert client.get("/analytics?class_id=math").get_json()["session_active"] is True
    assert client.get("/analytics?class_id=art").get_json()["session_active"] is False

    # thresholds are per class
    saved = client.put("/alerts/settings?class_id=math",
                       json={"disengagement_threshold": 40}).get_json()
    assert saved["settings"]["disengagement_threshold"] == 40
    other = client.get("/alerts/settings?class_id=art").get_json()
    assert other["settings"]["disengagement_threshold"] == 50

    assert client.post("/alerts/test?class_id=math").get_json()["success"]
    assert len(client.get("/alerts?class_id=math").get_json()["active"]) == 1
    assert client.get("/alerts?class_id=art").get_json()["active"] == []


# ------------------------------------------------------------
# reports + history in SQLite
# ------------------------------------------------------------

def test_session_report_is_saved_listed_compared_and_deleted(client):
    import engine as engine_module

    connect(client, "history", 0)
    live = engine_module.get_class_engine("history")

    # feed deterministic data on top of whatever the AI thread produced
    for i in range(12):
        live.ingest(make_class(3), [], (240, 320, 3))

    disconnect = client.post("/camera/disconnect", json={"class_id": "history"}).get_json()
    report = disconnect["report"]

    assert report is not None
    assert report["class_id"] == "history"
    assert report["id"] == live.session_id           # report id == session id

    listed = client.get("/reports?class_id=history").get_json()["reports"]
    assert [r["id"] for r in listed] == [report["id"]]
    assert "engagement_levels" in listed[0]
    assert client.get("/reports?class_id=other").get_json()["reports"] == []

    full = client.get(f"/reports/{report['id']}").get_json()["report"]
    assert len(full["students"]) == 3

    history = client.get("/history/sessions?class_id=history").get_json()["sessions"]
    assert history[0]["id"] == report["id"]

    samples = client.get(f"/history/sessions/{report['id']}/samples").get_json()["samples"]
    assert len(samples) >= 1

    assert client.delete(f"/reports/{report['id']}").get_json()["success"]
    assert client.get(f"/reports/{report['id']}").status_code == 404
    assert client.delete(f"/reports/{report['id']}").status_code == 404


def test_session_without_students_saves_nothing_and_leaves_no_rows(client):
    from storage import get_storage

    connect(client, "empty", 0)
    result = client.post("/camera/disconnect", json={"class_id": "empty"}).get_json()

    # the AI thread may or may not have run; with no real student -> None
    if result["report"] is None:
        assert get_storage().list_sessions("empty") == []
        assert get_storage()._query(
            "SELECT * FROM sessions WHERE class_id = 'empty'") == []


def test_bad_report_ids_are_404(client):
    assert client.get("/reports/not-an-id").status_code == 404
    assert client.get("/reports/" + "0" * 32).status_code == 404
    assert client.delete("/reports/../../etc").status_code in (404, 405)
