"""Temporal eye-state logic (no TensorFlow, so it is easy to test).

Turns the raw per-frame Open / Close reading of each tracked face into
Open / Blink / Close / Drowsy / Sleeping:

    closed < BLINK_MAX_DURATION               -> "Close"  (maybe a blink)
    BLINK_MAX_DURATION <= closed < SLEEPING   -> "Drowsy"
    closed >= SLEEPING_THRESHOLD              -> "Sleeping"
    eyes re-open after a closure < BLINK_MAX  -> "Blink" for BLINK_DISPLAY_DURATION

Calibration (point 14)
----------------------
The three durations can be tuned per deployment without editing code:

    EYE_BLINK_MAX_SECONDS    default 0.8
    EYE_SLEEPING_SECONDS     default 3.0
    EYE_BLINK_DISPLAY_SECONDS  default 0.5

Each EyeTracker is independent, so every class / camera gets its own
(point 12) and the clock can be replaced in tests.
"""

import logging
import math
import os
import threading
import time

logger = logging.getLogger(__name__)


def _env_float(name, default):

    raw = os.environ.get(name)

    if raw is None or raw.strip() == "":
        return default

    try:
        value = float(raw)
    except ValueError:
        logger.warning("Ignoring invalid %s=%r", name, raw)
        return default

    if not math.isfinite(value) or value <= 0:
        logger.warning("Ignoring non-positive %s=%r", name, raw)
        return default

    return value


BLINK_MAX_DURATION = _env_float("EYE_BLINK_MAX_SECONDS", 0.8)
SLEEPING_THRESHOLD = _env_float("EYE_SLEEPING_SECONDS", 3.0)
BLINK_DISPLAY_DURATION = _env_float("EYE_BLINK_DISPLAY_SECONDS", 0.5)

if SLEEPING_THRESHOLD <= BLINK_MAX_DURATION:
    logger.warning(
        "EYE_SLEEPING_SECONDS (%s) must be larger than "
        "EYE_BLINK_MAX_SECONDS (%s); using the defaults.",
        SLEEPING_THRESHOLD, BLINK_MAX_DURATION,
    )
    BLINK_MAX_DURATION = 0.8
    SLEEPING_THRESHOLD = 3.0

# A track that was not seen for this long is forgotten.
TRACK_STALE_SECONDS = 2.0
# A face closer than this many pixels to an old track is the same person.
TRACK_MATCH_DISTANCE = 120


class EyeTracker:
    """Short-lived face tracks + the Open/Blink/Drowsy/Sleeping state machine
    for ONE camera. Thread safe."""

    def __init__(self, clock=time.time):

        self._clock = clock
        self._lock = threading.Lock()
        self.tracks = {}
        self._next_track_id = 0

    # --------------------------------------------------------

    def get_track_id(self, center_x, center_y):
        """Associate a face position with a short-lived track id."""

        now = self._clock()

        with self._lock:

            for track_id in [
                tid for tid, track in self.tracks.items()
                if now - track["last_seen"] > TRACK_STALE_SECONDS
            ]:
                del self.tracks[track_id]

            best_id = None
            best_distance = float("inf")

            for track_id, track in self.tracks.items():

                distance = math.hypot(
                    center_x - track["center_x"],
                    center_y - track["center_y"],
                )

                if distance < best_distance and distance < TRACK_MATCH_DISTANCE:
                    best_distance = distance
                    best_id = track_id

            if best_id is None:

                best_id = self._next_track_id
                self._next_track_id += 1

                self.tracks[best_id] = {
                    "center_x": center_x,
                    "center_y": center_y,
                    "last_seen": now,
                    "previous_raw_state": "Unknown",
                    "closed_since": None,
                    "blink_until": 0,
                    "was_sleeping": False,
                }

            else:

                track = self.tracks[best_id]
                track["center_x"] = center_x
                track["center_y"] = center_y
                track["last_seen"] = now

            return best_id

    # --------------------------------------------------------

    def update_display_state(self, track_id, raw_state):
        """Convert a raw reading into Open/Close/Blink/Drowsy/Sleeping."""

        now = self._clock()

        with self._lock:

            track = self.tracks.get(track_id)

            if track is None:
                return raw_state

            previous_state = track["previous_raw_state"]

            if raw_state == "Close":

                if previous_state != "Close":
                    track["closed_since"] = now

                closed_for = (
                    now - track["closed_since"]
                    if track["closed_since"] is not None else 0
                )

                track["previous_raw_state"] = "Close"

                if closed_for >= SLEEPING_THRESHOLD:
                    track["was_sleeping"] = True
                    return "Sleeping"

                if closed_for >= BLINK_MAX_DURATION:
                    return "Drowsy"

                return "Close"

            if raw_state == "Open":

                closed_for = (
                    now - track["closed_since"]
                    if track["closed_since"] is not None else 0
                )

                track["previous_raw_state"] = "Open"
                track["closed_since"] = None

                if track["was_sleeping"]:
                    track["was_sleeping"] = False
                    track["blink_until"] = 0
                    return "Open"

                if 0 < closed_for < BLINK_MAX_DURATION:
                    track["blink_until"] = now + BLINK_DISPLAY_DURATION
                    return "Blink"

                if now < track["blink_until"]:
                    return "Blink"

                return "Open"

            return "Unknown"

    # --------------------------------------------------------

    def reset(self):
        """Forget every track (start / end of a camera session)."""

        with self._lock:
            self.tracks.clear()
            self._next_track_id = 0
