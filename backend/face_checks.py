"""Cheap sanity checks that tell a real face from a false detection.

The Haar face detector sometimes "finds" a face on jeans, a shirt or a
patterned wall. These checks do NOT use any detector. They look at things a
real face always has:

  1. position  - a face sits in the UPPER part of a person's body box;
  2. skin tone - a real face contains a fair share of skin-coloured pixels.

Both checks are deliberately lenient and "fail open": when the picture has
no colour (grayscale / night-vision camera) the skin check cannot judge, so
it lets the face through instead of deleting real people.
"""

import cv2
import numpy as np


# ------------------------------------------------------------
# TUNABLE SETTINGS
# ------------------------------------------------------------

# Face centre must be inside this top share of the person box (0..1).
# Standing person ~0.10, seated head+shoulders ~0.30, head only ~0.50.
FACE_MAX_CENTER_RATIO = 0.60

# Share of skin-coloured pixels needed in the middle of the face box.
MIN_SKIN_RATIO = 0.18

# YCrCb skin range (works for light and dark skin tones).
SKIN_CR_RANGE = (133, 173)
SKIN_CB_RANGE = (77, 127)

# A crop darker than this is almost black (black clothes, shadows): it is
# treated as "not a face". Set to 0 to switch this off.
MIN_FACE_BRIGHTNESS = 28

# A crop with less colour than this (grayscale / night-vision camera) cannot
# be judged by skin colour, so it is let through.
MIN_JUDGE_COLOURFULNESS = 6.0


def face_position_ok(face_y, face_h, person_y, person_h):
    """True if the face centre lies in the upper part of the person box."""

    try:
        face_y = float(face_y)
        face_h = float(face_h)
        person_y = float(person_y)
        person_h = float(person_h)
    except (TypeError, ValueError):
        return True

    if person_h <= 0 or face_h <= 0:
        return True

    centre = (face_y + face_h / 2.0 - person_y) / person_h

    return centre <= FACE_MAX_CENTER_RATIO


def skin_ratio(crop_bgr):
    """Share (0..1) of skin-coloured pixels in the middle of the crop.

    Returns 0.0 for an almost black crop and None for a colourless one
    (cannot be judged).
    """

    if crop_bgr is None or getattr(crop_bgr, "ndim", 0) != 3:
        return None

    h, w = crop_bgr.shape[:2]

    if h < 8 or w < 8:
        return None

    # Use the middle of the box: hair, background and collar sit at the edge.
    top, bottom = int(h * 0.15), int(h * 0.90)
    left, right = int(w * 0.15), int(w * 0.85)

    core = crop_bgr[top:bottom, left:right]

    if core.size == 0:
        return None

    try:
        ycrcb = cv2.cvtColor(core, cv2.COLOR_BGR2YCrCb)
    except cv2.error:
        return None

    y = ycrcb[:, :, 0].astype(np.float32)
    cr = ycrcb[:, :, 1].astype(np.float32)
    cb = ycrcb[:, :, 2].astype(np.float32)

    if float(np.mean(y)) < MIN_FACE_BRIGHTNESS:
        return 0.0

    colourfulness = float(np.mean(np.abs(cr - 128)) + np.mean(np.abs(cb - 128)))

    if colourfulness < MIN_JUDGE_COLOURFULNESS:
        return None

    skin = (
        (cr >= SKIN_CR_RANGE[0]) & (cr <= SKIN_CR_RANGE[1])
        & (cb >= SKIN_CB_RANGE[0]) & (cb <= SKIN_CB_RANGE[1])
    )

    return float(np.mean(skin))


def looks_like_skin(crop_bgr):
    """True if the crop has enough skin colour (or cannot be judged)."""

    ratio = skin_ratio(crop_bgr)

    if ratio is None:
        return True

    return ratio >= MIN_SKIN_RATIO