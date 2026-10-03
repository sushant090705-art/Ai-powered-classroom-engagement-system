from flask import Blueprint, request, jsonify

import os
import cv2
import time

from eye_tracking import reset_eye_tracks

from ai_processing import (
    process_frame
)


# ============================================================
# RECORDED VIDEO BLUEPRINT
# ============================================================

recorded_video_bp = Blueprint(
    "recorded_video",
    __name__
)


# ============================================================
# ANALYZE RECORDED VIDEO
# ============================================================

@recorded_video_bp.route(
    "/analyze-video",
    methods=["POST"]
)
def analyze_video():

    video_path = None
    cap = None

    try:

        # ====================================================
        # CHECK VIDEO
        # ====================================================

        if "video" not in request.files:

            return jsonify({

                "success": False,

                "message":
                    "No video received"

            }), 400

        video_file = (
            request.files["video"]
        )

        if (
            video_file.filename
            == ""
        ):

            return jsonify({

                "success": False,

                "message":
                    "No video selected"

            }), 400

        # ====================================================
        # UPLOAD FOLDER
        # ====================================================

        upload_folder = os.path.join(

            os.path.dirname(
                os.path.abspath(
                    __file__
                )
            ),

            "uploads"

        )

        os.makedirs(
            upload_folder,
            exist_ok=True
        )

        filename = (
            f"uploaded_"
            f"{int(time.time())}.mp4"
        )

        video_path = os.path.join(
            upload_folder,
            filename
        )

        video_file.save(
            video_path
        )

        # ====================================================
        # OPEN VIDEO
        # ====================================================

        cap = cv2.VideoCapture(
            video_path
        )

        if not cap.isOpened():

            return jsonify({

                "success": False,

                "message":
                    "Could not open video"

            }), 400

        # ====================================================
        # VIDEO INFORMATION
        # ====================================================

        total_frames = int(
            cap.get(
                cv2.CAP_PROP_FRAME_COUNT
            )
        )

        fps = cap.get(
            cv2.CAP_PROP_FPS
        )

        if fps <= 0:

            fps = 25

        video_duration = (
            total_frames / fps
        )

        # ====================================================
        # RESULT VARIABLES
        # ====================================================

        emotion_counts = {}

        total_faces = 0

        processed_frames = 0

        frame_interval = max(
            int(fps),
            1
        )

        frame_number = 0

        # ====================================================
        # RESET EYE TRACKING
        # ====================================================
        reset_eye_tracks()

        # ====================================================
        # PROCESS VIDEO
        # ====================================================

        while True:

            success, frame = (
                cap.read()
            )

            if not success:

                break

            frame_number += 1

            # =================================================
            # PROCESS APPROXIMATELY ONE FRAME PER SECOND
            # =================================================

            if (
                frame_number
                %
                frame_interval
                != 0
            ):

                continue

            results = process_frame(
                frame
            )

            if results is None:

                results = []

            processed_frames += 1

            total_faces += len(
                results
            )

            # =================================================
            # COUNT EMOTIONS
            # =================================================

            for result in results:

                emotion = result[
                    "emotion"
                ]

                if (
                    emotion
                    not in
                    emotion_counts
                ):

                    emotion_counts[
                        emotion
                    ] = 0

                emotion_counts[
                    emotion
                ] += 1

        # ====================================================
        # RELEASE VIDEO
        # ====================================================

        cap.release()

        cap = None

        # ====================================================
        # MOST COMMON EMOTION
        # ====================================================

        most_common_emotion = (
            "Unknown"
        )

        if emotion_counts:

            most_common_emotion = max(

                emotion_counts,

                key=emotion_counts.get

            )

        # ====================================================
        # RETURN RESULT
        # ====================================================

        return jsonify({

            "success":
                True,

            "message":
                "Video analyzed successfully",

            "duration_seconds":
                round(
                    video_duration,
                    2
                ),

            "total_frames":
                total_frames,

            "processed_frames":
                processed_frames,

            "total_faces_detected":
                total_faces,

            "emotion_counts":
                emotion_counts,

            "most_common_emotion":
                most_common_emotion

        })

    # ========================================================
    # ERROR
    # ========================================================

    except Exception as e:

        print(
            "VIDEO ANALYSIS ERROR:",
            e
        )

        return jsonify({

            "success":
                False,

            "message":
                str(e)

        }), 500

    # ========================================================
    # CLEANUP
    # ========================================================

    finally:

        if cap is not None:

            cap.release()

        if (
            video_path
            and
            os.path.exists(
                video_path
            )
        ):

            try:

                os.remove(
                    video_path
                )

            except Exception as e:

                print(
                    "Could not delete "
                    "temporary video:",
                    e
                )


print(
    "Recorded video module loaded successfully!"
)