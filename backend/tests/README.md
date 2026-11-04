# Backend tests

```
cd backend
pip install -r requirements-dev.txt
python -m pytest tests
```

No camera, TensorFlow, YOLO or MongoDB is needed: `conftest.py` sends all data
to a temp folder and `fake_models` replaces the AI models with small fakes.

| File | What it checks |
|---|---|
| `test_engagement_formulas.py` | engagement / attention scores, Engaged-Moderate-Low cut-offs, per-class analytics |
| `test_eye_state.py` | Blink / Drowsy (0.8 s) / Sleeping (3 s) rules, face tracks, threshold tuning via env vars |
| `test_alert_engine.py` | hold times, the 50 % threshold, hysteresis, 30 % drowsy share, teacher zone, schedule, persistence, settings validation |
| `test_storage.py` | SQLite sessions / students / samples / alerts, cascade delete, legacy import |
| `test_pipeline.py` | shared engine: live + recorded video use the same code, several classes at once |
| `test_routes.py` | HTTP API: several cameras, per-class settings, reports and history |
| `test_app_startup.py` | the real app imports and registers every route |

## Calibrating the thresholds (point 14)

The agreed defaults are pinned by tests, so changing one is a deliberate act.
They can be tuned per deployment without editing code:

* eye timing: `EYE_BLINK_MAX_SECONDS` (0.8), `EYE_SLEEPING_SECONDS` (3.0),
  `EYE_BLINK_DISPLAY_SECONDS` (0.5)
* alert thresholds: per class via `PUT /alerts/settings?class_id=...`
  (`disengagement_threshold` 50 %, `disengagement_seconds`, `drowsy_share_threshold`
  30 %, `drowsy_seconds`, `teacher_absent_seconds`, ...)

To find good values, analyse a few real recorded lectures with
`POST /analyze-video`: the response lists the alerts that would have fired
(`alerts`, in video seconds), so thresholds can be compared with what a teacher
would consider a real problem.
