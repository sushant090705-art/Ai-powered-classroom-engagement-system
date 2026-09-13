import cv2
import time
from mrl_eye_predict import predict_eye_state


# -----------------------------------------
# Face detector
# -----------------------------------------

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


# -----------------------------------------
# Start webcam
# -----------------------------------------

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Error: Could not open webcam.")
    exit()

print("Webcam started.")
print("Press Q to quit.")


# -----------------------------------------
# Timer for each detected face
# -----------------------------------------

closed_start_times = {}


# -----------------------------------------
# Main loop
# -----------------------------------------

while True:

    ret, frame = cap.read()

    if not ret:
        print("Error: Could not read webcam frame.")
        break


    # -----------------------------------------
    # Convert frame to grayscale
    # -----------------------------------------

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


    # -----------------------------------------
    # Detect faces
    # -----------------------------------------

    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.2,
        minNeighbors=5,
        minSize=(100, 100)
    )


    # -----------------------------------------
    # Process every detected face
    # -----------------------------------------

    for face_id, (x, y, w, h) in enumerate(faces):


        # -----------------------------------------
        # Face rectangle
        # -----------------------------------------

        cv2.rectangle(
            frame,
            (x, y),
            (x + w, y + h),
            (255, 0, 0),
            2
        )


        # -----------------------------------------
        # Fixed eye regions
        # -----------------------------------------

        eye_y1 = y + int(h * 0.20)
        eye_y2 = y + int(h * 0.50)


        # Left eye
        left_x1 = x + int(w * 0.10)
        left_x2 = x + int(w * 0.48)


        # Right eye
        right_x1 = x + int(w * 0.52)
        right_x2 = x + int(w * 0.90)


        eye_regions = [
            (left_x1, eye_y1, left_x2, eye_y2),
            (right_x1, eye_y1, right_x2, eye_y2)
        ]


        # -----------------------------------------
        # Store predictions for both eyes
        # -----------------------------------------

        eye_states = []


        # -----------------------------------------
        # Process both eyes
        # -----------------------------------------

        for (ex1, ey1, ex2, ey2) in eye_regions:

            eye_frame = frame[ey1:ey2, ex1:ex2]


            if eye_frame.size == 0:
                continue


            # -----------------------------------------
            # MRL prediction
            # -----------------------------------------

            state, confidence = predict_eye_state(eye_frame)

            eye_states.append(state)


            # -----------------------------------------
            # Display prediction and confidence
            # -----------------------------------------

            cv2.putText(
                frame,
                f"{state}: {confidence:.1f}%",
                (ex1, ey1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 255, 255),
                1
            )


            # -----------------------------------------
            # Draw eye box
            # -----------------------------------------

            cv2.rectangle(
                frame,
                (ex1, ey1),
                (ex2, ey2),
                (0, 255, 0),
                2
            )


        # -----------------------------------------
        # Decide overall eye state
        # -----------------------------------------

        if len(eye_states) >= 2:

            open_eyes = eye_states.count("Awake")
            closed_eyes = eye_states.count("Sleepy")


            # -----------------------------------------
            # BOTH EYES OPEN
            # -----------------------------------------

            if open_eyes == 2:

                display_state = "OPEN"

                # Reset this face's timer
                closed_start_times.pop(face_id, None)


            # -----------------------------------------
            # BOTH EYES CLOSED
            # -----------------------------------------

            elif closed_eyes == 2:

                # Start timer for this face
                if face_id not in closed_start_times:

                    closed_start_times[face_id] = time.time()


                # Calculate closed duration
                closed_duration = (
                    time.time() - closed_start_times[face_id]
                )


                # -----------------------------------------
                # Less than 1 second
                # -----------------------------------------

                if closed_duration < 1:

                    display_state = "BLINK"


                # -----------------------------------------
                # 1 to 3 seconds
                # -----------------------------------------

                elif closed_duration < 3:

                    display_state = "DROWSY"


                # -----------------------------------------
                # More than 3 seconds
                # -----------------------------------------

                else:

                    display_state = "SLEEPING"


            # -----------------------------------------
            # ONLY ONE EYE CLOSED
            # -----------------------------------------

            else:

                display_state = "BLINK"

                # Reset this face's timer
                closed_start_times.pop(face_id, None)


        else:

            display_state = "NO EYES"

            # Reset this face's timer
            closed_start_times.pop(face_id, None)


        # -----------------------------------------
        # Display overall state
        # -----------------------------------------

        cv2.putText(
            frame,
            display_state,
            (x, y - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2
        )


        # -----------------------------------------
        # Display face ID
        # -----------------------------------------

        cv2.putText(
            frame,
            f"Face {face_id + 1}",
            (x, y + h + 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2
        )


    # -----------------------------------------
    # Show webcam
    # -----------------------------------------

    cv2.imshow(
        "MRL Eye State Detection",
        frame
    )


    # -----------------------------------------
    # Press Q to quit
    # -----------------------------------------

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break


# -----------------------------------------
# Release resources
# -----------------------------------------

cap.release()
cv2.destroyAllWindows()