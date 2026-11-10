"""Clean face snapshots for student reports.

Only detector-provided face boxes are cropped. No identity recognition is
performed; images are associated with temporary tracker-generated IDs.

Design: a student should ALWAYS end up with a visible face photo. So the
rules below only reject crops that are clearly unusable (outside the frame,
tiny, black/white, featureless). Everything else gets a quality score and
the engine keeps the BEST crop it ever sees for each student.
"""

import os

import cv2
import numpy as np


# ------------------------------------------------------------
# TUNABLE SETTINGS (adjust here if photos are still too strict/loose)
# ------------------------------------------------------------

MIN_FACE_SIDE = 24          # px in the source frame; smaller = rejected
MIN_VISIBLE_SHARE = 0.70    # share of the face box that must be in-frame
MIN_BRIGHTNESS = 15
MAX_BRIGHTNESS = 245
MIN_CONTRAST = 8
MIN_SHARPNESS = 5           # measured on a normalised 96x96 crop

PAD_SIDE = 0.25             # extra margin left/right (share of face width)
PAD_TOP = 0.35              # forehead / hair
PAD_BOTTOM = 0.25           # chin / neck

# Crops where a second face check confirmed a real face score >= this.
# Unconfirmed crops (walls, posters, clothes) always score below it.
FACE_VERIFIED_MIN_QUALITY = 50

VERIFY_SIDE = 200           # crop is enlarged to this before verification

MIN_OUTPUT_SIDE = 192       # small crops are enlarged to at least this
MAX_OUTPUT_SIDE = 360       # huge crops are reduced to at most this


# Load the face detector once (used only as a quality bonus).
FACE_DETECTOR = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


def _looks_like_face(crop_bgr):
    """Confirm there is a real face near the middle of the crop.

    The crop is enlarged first, because small faces are missed by the
    detector at their original size.
    """

    if FACE_DETECTOR.empty():
        return False

    try:
        gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]

        factor = max(1.0, VERIFY_SIDE / float(max(h, w)))

        if factor > 1.0:
            gray = cv2.resize(
                gray,
                (int(round(w * factor)), int(round(h * factor))),
                interpolation=cv2.INTER_CUBIC,
            )

        gray = cv2.equalizeHist(gray)
        big_h, big_w = gray.shape[:2]

        detections = FACE_DETECTOR.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=3,
            minSize=(int(big_w * 0.30), int(big_h * 0.30)),
        )
    except cv2.error:
        return False

    # The crop is centred on the face, so a real face sits near the middle.
    for (fx, fy, fw, fh) in detections:
        cx = (fx + fw / 2.0) / big_w
        cy = (fy + fh / 2.0) / big_h

        if 0.25 <= cx <= 0.75 and 0.20 <= cy <= 0.80:
            return True

    return False


def _resize_for_display(crop):
    """Enlarge tiny crops / shrink huge ones so the photo looks clear."""

    h, w = crop.shape[:2]
    longest = max(h, w)

    if longest < MIN_OUTPUT_SIDE:
        factor = MIN_OUTPUT_SIDE / float(longest)
        return cv2.resize(
            crop,
            (int(round(w * factor)), int(round(h * factor))),
            interpolation=cv2.INTER_LANCZOS4,
        )

    if longest > MAX_OUTPUT_SIDE:
        factor = MAX_OUTPUT_SIDE / float(longest)
        return cv2.resize(
            crop,
            (int(round(w * factor)), int(round(h * factor))),
            interpolation=cv2.INTER_AREA,
        )

    return crop


def save_clear_face_snapshot(frame, box, destination, scale=1.0):
    """Save the face crop; return quality (1..100) or None if unusable.

    frame:  untouched BGR frame (no boxes drawn on it).
    box:    (x, y, w, h) in the coordinates the detector used.
    scale:  frame_width / detector_frame_width. Use it when `frame` is a
            higher-resolution version of the frame the detector saw.
    """

    if frame is None or getattr(frame, "ndim", 0) != 3 or frame.size == 0:
        return None

    frame_h, frame_w = frame.shape[:2]

    try:
        x, y, width, height = [
            float(value) * float(scale) for value in box
        ]
    except (TypeError, ValueError, OverflowError):
        return None

    if width <= 0 or height <= 0:
        return None

    if width < MIN_FACE_SIDE or height < MIN_FACE_SIDE:
        return None

    # Face box must be mostly inside the frame (partial edge faces ok).
    vis_w = min(frame_w, x + width) - max(0.0, x)
    vis_h = min(frame_h, y + height) - max(0.0, y)

    if vis_w <= 0 or vis_h <= 0:
        return None

    if (vis_w * vis_h) / (width * height) < MIN_VISIBLE_SHARE:
        return None

    # Margin around the face so the whole head is visible.
    left = int(max(0, round(x - width * PAD_SIDE)))
    right = int(min(frame_w, round(x + width * (1 + PAD_SIDE))))
    top = int(max(0, round(y - height * PAD_TOP)))
    bottom = int(min(frame_h, round(y + height * (1 + PAD_BOTTOM))))

    if right - left < MIN_FACE_SIDE or bottom - top < MIN_FACE_SIDE:
        return None

    crop = frame[top:bottom, left:right].copy()

    if crop.size == 0:
        return None

    try:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    except cv2.error:
        return None

    # Measure quality on a fixed size so big and small faces compare fairly.
    norm = cv2.resize(gray, (96, 96), interpolation=cv2.INTER_AREA)

    brightness = float(np.mean(norm))
    contrast = float(np.std(norm))
    sharpness = float(cv2.Laplacian(norm, cv2.CV_64F).var())

    if brightness < MIN_BRIGHTNESS or brightness > MAX_BRIGHTNESS:
        return None

    if contrast < MIN_CONTRAST:
        return None

    if sharpness < MIN_SHARPNESS:
        return None

    sharp_score = min(1.0, sharpness / 150.0)
    light_score = max(0.0, 1.0 - abs(brightness - 128.0) / 128.0)
    contrast_score = min(1.0, contrast / 55.0)
    size_score = min(1.0, min(width, height) / 110.0)
    verified = _looks_like_face(crop)

    detail_score = (
        0.45 * sharp_score
        + 0.20 * light_score
        + 0.15 * contrast_score
        + 0.20 * size_score
    )

    if verified:
        # 50..100: a confirmed face always beats an unconfirmed crop.
        quality = 50 + 50 * detail_score
    else:
        # 1..40: kept only as a last-resort photo.
        quality = 40 * detail_score

    quality = max(1, int(round(quality)))

    crop = _resize_for_display(crop)

    folder = os.path.dirname(destination)

    if folder:
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError:
            return None

    try:
        saved = cv2.imwrite(
            destination,
            crop,
            [int(cv2.IMWRITE_JPEG_QUALITY), 95],
        )
    except (cv2.error, OSError):
        return None

    return quality if saved else None