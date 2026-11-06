"""Quality-gated face snapshots for per-student reports.

Only detector-provided face boxes are used. This module does not identify
people; it stores a cropped image against the tracker-generated student ID.
"""
import os

import cv2
import numpy as np


def save_clear_face_snapshot(frame, box, destination):
    """Save a face crop only when it is sufficiently complete and clear.

    Returns a quality score (0..100), or None when the crop fails checks.
    """
    if frame is None or getattr(frame, "ndim", 0) < 2:
        return None

    frame_h, frame_w = frame.shape[:2]
    x, y, width, height = [int(round(value)) for value in box]

    if width < 70 or height < 70:
        return None

    # Reject boxes touching/crossing the image edge: these may be cut faces.
    if x < 2 or y < 2 or x + width > frame_w - 2 or y + height > frame_h - 2:
        return None

    ratio = width / float(height)
    if ratio < 0.62 or ratio > 1.48:
        return None

    # Include a modest margin around the detected face for a natural crop.
    pad_x = int(width * 0.18)
    pad_y = int(height * 0.18)
    left = max(0, x - pad_x)
    top = max(0, y - pad_y)
    right = min(frame_w, x + width + pad_x)
    bottom = min(frame_h, y + height + pad_y)
    crop = frame[top:bottom, left:right]

    if crop.size == 0:
        return None

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    brightness = float(np.mean(gray))
    contrast = float(np.std(gray))
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    if brightness < 38 or brightness > 225:
        return None
    if contrast < 18 or sharpness < 45:
        return None

    # Score is used only to keep the best acceptable image for this student.
    sharp_score = min(1.0, sharpness / 180.0)
    light_score = max(0.0, 1.0 - abs(brightness - 128.0) / 128.0)
    contrast_score = min(1.0, contrast / 55.0)
    quality = round(100 * (0.55 * sharp_score + 0.25 * light_score + 0.20 * contrast_score))

    os.makedirs(os.path.dirname(destination), exist_ok=True)
    ok = cv2.imwrite(destination, crop, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    return quality if ok else None
