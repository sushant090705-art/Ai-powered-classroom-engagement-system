import { useNavigate } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import ThemeToggle from "../components/ThemeToggle";
import "./Classroom.css";

function Classroom() {
  const navigate = useNavigate();

  // =========================
  // CAMERA
  // =========================

  const videoRef = useRef(null);

  const [cameraOn, setCameraOn] = useState(false);
  const [stream, setStream] = useState(null);

  // =========================
  // FER EMOTION
  // =========================

  const [emotion, setEmotion] = useState("Waiting...");
  const [emotionConfidence, setEmotionConfidence] = useState(0);

  // =========================
  // START CAMERA
  // =========================

  const startCamera = async () => {
    try {
      const mediaStream =
        await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: false,
        });

      setStream(mediaStream);
      setCameraOn(true);

    } catch (error) {
      console.error("Camera access failed:", error);

      alert(
        "Unable to access camera. Please allow camera permission and try again."
      );
    }
  };

  // =========================
  // FER ANALYSIS
  // =========================

  const analyzeEmotion = async () => {
    if (!videoRef.current) return;

    const video = videoRef.current;

    // Camera not ready yet
    if (video.readyState < 2) return;

    // Make canvas
    const canvas = document.createElement("canvas");

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext("2d");

    if (!ctx) return;

    // Capture current video frame
    ctx.drawImage(
      video,
      0,
      0,
      canvas.width,
      canvas.height
    );

    // Convert frame to image
    canvas.toBlob(
      async (blob) => {
        if (!blob) return;

        const formData = new FormData();

        formData.append(
          "image",
          blob,
          "frame.jpg"
        );

        try {
          const response = await fetch(
            "http://127.0.0.1:5000/predict-emotion",
            {
              method: "POST",
              body: formData,
            }
          );

          if (!response.ok) {
            throw new Error(
              `Server error: ${response.status}`
            );
          }

          const data = await response.json();

          console.log("FER Response:", data);

          // =========================
          // FACE DETECTED
          // =========================

          if (
            data.success &&
            data.faces_detected > 0 &&
            data.faces &&
            data.faces.length > 0
          ) {
            const face = data.faces[0];

            setEmotion(
              face.emotion || "Unknown"
            );

            setEmotionConfidence(
              Number(face.confidence) || 0
            );

          } else {

            // No face detected
            setEmotion("No face");
            setEmotionConfidence(0);
          }

        } catch (error) {

          console.error(
            "FER connection error:",
            error
          );

          setEmotion("Connection error");
          setEmotionConfidence(0);
        }
      },
      "image/jpeg",
      0.8
    );
  };

  // =========================
  // ATTACH STREAM TO VIDEO
  // =========================

  useEffect(() => {
    if (videoRef.current && stream) {
      videoRef.current.srcObject = stream;
    }
  }, [stream]);

  // =========================
  // RUN FER EVERY 1.5 SECONDS
  // =========================

  useEffect(() => {
    if (!cameraOn) return;

    const interval = setInterval(() => {
      analyzeEmotion();
    }, 1500);

    return () => {
      clearInterval(interval);
    };
  }, [cameraOn]);

  // =========================
  // STOP CAMERA
  // =========================

  const stopCamera = () => {
    if (stream) {
      stream.getTracks().forEach((track) => {
        track.stop();
      });
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    setStream(null);
    setCameraOn(false);

    // Reset FER
    setEmotion("Waiting...");
    setEmotionConfidence(0);
  };

  // =========================
  // CLEANUP WHEN LEAVING PAGE
  // =========================

  useEffect(() => {
    return () => {
      if (stream) {
        stream.getTracks().forEach((track) => {
          track.stop();
        });
      }
    };
  }, [stream]);

  // =========================
  // EMOTION EMOJI
  // =========================

  const getEmotionEmoji = () => {
    switch (emotion?.toLowerCase()) {
      case "happy":
        return "😊";

      case "sad":
        return "😢";

      case "angry":
        return "😠";

      case "fear":
        return "😨";

      case "disgust":
        return "🤢";

      case "surprise":
        return "😮";

      case "neutral":
        return "😐";

      default:
        return "🤖";
    }
  };

  // =========================
  // RETURN UI
  // =========================

  return (
    <div className="classroom-page">

      {/* =========================
          NAVBAR
      ========================= */}

      <nav className="classroom-nav">

        <div className="classroom-logo">
          <span>◉</span>
          ClassroomAI
        </div>

        <div className="classroom-nav-right">

          <ThemeToggle />

          <span className="teacher-name">
            Teacher
          </span>

          <button
            onClick={() =>
              navigate("/dashboard")
            }
          >
            Dashboard
          </button>

        </div>

      </nav>

      {/* =========================
          MAIN CONTENT
      ========================= */}

      <main className="classroom-content">

        {/* =========================
            PAGE HEADING
        ========================= */}

        <div className="classroom-heading">

          <div>
            <p>LIVE CLASSROOM</p>

            <h1>
              Computer Science — AI
            </h1>
          </div>

          <div className="live-indicator">

            {cameraOn ? (
              <>
                <span></span>
                LIVE
              </>
            ) : (
              "CAMERA OFF"
            )}

          </div>

        </div>

        {/* =========================
            CAMERA + ENGAGEMENT
        ========================= */}

        <div className="classroom-grid">

          {/* =========================
              CAMERA CARD
          ========================= */}

          <section className="camera-card">

            <div className="camera-header">

              <div>

                <small>
                  CLASSROOM CAMERA
                </small>

                <h2>
                  Live View
                </h2>

              </div>

              <span className="camera-status">

                {cameraOn
                  ? "Camera Active"
                  : "Camera Ready"}

              </span>

            </div>

            {/* CAMERA BOX */}

            <div className="camera-box">

              {cameraOn ? (

                <div className="camera-live">

                  {/* VIDEO */}

                  <video
                    ref={videoRef}
                    autoPlay
                    playsInline
                    muted
                  />

                  {/* =========================
                      FER EMOTION OVERLAY
                  ========================= */}

                  <div className="emotion-overlay">

                    <div className="emotion-title">
                      AI EMOTION DETECTION
                    </div>

                    <div className="emotion-main">

                      <span className="emotion-emoji">
                        {getEmotionEmoji()}
                      </span>

                      <span className="emotion-value">
                        {emotion}
                      </span>

                    </div>

                    <div className="emotion-confidence">

                      Confidence:{" "}
                      {Number(
                        emotionConfidence
                      ).toFixed(1)}
                      %

                    </div>

                  </div>

                  {/* STOP CAMERA */}

                  <button
                    className="camera-btn stop-btn"
                    onClick={stopCamera}
                  >
                    Stop Camera
                  </button>

                </div>

              ) : (

                <div className="camera-placeholder">

                  <div className="camera-icon">
                    📷
                  </div>

                  <h3>
                    Camera Preview
                  </h3>

                  <p>
                    Start the camera to begin
                    classroom monitoring.
                  </p>

                  <button
                    className="camera-btn"
                    onClick={startCamera}
                  >
                    Start Camera
                  </button>

                </div>

              )}

            </div>

          </section>

          {/* =========================
              ENGAGEMENT CARD
          ========================= */}

          <section className="engagement-card">

            <div className="card-title">

              <div>

                <small>
                  REAL-TIME ANALYSIS
                </small>

                <h2>
                  Engagement
                </h2>

              </div>

              <span className="ai-badge">
                AI
              </span>

            </div>

            {/* SCORE */}

            <div className="engagement-score">

              <strong>
                78%
              </strong>

              <span>
                Overall Engagement
              </span>

            </div>

            {/* ATTENTION */}

            <div className="metric">

              <div>

                <span>
                  Attention
                </span>

                <strong>
                  82%
                </strong>

              </div>

              <div className="progress">

                <div
                  style={{
                    width: "82%",
                  }}
                ></div>

              </div>

            </div>

            {/* PARTICIPATION */}

            <div className="metric">

              <div>

                <span>
                  Participation
                </span>

                <strong>
                  69%
                </strong>

              </div>

              <div className="progress">

                <div
                  style={{
                    width: "69%",
                  }}
                ></div>

              </div>

            </div>

            {/* POSITIVE MOOD */}

            <div className="metric">

              <div>

                <span>
                  Positive Mood
                </span>

                <strong>
                  74%
                </strong>

              </div>

              <div className="progress">

                <div
                  style={{
                    width: "74%",
                  }}
                ></div>

              </div>

            </div>

          </section>

        </div>

        {/* =========================
            STUDENT STATISTICS
        ========================= */}

        <section className="classroom-stats">

          <div className="classroom-stat">

            <span>
              👥
            </span>

            <div>

              <small>
                Students Detected
              </small>

              <strong>
                32
              </strong>

            </div>

          </div>

          <div className="classroom-stat">

            <span>
              👁️
            </span>

            <div>

              <small>
                Focused Students
              </small>

              <strong>
                26
              </strong>

            </div>

          </div>

          <div className="classroom-stat">

            <span>
              🙋
            </span>

            <div>

              <small>
                Participating
              </small>

              <strong>
                22
              </strong>

            </div>

          </div>

          <div className="classroom-stat">

            <span>
              😕
            </span>

            <div>

              <small>
                Confused
              </small>

              <strong>
                4
              </strong>

            </div>

          </div>

        </section>

        {/* =========================
            CLASSROOM EMOTIONS
        ========================= */}

        <section className="emotion-card">

          <div>

            <small>
              CLASSROOM EMOTIONS
            </small>

            <h2>
              Current Emotional State
            </h2>

          </div>

          <div className="emotion-list">

            <div>

              <span>
                😊
              </span>

              <p>
                Positive
              </p>

              <strong>
                74%
              </strong>

            </div>

            <div>

              <span>
                😐
              </span>

              <p>
                Neutral
              </p>

              <strong>
                18%
              </strong>

            </div>

            <div>

              <span>
                😕
              </span>

              <p>
                Confused
              </p>

              <strong>
                6%
              </strong>

            </div>

            <div>

              <span>
                😴
              </span>

              <p>
                Disengaged
              </p>

              <strong>
                2%
              </strong>

            </div>

          </div>

        </section>

        {/* =========================
            ANALYTICS BUTTON
        ========================= */}

        <button
          className="analytics-button"
          onClick={() =>
            navigate("/analytics")
          }
        >
          View Detailed Analytics →
        </button>

      </main>

    </div>
  );
}

export default Classroom;