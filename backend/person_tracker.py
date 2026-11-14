"""ByteTrack person tracker (one instance per ClassEngine)."""

import logging
from types import SimpleNamespace

logger = logging.getLogger(__name__)

# AI loop ~2 FPS chalta hai. 20 frames ~ 10 second lost student yaad rehta hai.
DEFAULT_TRACK_BUFFER = 20
DEFAULT_MATCH_THRESH = 0.85


def _plain_boxes(boxes):
    out = []
    for box in boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        out.append((x1, y1, x2, y2, None))
    return out


class PersonTracker:

    def __init__(self, track_buffer=DEFAULT_TRACK_BUFFER,
                 match_thresh=DEFAULT_MATCH_THRESH):
        self._args = SimpleNamespace(
            track_high_thresh=0.40,
            track_low_thresh=0.10,
            new_track_thresh=0.45,
            track_buffer=track_buffer,
            match_thresh=match_thresh,
            fuse_score=True,
            mot20=False,
        )
        self._tracker = None
        self._create()

    def _create(self):
        try:
            from ultralytics.trackers.byte_tracker import BYTETracker
            self._tracker = BYTETracker(self._args, frame_rate=30)
        except Exception:
            logger.exception("ByteTrack could not be created - IoU fallback")
            self._tracker = None

    def update(self, boxes):
        """Returns [(x1, y1, x2, y2, person_id)]. person_id None = no tracking."""

        if self._tracker is None:
            return _plain_boxes(boxes if boxes is not None else [])

        if boxes is None or len(boxes) == 0:
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

    def _feed_empty(self):
        import numpy as np
        empty = SimpleNamespace(
            conf=np.empty((0,), dtype=np.float32),
            xywh=np.empty((0, 4), dtype=np.float32),
            cls=np.empty((0,), dtype=np.float32),
        )
        self._tracker.update(empty)

    def reset(self):
        self._create()