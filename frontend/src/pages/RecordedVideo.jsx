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

        URL.revokeObjectURL(
          videoPreview
        );
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


    // ----------------------------------------------------------
    // Validate file type
    // ----------------------------------------------------------

    if (!file.type.startsWith("video/")) {

      setError(
        "Please select a valid video file."
      );

      return;
    }


    // ----------------------------------------------------------
    // Remove old preview
    // ----------------------------------------------------------

    if (videoPreview) {

      URL.revokeObjectURL(
        videoPreview
      );
    }


    // ----------------------------------------------------------
    // Create new preview
    // ----------------------------------------------------------

    const previewUrl = URL.createObjectURL(
      file
    );


    setSelectedVideo(file);

    setVideoPreview(
      previewUrl
    );
  };


  // ============================================================
  // REMOVE VIDEO
  // ============================================================

  const removeVideo = () => {

    if (videoPreview) {

      URL.revokeObjectURL(
        videoPreview
      );
    }


    setSelectedVideo(null);

    setVideoPreview("");

    setAnalysisResult(null);

    setError("");

    setSuccessMessage("");
  };


  // ============================================================
  // ANALYZE VIDEO
  // ============================================================

  const handleAnalyzeVideo = async () => {

    if (!selectedVideo) {

      setError(
        "Please select a video first."
      );

      return;
    }


    setAnalyzing(true);

    setError("");

    setSuccessMessage("");

    setAnalysisResult(null);


    try {

      const formData = new FormData();

      formData.append(
        "video",
        selectedVideo
      );


      const response = await fetch(
        `${BACKEND_URL}/analyze-video`,
        {
          method: "POST",
          body: formData
        }
      );


      const data = await response.json();


      if (!response.ok || !data.success) {

        throw new Error(
          data.message ||
          "Video analysis failed."
        );
      }


      setAnalysisResult(
        data
      );


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
  // FORMAT EMOTION NAME
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
              analyze people, faces and emotions.
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

            <div className="result-header">

              <p className="section-label">
                AI ANALYSIS
              </p>

              <h2>
                Analysis Result
              </h2>

            </div>


            {/* ================================================== */}
            {/* BASIC VIDEO INFORMATION */}
            {/* ================================================== */}

            <div className="result-list">

              <div className="result-row">

                <strong>
                  Video Duration:
                </strong>

                <span>
                  {analysisResult.duration_seconds}
                  {" "}
                  seconds
                </span>

              </div>


              <div className="result-row">

                <strong>
                  Total Frames:
                </strong>

                <span>
                  {analysisResult.total_frames}
                </span>

              </div>


              <div className="result-row">

                <strong>
                  Processed Frames:
                </strong>

                <span>
                  {analysisResult.processed_frames}
                </span>

              </div>


              {/* IMPORTANT */}
             <div className="result-row highlight-row">

  <strong>
    Unique Persons Detected:
  </strong>

  <span>
    {Number(
      analysisResult.unique_persons_detected ??
      analysisResult.unique_persons ??
      analysisResult.total_persons ??
      0
    )}
  </span>

</div>


              {/* FACE DETECTIONS */}
              <div className="result-row">

  <strong>
    Face Detections:
  </strong>

  <span>
    {Number(
      analysisResult.face_detections ??
      analysisResult.total_faces_detected ??
      analysisResult.faces_detected ??
      0
    )}
  </span>

</div>

              {/* MOST COMMON EMOTION */}
              <div className="result-row emotion-result-row">

                <strong>
                  Most Common Emotion:
                </strong>

                <span className="main-emotion">

                  <span className="emotion-big-emoji">
                    {getEmotionEmoji(
                      analysisResult.most_common_emotion
                    )}
                  </span>

                  {analysisResult.most_common_emotion}

                </span>

              </div>

            </div>


            {/* ================================================== */}
            {/* EMOTION COUNTS */}
            {/* ================================================== */}

            <div className="emotion-section">

              <h3>
                Emotion Counts
              </h3>


              {analysisResult.emotion_counts &&
              Object.keys(
                analysisResult.emotion_counts
              ).length > 0 ? (

                <div className="emotion-grid">

                  {Object.entries(
                    analysisResult.emotion_counts
                  ).map(
                    (
                      [
                        emotion,
                        count
                      ]
                    ) => (

                      <div
                        className="emotion-box"
                        key={emotion}
                      >

                        <div className="emotion-box-icon">

                          {getEmotionEmoji(
                            emotion
                          )}

                        </div>

                        <div>

                          <span className="emotion-name">

                            {emotion}

                          </span>

                          <span className="emotion-count">

                            {count}

                          </span>

                        </div>

                      </div>

                    )
                  )}

                </div>

              ) : (

                <p className="no-data">
                  No emotions detected.
                </p>

              )}

            </div>


            {/* ================================================== */}
            {/* PERSON SUMMARY */}
            {/* ================================================== */}

            {analysisResult.person_summary &&
            analysisResult.person_summary.length > 0 && (

              <div className="person-section">

                <h3>
                  Person-wise Analysis
                </h3>


                <div className="person-grid">

                  {analysisResult.person_summary.map(
                    (person) => (

                      <div
                        className="person-card"
                        key={person.person_id}
                      >

                        <div className="person-title">

                          <span>
                            👤
                          </span>

                          <strong>
                            Person {person.person_id}
                          </strong>

                        </div>


                        <div className="person-emotion">

                          <span>
                            Main Emotion
                          </span>

                          <strong>

                            {getEmotionEmoji(
                              person.most_common_emotion
                            )}

                            {" "}

                            {person.most_common_emotion}

                          </strong>

                        </div>


                        <div className="person-samples">

                          Samples analyzed:

                          {" "}

                          {person.samples_analyzed}

                        </div>

                      </div>

                    )
                  )}

                </div>

              </div>

            )}

          </div>

        )}

      </div>

    </div>
  );
}

export default RecordedVideo;