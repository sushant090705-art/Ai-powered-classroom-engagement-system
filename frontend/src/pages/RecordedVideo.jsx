import { useEffect, useState } from "react";
import "./RecordedVideo.css";

function RecordedVideo() {
  const BACKEND_URL = "http://127.0.0.1:5000";

  const [selectedVideo, setSelectedVideo] = useState(null);
  const [videoPreview, setVideoPreview] = useState("");
  const [analysisResult, setAnalysisResult] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  // ============================================================
  // CLEAN VIDEO URL
  // ============================================================

  useEffect(() => {
    return () => {
      if (videoPreview) {
        URL.revokeObjectURL(videoPreview);
      }
    };
  }, [videoPreview]);

  // ============================================================
  // SELECT VIDEO
  // ============================================================

  const handleVideoSelect = (event) => {
    const file = event.target.files?.[0];

    setError("");
    setSuccessMessage("");
    setAnalysisResult(null);

    if (!file) {
      return;
    }

    // Validate video
    if (!file.type.startsWith("video/")) {
      setError("Please select a valid video file.");
      return;
    }

    // Remove old preview
    if (videoPreview) {
      URL.revokeObjectURL(videoPreview);
    }

    // Create new preview
    const previewUrl = URL.createObjectURL(file);

    setSelectedVideo(file);
    setVideoPreview(previewUrl);
  };

  // ============================================================
  // REMOVE VIDEO
  // ============================================================

  const removeVideo = () => {
    if (videoPreview) {
      URL.revokeObjectURL(videoPreview);
    }

    setSelectedVideo(null);
    setVideoPreview("");
    setAnalysisResult(null);
    setError("");
    setSuccessMessage("");

    // Reset file input
    const input = document.getElementById("video-upload");

    if (input) {
      input.value = "";
    }
  };

  // ============================================================
  // ANALYZE VIDEO
  // ============================================================

  const handleAnalyzeVideo = async () => {
    if (!selectedVideo) {
      setError("Please select a video first.");
      return;
    }

    setAnalyzing(true);
    setError("");
    setSuccessMessage("");
    setAnalysisResult(null);

    try {
      const formData = new FormData();

      formData.append("video", selectedVideo);

      const response = await fetch(
        `${BACKEND_URL}/analyze-video`,
        {
          method: "POST",
          body: formData,
        }
      );

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.message || "Video analysis failed."
        );
      }

      console.log("VIDEO ANALYSIS RESULT:", data);

      setAnalysisResult(data);

      setSuccessMessage(
        "Video analyzed successfully!"
      );
    } catch (err) {
      console.error(
        "Video analysis error:",
        err
      );

      setError(
        err.message ||
        "Unable to analyze video."
      );
    } finally {
      setAnalyzing(false);
    }
  };

  // ============================================================
  // EMOTION EMOJI
  // ============================================================

  const getEmotionEmoji = (emotion) => {
    switch (emotion) {
      case "Happy":
        return "😊";

      case "Sad":
        return "😢";

      case "Angry":
        return "😠";

      case "Fear":
        return "😨";

      case "Disgust":
        return "🤢";

      case "Surprise":
        return "😮";

      case "Neutral":
        return "😐";

      default:
        return "🙂";
    }
  };

  // ============================================================
  // RENDER
  // ============================================================

  return (
    <div className="recorded-video-page">

      <div className="recorded-video-container">

        {/* ================================================== */}
        {/* HEADER */}
        {/* ================================================== */}

        <div className="recorded-header">

          <div>

            <p className="page-label">
              CLASSROOM AI
            </p>

            <h1>
              Recorded Video Analysis
            </h1>

            <p className="page-description">
              Upload a classroom recording and let AI
              analyze faces and emotions.
            </p>

          </div>

        </div>


        {/* ================================================== */}
        {/* UPLOAD CARD */}
        {/* ================================================== */}

        <div className="upload-card">

          <div className="upload-icon">
            🎥
          </div>

          <h2>
            Upload Classroom Video
          </h2>

          <p>
            Select a recorded classroom video
            for AI analysis.
          </p>

          <label
            className="upload-button"
            htmlFor="video-upload"
          >
            Select Video
          </label>

          <input
            id="video-upload"
            type="file"
            accept="video/*"
            onChange={handleVideoSelect}
            hidden
          />

        </div>


        {/* ================================================== */}
        {/* VIDEO PREVIEW */}
        {/* ================================================== */}

        {videoPreview && (

          <div className="preview-card">

            <div className="section-header">

              <div>

                <p className="section-label">
                  SELECTED VIDEO
                </p>

                <h2>
                  Video Preview
                </h2>

              </div>

            </div>


            <video
              src={videoPreview}
              controls
              className="video-preview"
            />


            {selectedVideo && (

              <p className="file-name">
                {selectedVideo.name}
              </p>

            )}


            <div className="video-actions">

              <button
                className="remove-button"
                onClick={removeVideo}
                disabled={analyzing}
              >
                Remove Video
              </button>


              <button
                className="analyze-button"
                onClick={handleAnalyzeVideo}
                disabled={analyzing}
              >

                {analyzing
                  ? "Analyzing..."
                  : "Analyze Video"
                }

              </button>

            </div>

          </div>

        )}


        {/* ================================================== */}
        {/* LOADING */}
        {/* ================================================== */}

        {analyzing && (

          <div className="loading-card">

            <div className="loading-spinner"></div>

            <h3>
              AI is analyzing your video...
            </h3>

            <p>
              YOLO is detecting people,
              Haar is detecting faces and
              FER is analyzing emotions.
            </p>

            <span>
              Please wait. This may take some time.
            </span>

          </div>

        )}


        {/* ================================================== */}
        {/* ERROR */}
        {/* ================================================== */}

        {error && (

          <div className="message-card error-card">

            <strong>
              Analysis Error
            </strong>

            <p>
              {error}
            </p>

          </div>

        )}


        {/* ================================================== */}
        {/* SUCCESS */}
        {/* ================================================== */}

        {successMessage && !analyzing && (

          <div className="message-card success-card">

            <strong>
              ✓ Analysis Complete
            </strong>

            <p>
              {successMessage}
            </p>

          </div>

        )}


        {/* ================================================== */}
        {/* ANALYSIS RESULT */}
        {/* ================================================== */}

        {analysisResult && (

          <div className="result-card">

            {/* RESULT HEADER */}

            <div className="result-header">

              <p className="section-label">
                AI ANALYSIS
              </p>

              <h2>
                Analysis Result
              </h2>

            </div>


            {/* ================================================== */}
            {/* TOTAL FACES DETECTED */}
            {/* ================================================== */}

            <div className="result-list">

              <div className="result-row highlight-row">

                <strong>
                  Total Faces Detected:
                </strong>

                <span>
                  {Number(
                    analysisResult.total_faces_detected ?? 0
                  )}
                </span>

              </div>

            </div>


            {/* ================================================== */}
            {/* FACE-WISE EMOTION ANALYSIS */}
            {/* ================================================== */}

            <div className="person-section">

              <h3>
                Face-wise Emotion Analysis
              </h3>


              {Array.isArray(
                analysisResult.person_summary
              ) &&
              analysisResult.person_summary.length > 0 ? (

                <div className="person-grid">

                  {analysisResult.person_summary.map(
                    (person) => (

                      <div
                        className="person-card"
                        key={person.person_id}
                      >

                        {/* FACE NUMBER */}

                        <div className="person-title">

                          <span>
                            👤
                          </span>

                          <strong>
                            Face {person.person_id}
                          </strong>

                        </div>


                        {/* EMOTION */}

                        <div className="person-emotion">

                          <span>
                            Overall Emotion
                          </span>

                          <strong>

                            {getEmotionEmoji(
                              person.most_common_emotion
                            )}

                            {" "}

                            {person.most_common_emotion ||
                              "Unknown"}

                          </strong>

                        </div>

                      </div>

                    )
                  )}

                </div>

              ) : (

                <div className="no-data">

                  <p>
                    No faces were detected in
                    this video.
                  </p>

                </div>

              )}

            </div>

          </div>

        )}

      </div>

    </div>
  );
}

export default RecordedVideo;