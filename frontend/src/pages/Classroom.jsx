import { useNavigate } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
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

  const [cameraMode, setCameraMode] = useState("webcam");
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

  // Stores ALL currently detected faces
  const [liveFaces, setLiveFaces] = useState([]);

  // =========================
  // CAMERA STATUS
  // =========================

  useEffect(() => {
    const checkCameraStatus = async () => {
      try {
        const response = await fetch(
          `${BACKEND_URL}/camera/status`
        );

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
        // Backend may not be running yet
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
        setCameraError(
          "Please enter phone camera IP or URL"
        );
        return;
      }

      let formattedUrl = rawUrl;

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
      console.error(
        "Camera connection error:",
        error
      );

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
    setLiveFaces([]);
  };

  // =========================
  // STOP CAMERA
  // =========================

  const stopCamera = async () => {
    await disconnectCamera();
  };

  // =========================
  // GET LIVE AI RESULTS
  // =========================

  useEffect(() => {
    if (!cameraOn) {
      setLiveFaces([]);
      return;
    }

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
          const faces = Array.isArray(data.faces)
            ? data.faces
            : [];

          // Save ALL detected faces
          setLiveFaces(faces);

          setFacesDetected(
            Number(data.faces_detected) ||
              faces.length
          );

          // Existing main emotion display
          if (faces.length > 0) {
            const face = faces[0];

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
        setLiveFaces([]);
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
  // REAL-TIME ENGAGEMENT METRICS
  // =========================
  //
  // These are calculated from:
  // - FER2013 emotion
  // - MRL eye state
  // - detected faces
  //
  // They are project-level AI indicators,
  // not the paper's exact engagement model.
  // =========================

  const liveMetrics = useMemo(() => {
    const faces = Array.isArray(liveFaces)
      ? liveFaces
      : [];

    if (faces.length === 0) {
      return {
        engagement: 0,
        attention: 0,
        participation: 0,
        positiveMood: 0,
        focusedStudents: 0,
        participatingStudents: 0,
        confusedStudents: 0,
      };
    }

    // -------------------------
    // ON-TASK PROXY
    // -------------------------
    //
    // Open / Blink = attention available
    //
    const onTaskStudents = faces.filter(
      (face) =>
        face.eye_state === "Open" ||
        face.eye_state === "Blink"
    );

    // -------------------------
    // OFF-TASK / LOW ATTENTION
    // -------------------------

    const offTaskStudents = faces.filter(
      (face) =>
        face.eye_state === "Close" ||
        face.eye_state === "Drowsy" ||
        face.eye_state === "Sleeping"
    );

    // -------------------------
    // SATISFIED / POSITIVE MOOD
    // -------------------------
    //
    // Happy + Neutral are used as
    // positive/satisfied proxies.
    //

    const satisfiedStudents = faces.filter(
      (face) =>
        face.emotion === "Happy" ||
        face.emotion === "Neutral"
    );

    // -------------------------
    // CONFUSION PROXY
    // -------------------------
    //
    // Fear / Angry can indicate
    // frustration or confusion.
    //
    // This is a heuristic because
    // FER2013 does not directly
    // contain a "Confused" class.
    //

    const confusedStudents = faces.filter(
      (face) =>
        face.emotion === "Fear" ||
        face.emotion === "Angry"
    );

    // -------------------------
    // BOREDOM PROXY
    // -------------------------
    //
    // Sad is used as a possible
    // disengagement/boredom signal.
    //

    const boredStudents = faces.filter(
      (face) =>
        face.emotion === "Sad"
    );

    // -------------------------
    // ENGAGED STUDENTS
    // -------------------------
    //
    // Paper structure:
    //
    // On-task + Satisfied = Engaged
    // On-task + Confused = Engaged
    //
    // We use our FER + eye-state
    // categories as proxies.
    //

    const engagedStudents = faces.filter(
      (face) => {
        const onTask =
          face.eye_state === "Open" ||
          face.eye_state === "Blink";

        const satisfied =
          face.emotion === "Happy" ||
          face.emotion === "Neutral";

        const confused =
          face.emotion === "Fear" ||
          face.emotion === "Angry";

        const bored =
          face.emotion === "Sad";

        if (!onTask) {
          return false;
        }

        if (bored) {
          return false;
        }

        return satisfied || confused;
      }
    );

    // -------------------------
    // PERCENTAGES
    // -------------------------

    const attention = Math.round(
      (onTaskStudents.length / faces.length) *
        100
    );

    const engagement = Math.round(
      (engagedStudents.length / faces.length) *
        100
    );

    const positiveMood = Math.round(
      (satisfiedStudents.length / faces.length) *
        100
    );

    // Participation is currently an
    // engagement-based proxy because
    // backend does not yet detect
    // actual hand raising/speaking.
    const participation = Math.round(
      (engagedStudents.length / faces.length) *
        100
    );

    return {
      engagement,
      attention,
      participation,
      positiveMood,

      focusedStudents:
        onTaskStudents.length,

      participatingStudents:
        engagedStudents.length,

      confusedStudents:
        confusedStudents.length,

      offTaskStudents:
        offTaskStudents.length,

      boredStudents:
        boredStudents.length,
    };
  }, [liveFaces]);

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

              <h3>
                Connect Classroom Camera
              </h3>

              <p>
                Choose between your laptop/PC webcam or stream from a mobile phone via IP Webcam.
              </p>

            </div>

            <div className="camera-mode-tabs">

              <button
                type="button"
                className={`camera-mode-tab ${
                  cameraMode === "webcam"
                    ? "active"
                    : ""
                }`}
                onClick={() => {
                  if (!cameraConnected) {
                    setCameraMode("webcam");
                    setCameraError("");
                  }
                }}
                disabled={
                  cameraConnected ||
                  cameraLoading
                }
              >
                💻 Laptop / PC Webcam
              </button>

              <button
                type="button"
                className={`camera-mode-tab ${
                  cameraMode === "phone"
                    ? "active"
                    : ""
                }`}
                onClick={() => {
                  if (!cameraConnected) {
                    setCameraMode("phone");
                    setCameraError("");
                  }
                }}
                disabled={
                  cameraConnected ||
                  cameraLoading
                }
              >
                📱 Phone Camera (IP)
              </button>

            </div>

          </div>

          {/* WEBCAM MODE */}

          {cameraMode === "webcam" && (

            <div className="camera-controls-wrapper">

              <div className="camera-webcam-row">

                <div className="camera-select-field">

                  <label htmlFor="webcam-select">
                    Camera Device:
                  </label>

                  <select
                    id="webcam-select"
                    value={webcamIndex}
                    onChange={(e) =>
                      setWebcamIndex(
                        e.target.value
                      )
                    }
                    disabled={
                      cameraLoading ||
                      cameraConnected
                    }
                  >

                    <option value="0">
                      Camera 0 (Default Built-in Webcam)
                    </option>

                    <option value="1">
                      Camera 1 (Secondary / External USB)
                    </option>

                    <option value="2">
                      Camera 2 (External Camera 2)
                    </option>

                  </select>

                </div>

                {!cameraConnected ? (

                  <button
                    className="camera-action-btn"
                    onClick={() =>
                      connectCamera("webcam")
                    }
                    disabled={cameraLoading}
                  >
                    {cameraLoading
                      ? "Starting Webcam..."
                      : "Start Laptop Webcam"}
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

          {/* PHONE MODE */}

          {cameraMode === "phone" && (

            <div className="camera-controls-wrapper">

              <div className="camera-url-row">

                <input
                  type="text"
                  value={cameraUrl}
                  onChange={(e) =>
                    setCameraUrl(e.target.value)
                  }
                  placeholder="Enter phone IP (e.g. 192.168.1.15) or full video URL"
                  disabled={
                    cameraLoading ||
                    cameraConnected
                  }
                />

                {!cameraConnected ? (

                  <button
                    className="camera-action-btn"
                    onClick={() =>
                      connectCamera("phone")
                    }
                    disabled={cameraLoading}
                  >
                    {cameraLoading
                      ? "Connecting..."
                      : "Connect Phone Camera"}
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

              ✓{" "}
              {activeCameraType === "webcam"
                ? "Laptop / PC Webcam"
                : "Phone Camera"}{" "}
              connected and streaming live

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

                  {/* FER OVERLAY */}

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

                    {cameraMode === "webcam"
                      ? "💻"
                      : "📱"}

                  </div>

                  <h3>

                    {cameraMode === "webcam"
                      ? "Laptop / PC Webcam"
                      : "Mobile IP Camera"}

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

            {/* OVERALL ENGAGEMENT */}

            <div className="engagement-score">

              <strong>
                {liveMetrics.engagement}%
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
                  {liveMetrics.attention}%
                </strong>

              </div>

              <div className="progress">

                <div
                  style={{
                    width: `${liveMetrics.attention}%`,
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
                  {liveMetrics.participation}%
                </strong>

              </div>

              <div className="progress">

                <div
                  style={{
                    width: `${liveMetrics.participation}%`,
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
                  {liveMetrics.positiveMood}%
                </strong>

              </div>

              <div className="progress">

                <div
                  style={{
                    width: `${liveMetrics.positiveMood}%`,
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

          {/* STUDENTS DETECTED */}

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

          {/* FOCUSED */}

          <div className="classroom-stat">

            <span>
              👁️
            </span>

            <div>

              <small>
                Focused Students
              </small>

              <strong>
                {liveMetrics.focusedStudents}
              </strong>

            </div>

          </div>

          {/* PARTICIPATING */}

          <div className="classroom-stat">

            <span>
              🙋
            </span>

            <div>

              <small>
                Participating
              </small>

              <strong>
                {liveMetrics.participatingStudents}
              </strong>

            </div>

          </div>

          {/* CONFUSED */}

          <div className="classroom-stat">

            <span>
              😕
            </span>

            <div>

              <small>
                Confused
              </small>

              <strong>
                {liveMetrics.confusedStudents}
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

            {/* CURRENT EMOTION */}

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

            {/* CONFIDENCE */}

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
                ).toFixed(1)}
                %
              </strong>

            </div>

            {/* FACES */}

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
            ANALYTICS BUTTONS
        ========================= */}

        <button
          className="recorded-video-button"
          onClick={() =>
            navigate("/recorded-video")
          }
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