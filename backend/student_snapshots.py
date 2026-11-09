
"""Quality-gated, clean face snapshots for student reports.

Only detector-provided face boxes are cropped. No identity recognition is
performed; images are associated with temporary tracker-generated IDs.
"""

import os

import cv2
import numpy as np


# Load the face detector once.
CASCADE_PATH = (
    cv2.data.haarcascades
    + "haarcascade_frontalface_default.xml"
)

FACE_DETECTOR = cv2.CascadeClassifier(CASCADE_PATH)


def _is_valid_face_detection(gray_crop):
    """Check whether the crop contains a reasonably central face."""

    if FACE_DETECTOR.empty():
        return False

    if gray_crop is None or gray_crop.size == 0:
        return False

    crop_h, crop_w = gray_crop.shape[:2]

    if crop_h < 60 or crop_w < 60:
        return False

    # Improve contrast for secondary face detection.
    enhanced = cv2.equalizeHist(gray_crop)

    detections = FACE_DETECTOR.detectMultiScale(
        enhanced,
        scaleFactor=1.05,
        minNeighbors=3,
        minSize=(35, 35),
    )

    if len(detections) == 0:
        return False

    crop_center_x = crop_w / 2.0
    crop_center_y = crop_h / 2.0

    for (face_x, face_y, face_w, face_h) in detections:
        face_center_x = face_x + face_w / 2.0
        face_center_y = face_y + face_h / 2.0

        distance_x = abs(face_center_x - crop_center_x)
        distance_y = abs(face_center_y - crop_center_y)

        # Allow some variation in face position inside the crop.
        if (
            distance_x <= crop_w * 0.42
            and distance_y <= crop_h * 0.42
        ):
            return True

    return False


def save_clear_face_snapshot(frame, box, destination):
    """Save a sharp, plausible face crop; return quality (0..100) or None."""

    if frame is None or getattr(frame, "ndim", 0) != 3:
        return None

    if frame.size == 0:
        return None

    frame_h, frame_w = frame.shape[:2]

    try:
        x, y, width, height = [
            int(round(float(value))) for value in box
        ]
    except (TypeError, ValueError, OverflowError):
        return None

    if width <= 0 or height <= 0:
        return None

    # Permit some variation in detector face-box proportions.
    ratio = width / float(height)

    if ratio < 0.55 or ratio > 1.60:
        return None

    # Allow smaller faces, but not tiny detections.
    if width < 55 or height < 55:
        return None

    # Reject boxes that are completely or partly outside the frame.
    if (
        x < 0
        or y < 0
        or x + width > frame_w
        or y + height > frame_h
    ):
        return None

    # Add a modest margin around the detected face.
    pad_x = max(4, int(width * 0.14))
    pad_y = max(4, int(height * 0.14))

    left = max(0, x - pad_x)
    top = max(0, y - pad_y)
    right = min(frame_w, x + width + pad_x)
    bottom = min(frame_h, y + height + pad_y)

    crop = frame[top:bottom, left:right].copy()

    if crop.size == 0:
        return None

    crop_h, crop_w = crop.shape[:2]

    if crop_h < 60 or crop_w < 60:
        return None

    try:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    except cv2.error:
        return None

    brightness = float(np.mean(gray))
    contrast = float(np.std(gray))
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # Reject extremely dark or overexposed images.
    if brightness < 25 or brightness > 240:
        return None

    # Reject nearly featureless crops.
    if contrast < 12:
        return None

    # Reject heavily blurred crops.
    if sharpness < 25:
        return None

    # Secondary verification helps reject false detections on clothing.
    if not _is_valid_face_detection(gray):
        return None

    sharp_score = min(1.0, sharpness / 180.0)

    light_score = max(
        0.0,
        1.0 - abs(brightness - 128.0) / 128.0
    )

    contrast_score = min(1.0, contrast / 55.0)

    quality = round(
        100 * (
            0.55 * sharp_score
            + 0.25 * light_score
            + 0.20 * contrast_score
        )
    )

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
            [int(cv2.IMWRITE_JPEG_QUALITY), 92],
        )
    except (cv2.error, OSError):
        return None

    if not saved:
        return None

    return quality
