"""Open / Blink / Close / Drowsy / Sleeping rules and their thresholds
(0.8 s drowsy, 3 s sleeping, 0.5 s blink display)."""

import importlib

import pytest

import eye_state
from eye_state import EyeTracker


@pytest.fixture
def tracker(clock):
    t = EyeTracker(clock=clock)
    track_id = t.get_track_id(100, 100)
    return t, track_id


def feed(tracker_and_id, clock, raw, advance=0.0):
    tracker, track_id = tracker_and_id
    clock.advance(advance)
    return tracker.update_display_state(track_id, raw)


def test_default_thresholds_are_the_agreed_values():
    assert eye_state.BLINK_MAX_DURATION == 0.8
    assert eye_state.SLEEPING_THRESHOLD == 3.0
    assert eye_state.BLINK_DISPLAY_DURATION == 0.5


def test_open_eyes_stay_open(tracker, clock):
    assert feed(tracker, clock, "Open") == "Open"
    assert feed(tracker, clock, "Open", 5) == "Open"


def test_short_closure_is_close_then_blink_when_reopened(tracker, clock):
    assert feed(tracker, clock, "Close") == "Close"
    assert feed(tracker, clock, "Close", 0.5) == "Close"
    assert feed(tracker, clock, "Open", 0.1) == "Blink"      # 0.6 s closed


def test_blink_is_shown_for_half_a_second(tracker, clock):
    feed(tracker, clock, "Close")
    assert feed(tracker, clock, "Open", 0.3) == "Blink"
    assert feed(tracker, clock, "Open", 0.4) == "Blink"      # 0.4 s after
    assert feed(tracker, clock, "Open", 0.2) == "Open"       # 0.6 s after


@pytest.mark.parametrize("closed_for, expected", [
    (0.79, "Close"),
    (0.80, "Drowsy"),          # threshold is inclusive
    (2.99, "Drowsy"),
    (3.00, "Sleeping"),        # threshold is inclusive
    (10.0, "Sleeping"),
])
def test_closure_duration_thresholds(tracker, clock, closed_for, expected):
    feed(tracker, clock, "Close")
    assert feed(tracker, clock, "Close", closed_for) == expected


def test_closure_of_exactly_the_blink_limit_is_not_a_blink(tracker, clock):
    feed(tracker, clock, "Close")
    clock.advance(0.8)
    assert feed(tracker, clock, "Open") == "Open"


def test_waking_up_after_sleeping_is_open_not_blink(tracker, clock):
    feed(tracker, clock, "Close")
    assert feed(tracker, clock, "Close", 4) == "Sleeping"
    assert feed(tracker, clock, "Open", 0.1) == "Open"
    assert feed(tracker, clock, "Open", 0.1) == "Open"


def test_unknown_raw_state_is_unknown(tracker, clock):
    assert feed(tracker, clock, "Unknown") == "Unknown"


def test_unknown_track_returns_raw_state(clock):
    assert EyeTracker(clock=clock).update_display_state(99, "Close") == "Close"


# ------------------------------------------------------------
# tracks
# ------------------------------------------------------------

def test_same_face_keeps_its_track_id(clock):
    t = EyeTracker(clock=clock)
    first = t.get_track_id(100, 100)
    clock.advance(0.5)
    assert t.get_track_id(130, 110) == first          # moved 31 px


def test_far_face_gets_a_new_track_id(clock):
    t = EyeTracker(clock=clock)
    first = t.get_track_id(100, 100)
    assert t.get_track_id(100 + eye_state.TRACK_MATCH_DISTANCE + 1, 100) != first


def test_stale_track_is_forgotten(clock):
    t = EyeTracker(clock=clock)
    first = t.get_track_id(100, 100)
    clock.advance(eye_state.TRACK_STALE_SECONDS + 0.1)
    assert t.get_track_id(100, 100) != first


def test_reset_clears_tracks_and_ids(clock):
    t = EyeTracker(clock=clock)
    t.get_track_id(1, 1)
    t.reset()
    assert t.tracks == {}
    assert t.get_track_id(500, 500) == 0


def test_two_classes_do_not_share_tracks(clock):
    a, b = EyeTracker(clock=clock), EyeTracker(clock=clock)
    a.get_track_id(100, 100)
    assert b.tracks == {}


# ------------------------------------------------------------
# calibration through environment variables
# ------------------------------------------------------------

@pytest.fixture
def reload_eye_state(monkeypatch):
    def _reload(**env):
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        return importlib.reload(eye_state)

    yield _reload

    monkeypatch.undo()
    importlib.reload(eye_state)


def test_thresholds_can_be_tuned_with_environment_variables(reload_eye_state):
    module = reload_eye_state(
        EYE_BLINK_MAX_SECONDS="1.2", EYE_SLEEPING_SECONDS="5"
    )
    assert module.BLINK_MAX_DURATION == 1.2
    assert module.SLEEPING_THRESHOLD == 5.0


def test_invalid_or_inconsistent_values_fall_back_to_defaults(reload_eye_state):
    module = reload_eye_state(EYE_BLINK_MAX_SECONDS="abc")
    assert module.BLINK_MAX_DURATION == 0.8

    module = reload_eye_state(
        EYE_BLINK_MAX_SECONDS="4", EYE_SLEEPING_SECONDS="2"
    )
    assert (module.BLINK_MAX_DURATION, module.SLEEPING_THRESHOLD) == (0.8, 3.0)
