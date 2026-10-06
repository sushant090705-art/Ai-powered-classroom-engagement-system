import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import StudentReportCard from "../components/StudentReportCard";
import { formatDuration } from "../utils/formatDuration";
import "./RecordedVideo.css";

function RecordedVideo() {
  const BACKEND_URL = "http://127.0.0.1:5000";

  const navigate = useNavigate();

  const [selectedVideo, setSelectedVideo] = useState(null);
  const [videoPreview, setVideoPreview] = useState("");
  const [analysisResult, setAnalysisResult] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  // progress of the running analysis
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState("");
  const [studentsFound, setStudentsFound] = useState(0);

  // names typed by the teacher (video students are not saved on the server)
  const [names, setNames] = useState({});

  const pollTimer = useRef(null);

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

  // stop polling if the page is closed mid-analysis
  useEffect(() => {
    return () => {
      if (pollTimer.current) {
        clearTimeout(pollTimer.current);
      }
    };
  }, []);

  // ============================================================
  // SELECT VIDEO
  // ============================================================

  const handleVideoSelect = (event) => {
    const file = event.target.files?.[0];

    setError("");
    setSuccessMessage("");
    setAnalysisResult(null);
    setNames({});

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
    setNames({});
    setError("");
    setSuccessMessage("");

    // Reset file input
    const input = document.getElementById("video-upload");

    if (input) {
      input.value = "";
    }
  };

  // ============================================================
  // WAIT FOR THE BACKEND JOB (shows live progress)
  // ============================================================

  const waitForJob = (jobId) =>
    new Promise((resolve, reject) => {
      const check = async () => {
        try {
          const response = await fetch(
            `${BACKEND_URL}/analyze-video/status/${jobId}`
          );

          const data = await response.json();

          if (!response.ok || !data.success) {
            throw new Error(
              data.message || "Lost track of the analysis."
            );
          }

          setProgress(Number(data.progress) || 0);
          setStage(data.stage || "");
          setStudentsFound(Number(data.students_found) || 0);

          if (data.status === "done") {
            resolve(data.result);
            return;
          }

          if (data.status === "error") {
            reject(new Error(data.error || "Video analysis failed."));
            return;
          }

          pollTimer.current = setTimeout(check, 1500);
        } catch (err) {
          reject(err);
        }
      };

      check();
    });

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
    setNames({});
    setProgress(0);
    setStage("Uploading video");
    setStudentsFound(0);

    try {
      const formData = new FormData();

      formData.append("video", selectedVideo);
      formData.append("async", "1");

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

      // New backend: a job id to follow. Older backend: the result itself.
      const result = data.job_id
        ? await waitForJob(data.job_id)
        : data;

      console.log("VIDEO ANALYSIS RESULT:", result);

      setAnalysisResult(result);

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
  // RESULT HELPERS
  // ============================================================

  const students = Array.isArray(analysisResult?.students)
    ? analysisResult.students
    : [];

  const notes = Array.isArray(analysisResult?.notes)
    ? analysisResult.notes
    : [];

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

          <button
            type="button"
            className="back-button"
            onClick={() => navigate("/classroom")}
          >
            ← Back to Classroom
          </button>

          <p className="page-label">
            CLASSROOM AI
          </p>

          <h1>
            Recorded Video Analysis
          </h1>

          <p className="page-description">
            Upload a classroom recording and get an individual report
            for every student: emotions, attention, eye status and
            engagement.
          </p>

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
            disabled={analyzing}
            hidden
          />

          <small className="upload-hint">
            Works best when faces are clearly visible, well lit and not
            too small.
          </small>

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

            <div className="progress-track">
              <div
                className="progress-fill"
                style={{
                  width: `${Math.round(progress * 100)}%`,
                }}
              />
            </div>

            <p>
              {stage || "Working"}
              {progress > 0 &&
                ` · ${Math.round(progress * 100)}%`}
              {studentsFound > 0 &&
                ` · ${studentsFound} student${
                  studentsFound === 1 ? "" : "s"
                } found so far`}
            </p>

            <span>
              Please keep this page open. Longer videos take a few
              minutes.
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

          <div className="result-card sr-theme-light">

            <div className="result-header">

              <p className="section-label">
                AI ANALYSIS
              </p>

              <h2>
                Student Reports
              </h2>

            </div>


            {/* SUMMARY */}

            <div className="sr-summary">

              <div>
                <small>Students detected</small>
                <strong>
                  {Number(analysisResult.total_faces_detected ?? students.length)}
                </strong>
              </div>

              <div>
                <small>Class engagement</small>
                <strong>
                  {Number(analysisResult.class_average_engagement ?? 0)}%
                </strong>
              </div>

              <div>
                <small>Video length</small>
                <strong>
                  {formatDuration(analysisResult.duration_seconds)}
                </strong>
              </div>

              <div>
                <small>Frames analysed</small>
                <strong>
                  {Number(analysisResult.processed_frames ?? 0)}
                </strong>
              </div>

            </div>


            {/* NOTES */}

            {notes.length > 0 && (

              <ul className="result-notes">

                {notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}

              </ul>

            )}


            {/* PER-STUDENT REPORTS */}

            {students.length > 0 ? (

              <div className="sr-grid">

                {students.map((student) => (

                  <StudentReportCard
                    key={student.student_id}
                    student={{
                      ...student,
                      name: names[student.student_id] ?? student.name,
                    }}
                    onRename={(name) =>
                      setNames((previous) => ({
                        ...previous,
                        [student.student_id]: name,
                      }))
                    }
                  />

                ))}

              </div>

            ) : (

              <div className="no-data">

                <p>
                  No students were detected in this video.
                </p>

              </div>

            )}

          </div>

        )}

      </div>

    </div>
  );
}

export default RecordedVideo;
