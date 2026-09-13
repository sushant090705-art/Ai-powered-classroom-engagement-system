import { useEffect, useState } from "react";
import "./RecordedVideo.css";

function RecordedVideo() {
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [videoPreview, setVideoPreview] = useState("");
  const [analysisResult, setAnalysisResult] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");

  // Create and clean video preview URL
  useEffect(() => {
    if (!selectedVideo) {
      setVideoPreview("");
      return;
    }

    const videoUrl = URL.createObjectURL(selectedVideo);
    setVideoPreview(videoUrl);

    return () => {
      URL.revokeObjectURL(videoUrl);
    };
  }, [selectedVideo]);

  const handleVideoChange = (event) => {
    const file = event.target.files[0];

    if (!file) {
      return;
    }

    if (!file.type.startsWith("video/")) {
      setError("Please select a valid video file.");
      return;
    }

    setSelectedVideo(file);
    setAnalysisResult(null);
    setError("");
  };

  const handleRemoveVideo = () => {
    setSelectedVideo(null);
    setVideoPreview("");
    setAnalysisResult(null);
    setError("");
  };

  const handleAnalyzeVideo = async () => {
    if (!selectedVideo) {
      setError("Please upload a video first.");
      return;
    }

    setAnalyzing(true);
    setError("");
    setAnalysisResult(null);

    const formData = new FormData();
    formData.append("video", selectedVideo);

    try {
      const response = await fetch(
        "http://127.0.0.1:5000/analyze-video",
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

      setAnalysisResult(data);
    } catch (error) {
      console.error("Video analysis error:", error);
      setError(
        error.message ||
          "Unable to connect with the Flask backend."
      );
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="recorded-video-page">
      <div className="recorded-video-container">
        <h1>Recorded Video Analysis</h1>

        <p className="page-description">
          Upload a classroom recording and analyze student
          emotions using YOLO and FER.
        </p>

        <div className="upload-section">
          <label htmlFor="video-upload" className="upload-label">
            Select Classroom Video
          </label>

          <input
            id="video-upload"
            type="file"
            accept="video/*"
            onChange={handleVideoChange}
          />
        </div>

        {videoPreview && (
          <div className="video-preview-section">
            <video
              className="recorded-video-player"
              src={videoPreview}
              controls
            />

            <p className="video-name">
              {selectedVideo?.name}
            </p>

            <div className="video-actions">
              <button
                className="remove-video-button"
                onClick={handleRemoveVideo}
                disabled={analyzing}
              >
                Remove Video
              </button>

              <button
                className="analyze-video-button"
                onClick={handleAnalyzeVideo}
                disabled={analyzing}
              >
                {analyzing
                  ? "Analyzing Video..."
                  : "Analyze Video"}
              </button>
            </div>
          </div>
        )}

        {analyzing && (
          <div className="loading-message">
            <p>
              Please wait. YOLO and FER are analyzing your
              recorded video...
            </p>
          </div>
        )}

        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        {analysisResult && (
          <div className="analysis-result">
            <h2>Analysis Result</h2>

            <div className="result-item">
              <strong>Video Duration:</strong>
              <span>
                {analysisResult.duration_seconds} seconds
              </span>
            </div>

            <div className="result-item">
              <strong>Total Frames:</strong>
              <span>
                {analysisResult.total_frames}
              </span>
            </div>

            <div className="result-item">
              <strong>Processed Frames:</strong>
              <span>
                {analysisResult.processed_frames}
              </span>
            </div>

            <div className="result-item">
              <strong>Total Faces Detected:</strong>
              <span>
                {analysisResult.total_faces_detected}
              </span>
            </div>

            <div className="result-item">
              <strong>Most Common Emotion:</strong>
              <span>
                {analysisResult.most_common_emotion}
              </span>
            </div>

            <h3>Emotion Counts</h3>

            {Object.keys(
              analysisResult.emotion_counts || {}
            ).length > 0 ? (
              <ul className="emotion-list">
                {Object.entries(
                  analysisResult.emotion_counts
                ).map(([emotion, count]) => (
                  <li key={emotion}>
                    <span>{emotion}</span>
                    <strong>{count}</strong>
                  </li>
                ))}
              </ul>
            ) : (
              <p>
                No faces or emotions were detected in the
                video.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default RecordedVideo;