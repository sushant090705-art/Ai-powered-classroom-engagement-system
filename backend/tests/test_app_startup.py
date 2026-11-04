"""The real Flask app starts (no circular imports) and exposes every route."""

import sys
import types


def test_create_app_registers_all_routes(fake_models, monkeypatch):
    # app.py -> auth.py -> database.py would connect to MongoDB Atlas
    fake_database = types.ModuleType("database")
    fake_database.users = object()
    monkeypatch.setitem(sys.modules, "database", fake_database)

    try:
        import flask_cors  # noqa: F401
    except ImportError:         # optional here; the real app needs it
        stub = types.ModuleType("flask_cors")
        stub.CORS = lambda app: None
        monkeypatch.setitem(sys.modules, "flask_cors", stub)
    sys.modules.pop("app", None)

    import app as backend_app

    routes = {rule.rule for rule in backend_app.app.url_map.iter_rules()}

    for expected in (
        "/camera/connect", "/camera/status", "/camera/disconnect", "/classes",
        "/video_feed", "/emotion-results", "/analytics", "/analytics/reset",
        "/alerts", "/alerts/status", "/alerts/settings", "/reports",
        "/reports/<report_id>", "/history/sessions",
        "/history/sessions/<session_id>/samples", "/students/report",
        "/analyze-video", "/analyze-video/status/<job_id>",
    ):
        assert expected in routes, expected

    sys.modules.pop("app", None)
