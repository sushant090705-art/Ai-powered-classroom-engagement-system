"""The engagement / attention formulas (analytics.py)."""

import pytest

from analytics import (
    AnalyticsSession,
    annotate_engagement,
    calculate_attention_score,
    calculate_engagement_score,
    engagement_level,
)


def score(eye, emotion):
    return calculate_engagement_score({"eye_state": eye, "emotion": emotion})


@pytest.mark.parametrize("eye, emotion, expected", [
    # 65 % eye + 35 % emotion
    ("Open", "Happy", 85),         # 55.25 + 29.75
    ("Open", "Neutral", 80),       # 55.25 + 24.5  = 79.75
    ("Blink", "Neutral", 70),      # 45.5  + 24.5
    ("Close", "Neutral", 47),      # 22.75 + 24.5  = 47.25
    ("Drowsy", "Sad", 25),         # 13    + 12.25 = 25.25
    ("Sleeping", "Sad", 16),       # 3.25  + 12.25 = 15.5
    ("Unknown", "Unknown", 50),    # unknown values fall back to 50
])
def test_engagement_score_values(eye, emotion, expected):
    assert score(eye, emotion) == expected


def test_missing_keys_use_defaults():
    # eye "Unknown" (50) and emotion "Neutral" (70)
    assert calculate_engagement_score({}) == round(50 * 0.65 + 70 * 0.35)


def test_score_stays_between_0_and_100():
    for eye in ("Open", "Blink", "Close", "Drowsy", "Sleeping", "Unknown", "x"):
        for emotion in ("Happy", "Neutral", "Sad", "Angry", "x"):
            assert 0 <= score(eye, emotion) <= 100


def test_sleeping_is_less_engaged_than_awake():
    assert score("Sleeping", "Happy") < score("Close", "Happy") < score("Open", "Happy")


@pytest.mark.parametrize("eye, expected", [
    ("Open", 100), ("Blink", 85), ("Close", 35),
    ("Drowsy", 15), ("Sleeping", 0), ("Unknown", 50), ("???", 50),
])
def test_attention_score(eye, expected):
    assert calculate_attention_score({"eye_state": eye}) == expected


@pytest.mark.parametrize("value, level", [
    (100, "Engaged"), (75, "Engaged"), (74, "Moderate"),
    (50, "Moderate"), (49, "Low"), (0, "Low"),
])
def test_engagement_level_boundaries(value, level):
    assert engagement_level(value) == level


def test_annotate_engagement_does_not_touch_the_input():
    faces = [{"eye_state": "Open", "emotion": "Happy"}]
    out = annotate_engagement(faces)

    assert out[0]["engagement"] == 85
    assert out[0]["engagement_level"] == "Engaged"
    assert "engagement" not in faces[0]
    assert annotate_engagement(None) == []


# ------------------------------------------------------------
# AnalyticsSession (per class)
# ------------------------------------------------------------

def test_session_averages_and_distributions():
    session = AnalyticsSession(wall_clock=False)
    session.start(0.0)

    session.record([
        {"eye_state": "Open", "emotion": "Happy"},
        {"eye_state": "Sleeping", "emotion": "Sad"},
    ], now=0.0)

    snap = session.snapshot()

    assert snap["total_samples"] == 1
    assert snap["peak_students"] == 2
    assert snap["overall_engagement"] == round((85 + 15.5) / 2)
    assert snap["attention"] == 50
    assert snap["emotion_distribution"] == {"Happy": 50, "Sad": 50}
    assert snap["attention_distribution"] == {"Open": 50, "Sleeping": 50}


def test_trend_point_every_five_seconds():
    session = AnalyticsSession(wall_clock=False)
    session.start(0.0)

    for t in (0.0, 1.0, 4.9, 5.0, 9.0, 10.0):
        session.record([{"eye_state": "Open", "emotion": "Happy"}], now=t)

    assert [p["time"] for p in session.snapshot()["engagement_trend"]] == [
        "00:00", "00:05", "00:10",
    ]


def test_empty_cycle_resets_live_count_but_keeps_averages():
    session = AnalyticsSession(wall_clock=False)
    session.start(0.0)
    session.record([{"eye_state": "Open", "emotion": "Happy"}], now=0.0)
    session.record([], now=1.0)

    payload = session.payload()

    assert payload["active_students"] == 0
    assert payload["overall_engagement"] == 85


def test_sessions_are_independent_per_class():
    a, b = AnalyticsSession("a", False), AnalyticsSession("b", False)
    a.start(0.0)
    b.start(0.0)
    a.record([{"eye_state": "Open", "emotion": "Happy"}], now=0.0)

    assert a.snapshot()["total_samples"] == 1
    assert b.snapshot()["total_samples"] == 0
