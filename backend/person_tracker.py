"""ByteTrack person tracker (one instance per ClassEngine).

YOLO only *detects* people frame by frame. This wrapper runs ByteTrack on
those detections so the same physical person keeps the same `person_id`
across frames. Student reports (student_reports.py) key on that id.

Rules:
  * One PersonTracker per class / camera / video. Never share one between
    classes, otherwise their tracks get mixed.
  * Import-safe: ultralytics is imported lazily. If ByteTrack is missing or
    fails, update() returns the plain YOLO boxes with person_id = None and the
    old IoU matching in StudentRegistry takes over.
  * Works with different ultralytics versions: the constructor arguments are
    looked up with inspect, and the tracker settings start from ultralytics'
    own bytetrack.yaml.
"""

import inspect
import logging
from types import SimpleNamespace

logger = logging.getLogger(__name__)

# The AI loop runs at ~2 FPS (not 30). ByteTrack counts its buffer in
# frames, so with frame_rate=30 a track is kept for `track_buffer` frames:
# 20 frames at ~2 FPS = ~10 seconds of occlusion before the id is dropped.
DEFAULT_TRACK_BUFFER = 20
DEFAULT_MATCH_THRESH = 0.85      # looser than 0.8: boxes move more at 2 FPS

_FALLBACK_SETTINGS = {
    "tracker_type": "bytetrack",
    "track_high_thresh": 0.40,   # same as YOLO conf in process_frame
    "track_low_thresh": 0.10,
    "new_track_thresh": 0.45,
    "track_buffer": DEFAULT_TRACK_BUFFER,
    "match_thresh": DEFAULT_MATCH_THRESH,
    "fuse_score": True,
    "mot20": False,
}


def _plain_boxes(boxes):
    """YOLO boxes -> [(x1, y1, x2, y2, None)] (no tracking)."""

    out = []

    for box in boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        out.append((x1, y1, x2, y2, None))

    return out


def _load_settings(track_buffer, match_thresh):
    """ultralytics' own bytetrack.yaml (right keys for THIS version), with
    our two overrides on top. Falls back to built-in defaults."""

    settings = dict(_FALLBACK_SETTINGS)

    try:
        from pathlib import Path

        import ultralytics
        import yaml

        path = (
            Path(ultralytics.__file__).parent
            / "cfg" / "trackers" / "bytetrack.yaml"
        )

        with open(path, "r", encoding="utf-8") as handle:
            settings.update(yaml.safe_load(handle) or {})

    except Exception:
        logger.warning(
            "Could not read ultralytics bytetrack.yaml - using built-in "
            "tracker settings"
        )

    settings["track_buffer"] = track_buffer
    settings["match_thresh"] = match_thresh

    return SimpleNamespace(**settings)


class PersonTracker:

    def __init__(
        self,
        track_buffer=DEFAULT_TRACK_BUFFER,
        match_thresh=DEFAULT_MATCH_THRESH,
    ):

        self._track_buffer = track_buffer
        self._match_thresh = match_thresh

        self._tracker = None
        self._create()

    # --------------------------------------------------------

    def _create(self):

        try:
            from ultralytics.trackers.byte_tracker import BYTETracker

            args = _load_settings(self._track_buffer, self._match_thresh)

            # Some versions take frame_rate, some fps, some neither.
            params = inspect.signature(BYTETracker.__init__).parameters

            kwargs = {}

            for name in ("frame_rate", "fps"):
                if name in params:
                    kwargs[name] = 30
                    break

            self._tracker = BYTETracker(args, **kwargs)

        except Exception:
            logger.exception(
                "ByteTrack could not be created - falling back to IoU "
                "matching of faces"
            )
            self._tracker = None

    # --------------------------------------------------------

    def update(self, boxes):
        """boxes: `yolo_results[0].boxes`.

        Returns [(x1, y1, x2, y2, person_id)] for every tracked person of
        this frame. person_id is None when tracking is not available.
        """

        if self._tracker is None:
            return _plain_boxes(boxes if boxes is not None else [])

        if boxes is None or len(boxes) == 0:

            # No detections: still advance ByteTrack so lost tracks age out.
            try:
                self._feed_empty()
            except Exception:
                logger.exception("ByteTrack empty update failed")

            return []

        try:

            tracks = self._tracker.update(boxes.cpu().numpy())

            return [
                (int(t[0]), int(t[1]), int(t[2]), int(t[3]), int(t[4]))
                for t in tracks
            ]

        except Exception:

            logger.exception("ByteTrack update failed - using plain boxes")
            return _plain_boxes(boxes)

    # --------------------------------------------------------

    def _feed_empty(self):

        import numpy as np

        empty = SimpleNamespace(
            conf=np.empty((0,), dtype=np.float32),
            xywh=np.empty((0, 4), dtype=np.float32),
            cls=np.empty((0,), dtype=np.float32),
        )

        self._tracker.update(empty)

    # --------------------------------------------------------

    def reset(self):
        """Forget every track (start / end of a session)."""

        self._create()