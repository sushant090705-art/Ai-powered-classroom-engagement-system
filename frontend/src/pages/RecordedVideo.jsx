import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import html2pdf from "html2pdf.js";
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

  // Progress of the running analysis
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState("");
  const [studentsFound, setStudentsFound] = useState(0);

  // Names typed by the teacher
  const [names, setNames] = useState({});

  const pollTimer = useRef(null);
  const reportRef = useRef(null);

  const [downloading, setDownloading] = useState(false);

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

  // Stop polling if the page is closed
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

    if (!file.type.startsWith("video/")) {
      setError("Please select a valid video file.");
      event.target.value = "";
      return;
    }

    if (videoPreview) {
      URL.revokeObjectURL(videoPreview);
    }

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

    const input = document.getElementById("video-upload");

    if (input) {
      input.value = "";
    }
  };

  // ============================================================
  // WAIT FOR BACKEND JOB
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
            reject(
              new Error(data.error || "Video analysis failed.")
            );
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

      const result = data.job_id
        ? await waitForJob(data.job_id)
        : data;

      console.log("VIDEO ANALYSIS RESULT:", result);

      setAnalysisResult(result);

      setSuccessMessage("Video analyzed successfully!");
    } catch (err) {
      console.error("Video analysis error:", err);

      setError(
        err.message || "Unable to analyze video."
      );
    } finally {
      setAnalyzing(false);
    }
  };

  // ============================================================
  // WAIT FOR IMAGES
  // ============================================================

  const waitForImages = async (container) => {
    const images = Array.from(
      container.querySelectorAll("img")
    );

    await Promise.all(
      images.map((img) => {
        if (img.complete && img.naturalWidth > 0) {
          return Promise.resolve();
        }

        return new Promise((resolve) => {
          const finish = () => resolve();

          img.addEventListener("load", finish, { once: true });
          img.addEventListener("error", finish, { once: true });

          // Avoid waiting forever for a broken image.
          setTimeout(finish, 10000);
        });
      })
    );

    // Decode loaded images before capturing the PDF.
    await Promise.all(
      images.map(async (img) => {
        if (typeof img.decode === "function") {
          try {
            await img.decode();
          } catch {
            // Continue if a browser cannot decode an image.
          }
        }
      })
    );
  };

  // ============================================================
  // DOWNLOAD PDF
  // ============================================================

  const downloadPDF = async () => {
    const element = reportRef.current;

    if (!element || downloading) {
      return;
    }

    setDownloading(true);

    let pdfContainer = null;

    try {
      // Clone the report so the visible page is not modified.
      const clone = element.cloneNode(true);

      // Remove buttons and interactive controls from the PDF.
      clone.querySelectorAll("button").forEach((button) => {
        button.remove();
      });

      clone.querySelectorAll("input").forEach((input) => {
        const replacement = document.createElement("span");
        replacement.textContent = input.value || "";
        input.parentNode?.replaceChild(replacement, input);
      });

      // Remove any elements that should not appear in the report.
      clone.querySelectorAll(".recorded-pdf-actions").forEach((item) => {
        item.remove();
      });

      // Build a clean PDF container.
      pdfContainer = document.createElement("div");

      Object.assign(pdfContainer.style, {
        position: "fixed",
        left: "-10000px",
        top: "0",
        width: "718px",
        background: "#ffffff",
        color: "#172033",
        zIndex: "-1",
        overflow: "visible",
        boxSizing: "border-box",
      });

      // PDF-specific styling.
      const style = document.createElement("style");

      style.textContent = `
        .recorded-pdf-content {
          width: 100% !important;
          max-width: 100% !important;
          height: auto !important;
          min-height: 0 !important;
          overflow: visible !important;
          background: #ffffff !important;
          color: #172033 !important;
          padding: 24px !important;
          box-sizing: border-box !important;
          font-family: Arial, Helvetica, sans-serif !important;
        }

        .recorded-pdf-content * {
          box-sizing: border-box !important;
          color: #172033 !important;
          box-shadow: none !important;
          text-shadow: none !important;
        }

        .recorded-pdf-content .result-header {
          margin-bottom: 20px !important;
          border-bottom: 1px solid #dbe2ea !important;
          padding-bottom: 14px !important;
        }

        .recorded-pdf-content .section-label {
          color: #52647a !important;
        }

        .recorded-pdf-content .sr-summary {
          display: grid !important;
          grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
          gap: 12px !important;
          margin-bottom: 22px !important;
        }

        .recorded-pdf-content .sr-summary > div {
          background: #f3f6fa !important;
          border: 1px solid #dbe2ea !important;
          border-radius: 10px !important;
          padding: 14px !important;
          break-inside: avoid !important;
          page-break-inside: avoid !important;
        }

        .recorded-pdf-content .sr-grid {
          display: flex !important;
          flex-direction: column !important;
          gap: 18px !important;
          width: 100% !important;
        }

        .recorded-pdf-content .sr-card {
          width: 100% !important;
          max-width: 100% !important;
          margin: 0 !important;
          background: #ffffff !important;
          border: 1px solid #dbe2ea !important;
          border-radius: 12px !important;
          overflow: visible !important;
          break-inside: avoid !important;
          page-break-inside: avoid !important;
        }

        .recorded-pdf-content .sr-card img {
          display: block !important;
          max-width: 100% !important;
          object-fit: cover !important;
        }

        .recorded-pdf-content img {
          max-width: 100% !important;
        }

        .recorded-pdf-content .result-notes {
          background: #f3f6fa !important;
          border: 1px solid #dbe2ea !important;
          border-radius: 10px !important;
          padding: 14px 14px 14px 34px !important;
          margin-bottom: 20px !important;
        }

        .recorded-pdf-content h1,
        .recorded-pdf-content h2,
        .recorded-pdf-content h3,
        .recorded-pdf-content h4,
        .recorded-pdf-content p,
        .recorded-pdf-content small,
        .recorded-pdf-content strong,
        .recorded-pdf-content span,
        .recorded-pdf-content li {
          color: #172033 !important;
        }

        .recorded-pdf-content .sr-card,
        .recorded-pdf-content .sr-summary > div {
          break-inside: avoid !important;
          page-break-inside: avoid !important;
        }

        .recorded-pdf-content .sr-card * {
          max-width: 100%;
        }
      `;

      pdfContainer.appendChild(style);

      clone.classList.add("recorded-pdf-content");

      clone.style.cssText += `
        width: 100%;
        max-width: 100%;
        height: auto;
        overflow: visible;
        background: #ffffff;
        color: #172033;
      `;

      pdfContainer.appendChild(clone);
      document.body.appendChild(pdfContainer);

      // Wait for all report images.
      await waitForImages(clone);

      // Allow layout and image rendering to finish.
      await new Promise((resolve) => {
        requestAnimationFrame(() => {
          requestAnimationFrame(resolve);
        });
      });

      const filename = (
        selectedVideo?.name || "Recorded-Video-Report"
      )
        .replace(/\.[^.]+$/, "")
        .replace(/[<>:"/\\|?*]/g, "-") + "-Report.pdf";

      const worker = html2pdf()
        .set({
          margin: [18, 10, 15, 10],
          filename,
          image: {
            type: "jpeg",
            quality: 0.98,
          },
          html2canvas: {
            scale: 2,
            useCORS: true,
            backgroundColor: "#ffffff",
            logging: false,
            scrollY: 0,
            windowWidth: 718,
          },
          jsPDF: {
            unit: "mm",
            format: "a4",
            orientation: "portrait",
            compress: true,
          },
          pagebreak: {
            mode: ["css", "legacy"],
            avoid: [
              ".sr-card",
              ".sr-summary > div",
            ],
          },
        })
        .from(clone)
        .toPdf();

      const pdf = await worker.get("pdf");

      const pages = pdf.internal.getNumberOfPages();

      // Add a simple header and footer to each page.
      for (let page = 1; page <= pages; page++) {
        pdf.setPage(page);

        const pageWidth = pdf.internal.pageSize.getWidth();
        const pageHeight = pdf.internal.pageSize.getHeight();

        pdf.setFillColor(255, 255, 255);
        pdf.rect(0, 0, pageWidth, 13, "F");

        pdf.setTextColor(30, 41, 59);
        pdf.setFont("helvetica", "bold");
        pdf.setFontSize(9);

        pdf.text("CLASSROOM AI", 12, 8);

        pdf.setTextColor(100, 116, 139);
        pdf.setFont("helvetica", "normal");
        pdf.setFontSize(8);

        pdf.text(
          "RECORDED VIDEO ANALYSIS REPORT",
          pageWidth - 12,
          8,
          { align: "right" }
        );

        pdf.setDrawColor(226, 232, 240);
        pdf.line(10, 14, pageWidth - 10, 14);

        pdf.setTextColor(100, 116, 139);
        pdf.setFontSize(8);

        pdf.text(
          `Page ${page} of ${pages}`,
          pageWidth / 2,
          pageHeight - 7,
          { align: "center" }
        );
      }

      pdf.save(filename);
    } catch (err) {
      console.error("PDF download failed:", err);

      setError(
        "Could not generate the PDF. Please try again."
      );
    } finally {
      if (pdfContainer?.parentNode) {
        pdfContainer.parentNode.removeChild(pdfContainer);
      }

      setDownloading(false);
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

        {/* HEADER */}

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

        {/* UPLOAD CARD */}

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

        {/* VIDEO PREVIEW */}

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
                  : "Analyze Video"}
              </button>
            </div>
          </div>
        )}

        {/* LOADING */}

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

        {/* ERROR */}

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

        {/* SUCCESS */}

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

        {/* ANALYSIS RESULT */}

        {analysisResult && (
          <div
            className="result-card sr-theme-light"
            ref={reportRef}
          >
            <div className="recorded-pdf-actions">
              <button
                type="button"
                className="analyze-button"
                onClick={downloadPDF}
                disabled={downloading}
              >
                {downloading
                  ? "Preparing PDF..."
                  : "Download Complete PDF"}
              </button>
            </div>

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
                  {Number(
                    analysisResult.total_faces_detected ??
                    students.length
                  )}
                </strong>
              </div>

              <div>
                <small>Class engagement</small>

                <strong>
                  {Number(
                    analysisResult.class_average_engagement ?? 0
                  )}%
                </strong>
              </div>

              <div>
                <small>Video length</small>

                <strong>
                  {formatDuration(
                    analysisResult.duration_seconds
                  )}
                </strong>
              </div>

              <div>
                <small>Frames analysed</small>

                <strong>
                  {Number(
                    analysisResult.processed_frames ?? 0
                  )}
                </strong>
              </div>
            </div>

            {/* NOTES */}

            {notes.length > 0 && (
              <ul className="result-notes">
                {notes.map((note, index) => (
                  <li key={`${index}-${note}`}>
                    {note}
                  </li>
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
                      name:
                        names[student.student_id] ??
                        student.name,
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