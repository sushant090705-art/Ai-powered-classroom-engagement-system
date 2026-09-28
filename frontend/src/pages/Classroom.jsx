import { useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import ThemeToggle from "../components/ThemeToggle";
import "./Classroom.css";

function Classroom() {
  const navigate = useNavigate();

  // =========================
  // BACKEND
  // =========================

  const BACKEND_URL = "http://127.0.0.1:5000";

  // =========================
  // CAMERA
  // =========================

  const [cameraMode, setCameraMode] = useState("webcam"); // "webcam" | "phone"
  const [webcamIndex, setWebcamIndex] = useState(0);
  const [activeCameraType, setActiveCameraType] = useState("none");
  const [cameraUrl, setCameraUrl] = useState("");
  const [cameraConnected, setCameraConnected] = useState(false);
  const [cameraLoading, setCameraLoading] = useState(false);
  const [cameraError, setCameraError] = useState("");
  const [cameraOn, setCameraOn] = useState(false);

  // =========================
  // EMOTION
  // =========================

  const [emotion, setEmotion] = useState("Waiting...");
  const [emotionConfidence, setEmotionConfidence] = useState(0);
  const [facesDetected, setFacesDetected] = useState(0);

  // Check camera status on mount
  useEffect(() => {
    const checkCameraStatus = async () => {
      try {
        const response = await fetch(`${BACKEND_URL}/camera/status`);
        if (!response.ok) return;
        const data = await response.json();
        if (data.connected) {
          setCameraConnected(true);
          setCameraOn(true);
          setActiveCameraType(data.type || "phone");
          if (data.type === "webcam") {
            setCameraMode("webcam");
            setWebcamIndex(Number(data.source) || 0);
          } else if (data.type === "phone") {
            setCameraMode("phone");
          }
        }
      } catch (err) {
        // Backend not ready or offline
      }
    };

    checkCameraStatus();
  }, []);

  // =========================
  // CONNECT CAMERA
  // =========================

  const connectCamera = async (modeOverride) => {
    const mode = modeOverride || cameraMode;
    setCameraError("");

    let payload = {};

    if (mode === "webcam") {
      payload = {
        type: "webcam",
        index: Number(webcamIndex) || 0,
      };
    } else {
      const rawUrl = cameraUrl.trim();
      if (!rawUrl) {
        setCameraError("Please enter phone camera IP or URL");
        return;
      }

      let formattedUrl = rawUrl;
      // If user typed only IP or IP:port without http://
      if (
        !formattedUrl.startsWith("http://") &&
        !formattedUrl.startsWith("https://") &&
        !formattedUrl.startsWith("rtsp://")
      ) {
        if (!formattedUrl.includes(":")) {
          formattedUrl = `http://${formattedUrl}:8080/video`;
        } else {
          formattedUrl = `http://${formattedUrl}/video`;
        }
      }

      payload = {
        type: "phone",
        url: formattedUrl,
      };
    }

    setCameraLoading(true);

    try {
      const response = await fetch(
        `${BACKEND_URL}/camera/connect`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        }
      );

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.message || "Failed to connect camera"
        );
      }

      setCameraConnected(true);
      setCameraOn(true);
      setActiveCameraType(data.type || mode);

    } catch (error) {
      console.error("Camera connection error:", error);

      setCameraConnected(false);
      setCameraOn(false);
      setActiveCameraType("none");

      setCameraError(
        error.message || "Unable to connect camera"
      );

    } finally {
      setCameraLoading(false);
    }
  };

  // =========================
  // DISCONNECT CAMERA
  // =========================

  const disconnectCamera = async () => {
    try {
      await fetch(
        `${BACKEND_URL}/camera/disconnect`,
        {
          method: "POST",
        }
      );
    } catch (error) {
      console.error(
        "Camera disconnect error:",
        error
      );
    }

    setCameraConnected(false);
    setCameraOn(false);
    setActiveCameraType("none");

    setEmotion("Waiting...");
    setEmotionConfidence(0);
    setFacesDetected(0);
  };

  // =========================
  // STOP CAMERA
  // =========================

  const stopCamera = async () => {
    await disconnectCamera();
  };

  // =========================
  // GET EMOTION RESULTS
  // =========================

  useEffect(() => {
    if (!cameraOn) return;

    const getEmotionResults = async () => {
      try {
        const response = await fetch(
          `${BACKEND_URL}/emotion-results`
        );

        if (!response.ok) {
          throw new Error(
            `Server error: ${response.status}`
          );
        }

        const data = await response.json();

        if (data.success) {
          setFacesDetected(
            data.faces_detected || 0
          );

          if (
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
            setEmotion("No face");
            setEmotionConfidence(0);
          }
        }

      } catch (error) {
        console.error(
          "Emotion results error:",
          error
        );

        setEmotion("Connection error");
        setEmotionConfidence(0);
      }
    };

    getEmotionResults();

    const interval = setInterval(
      getEmotionResults,
      1000
    );

    return () => {
      clearInterval(interval);
    };

  }, [cameraOn]);


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

            <p>
              LIVE CLASSROOM
            </p>

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
            CAMERA CONNECTION
        ========================= */}

        <section className="camera-connection-panel">

          <div className="camera-panel-top">
            <div>
              <h3>Connect Classroom Camera</h3>
              <p>
                Choose between your laptop/PC webcam or stream from a mobile phone via IP Webcam.
              </p>
            </div>

            {/* Mode Switcher Tabs */}
            <div className="camera-mode-tabs">
              <button
                type="button"
                className={`camera-mode-tab ${cameraMode === "webcam" ? "active" : ""}`}
                onClick={() => {
                  if (!cameraConnected) {
                    setCameraMode("webcam");
                    setCameraError("");
                  }
                }}
                disabled={cameraConnected || cameraLoading}
              >
                💻 Laptop / PC Webcam
              </button>

              <button
                type="button"
                className={`camera-mode-tab ${cameraMode === "phone" ? "active" : ""}`}
                onClick={() => {
                  if (!cameraConnected) {
                    setCameraMode("phone");
                    setCameraError("");
                  }
                }}
                disabled={cameraConnected || cameraLoading}
              >
                📱 Phone Camera (IP)
              </button>
            </div>
          </div>

          {/* WEBCAM MODE CONTROLS */}
          {cameraMode === "webcam" && (
            <div className="camera-controls-wrapper">
              <div className="camera-webcam-row">
                <div className="camera-select-field">
                  <label htmlFor="webcam-select">Camera Device:</label>
                  <select
                    id="webcam-select"
                    value={webcamIndex}
                    onChange={(e) => setWebcamIndex(e.target.value)}
                    disabled={cameraLoading || cameraConnected}
                  >
                    <option value="0">Camera 0 (Default Built-in Webcam)</option>
                    <option value="1">Camera 1 (Secondary / External USB)</option>
                    <option value="2">Camera 2 (External Camera 2)</option>
                  </select>
                </div>

                {!cameraConnected ? (
                  <button
                    className="camera-action-btn"
                    onClick={() => connectCamera("webcam")}
                    disabled={cameraLoading}
                  >
                    {cameraLoading ? "Starting Webcam..." : "Start Laptop Webcam"}
                  </button>
                ) : (
                  <button
                    className="camera-action-btn disconnect"
                    onClick={disconnectCamera}
                  >
                    Disconnect
                  </button>
                )}
              </div>
              <small className="camera-hint">
                💡 Tip: Uses your built-in PC/laptop webcam directly. Ensure other apps (Zoom, Teams) aren't locking the camera.
              </small>
            </div>
          )}

          {/* PHONE CAMERA MODE CONTROLS */}
          {cameraMode === "phone" && (
            <div className="camera-controls-wrapper">
              <div className="camera-url-row">
                <input
                  type="text"
                  value={cameraUrl}
                  onChange={(e) => setCameraUrl(e.target.value)}
                  placeholder="Enter phone IP (e.g. 192.168.1.15) or full video URL"
                  disabled={cameraLoading || cameraConnected}
                />

                {!cameraConnected ? (
                  <button
                    className="camera-action-btn"
                    onClick={() => connectCamera("phone")}
                    disabled={cameraLoading}
                  >
                    {cameraLoading ? "Connecting..." : "Connect Phone Camera"}
                  </button>
                ) : (
                  <button
                    className="camera-action-btn disconnect"
                    onClick={disconnectCamera}
                  >
                    Disconnect
                  </button>
                )}
              </div>
              <small className="camera-hint">
                💡 Tip: Open the <b>IP Webcam</b> app on Android/iOS, tap "Start server", and enter the displayed IP address.
              </small>
            </div>
          )}

          {cameraError && (
            <p className="camera-error">
              ⚠️ {cameraError}
            </p>
          )}

          {cameraConnected && (
            <p className="camera-success">
              ✓ {activeCameraType === "webcam" ? "Laptop / PC Webcam" : "Phone Camera"} connected and streaming live
            </p>
          )}

        </section>


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
                  ? activeCameraType === "webcam"
                    ? "💻 PC Webcam Active"
                    : "📱 Phone Camera Active"
                  : "Camera Ready"}

              </span>

            </div>


            {/* CAMERA BOX */}

            <div className="camera-box">

              {cameraOn ? (

                <div className="camera-live">

                  <img
                    src={`${BACKEND_URL}/video_feed`}
                    alt="Live classroom camera"
                    className="classroom-video"
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

                    <div className="emotion-confidence">

                      Faces Detected:{" "}

                      {facesDetected}

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
                    {cameraMode === "webcam" ? "💻" : "📱"}
                  </div>

                  <h3>
                    {cameraMode === "webcam" ? "Laptop / PC Webcam" : "Mobile IP Camera"}
                  </h3>

                  <p>
                    {cameraMode === "webcam"
                      ? "Click 'Start Laptop Webcam' above to begin monitoring with your computer camera."
                      : "Connect your mobile IP Webcam above to begin classroom monitoring."}
                  </p>

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
                {facesDetected}
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
                --
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
                --
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
                --
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
                {getEmotionEmoji()}
              </span>

              <p>
                Current
              </p>

              <strong>
                {emotion}
              </strong>

            </div>

            <div>

              <span>
                🎯
              </span>

              <p>
                Confidence
              </p>

              <strong>
                {Number(
                  emotionConfidence
                ).toFixed(1)}%
              </strong>

            </div>

            <div>

              <span>
                👥
              </span>

              <p>
                Faces
              </p>

              <strong>
                {facesDetected}
              </strong>

            </div>

          </div>

        </section>


        {/* =========================
            ANALYTICS BUTTON
        ========================= */}
        <button
  className="recorded-video-button"
  onClick={() => navigate("/recorded-video")}
>
  Upload Recorded Video →
</button>
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
