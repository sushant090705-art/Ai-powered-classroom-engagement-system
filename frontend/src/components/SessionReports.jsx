
import { useCallback, useEffect, useRef, useState } from "react";
import html2pdf from "html2pdf.js";
import StudentReportCard from "./StudentReportCard";
import { formatDuration } from "../utils/formatDuration";
import "./SessionReports.css";

const POLL_MS = 10000;
const LEVELS = ["Engaged", "Moderate", "Low"];
const LEVEL_TONE = { Engaged: "good", Moderate: "warn", Low: "bad" };

function tone(score) {
  if (score >= 75) return "good";
  if (score >= 50) return "warn";
  return "bad";
}

function formatDate(seconds) {
  return new Date(seconds * 1000).toLocaleString([], {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function TrendLine({ trend }) {
  if (!trend || trend.length < 2) return null;

  const W = 600;
  const H = 120;
  const step = W / (trend.length - 1);

  const points = trend
    .map(
      (p, i) =>
        `${(i * step).toFixed(1)},${(
          H - 8 - (p.value / 100) * (H - 16)
        ).toFixed(1)}`
    )
    .join(" ");

  return (
    <svg
      className="ssr-trend"
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      role="img"
      aria-label="Engagement during the session"
    >
      <polyline
        points={points}
        fill="none"
        stroke="#a3e635"
        strokeWidth="3"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

function ReportDetail({ report, onClose, onDelete }) {
  const reportRef = useRef(null);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === "Escape") onClose();
    };

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

 

const downloadPDF = async () => {
  const element = reportRef.current;

  if (!element || downloading) return;

  setDownloading(true);

  let pdfContainer = null;

  try {
    const clone = element.cloneNode(true);

    const originalElements = [
      element,
      ...element.querySelectorAll("*"),
    ];

    const clonedElements = [
      clone,
      ...clone.querySelectorAll("*"),
    ];

    originalElements.forEach((original, index) => {
      const copied = clonedElements[index];
      const computed = window.getComputedStyle(original);

      for (let i = 0; i < computed.length; i++) {
        const property = computed[i];
        let value = computed.getPropertyValue(property);

        if (/color\(/i.test(value)) {
          if (property.includes("background")) {
            value = "#080808";
          } else if (property === "color") {
            value = "#f5f5f5";
          } else if (property.includes("border")) {
            value = "#303030";
          } else if (
            property === "fill" ||
            property === "stroke"
          ) {
            value = "#a3e635";
          } else {
            continue;
          }
        }

        try {
          copied.style.setProperty(property, value);
        } catch {
          // Ignore unsupported CSS properties.
        }
      }

      copied.removeAttribute("class");
      copied.removeAttribute("id");
    });

    pdfContainer = document.createElement("div");

    Object.assign(pdfContainer.style, {
      position: "fixed",
      left: "-10000px",
      top: "0",
      width: "794px",
      background: "#080808",
      color: "#f5f5f5",
      zIndex: "-1",
      overflow: "visible",
    });

    clone.style.setProperty("width", "100%", "important");
    clone.style.setProperty("height", "auto", "important");
    clone.style.setProperty("overflow", "visible", "important");
    clone.style.setProperty("background", "#080808", "important");
    clone.style.setProperty("color", "#f5f5f5", "important");

    pdfContainer.appendChild(clone);
    document.body.appendChild(pdfContainer);

    clone.querySelectorAll(
      ".ssr-modal-actions, button"
    ).forEach((button) => button.remove());

    const safeTitle = (report.title || "Session-Report")
      .replace(/[<>:"/\\|?*]/g, "-")
      .trim();

    const worker = html2pdf()
      .set({
        margin: [18, 12, 18, 12],
        filename: `${safeTitle}.pdf`,
        image: {
          type: "jpeg",
          quality: 0.98,
        },
        html2canvas: {
          scale: 2,
          useCORS: true,
          backgroundColor: "#080808",
          logging: false,
          scrollY: 0,
          windowWidth: 794,
        },
        jsPDF: {
          unit: "mm",
          format: "a4",
          orientation: "portrait",
        },
        pagebreak: {
          mode: ["css", "legacy"],
        },
      })
      .from(clone)
      .toPdf();

    const pdf = await worker.get("pdf");
    const totalPages = pdf.internal.getNumberOfPages();

    for (let page = 1; page <= totalPages; page++) {
      pdf.setPage(page);

      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();

      // Header
      pdf.setFillColor(8, 8, 8);
      pdf.rect(0, 0, pageWidth, 13, "F");

      pdf.setTextColor(163, 230, 53);
      pdf.setFontSize(9);
      pdf.setFont("helvetica", "bold");
      pdf.text("CLASSROOM AI", 12, 8);

      pdf.setTextColor(190, 190, 190);
      pdf.setFontSize(8);
      pdf.setFont("helvetica", "normal");
      pdf.text("SESSION ANALYTICS REPORT", pageWidth - 12, 8, {
        align: "right",
      });

      // Footer
      pdf.setDrawColor(70, 70, 70);
      pdf.line(12, pageHeight - 13, pageWidth - 12, pageHeight - 13);

      pdf.setTextColor(170, 170, 170);
      pdf.setFontSize(8);
      pdf.text("Generated by ClassroomAI", 12, pageHeight - 7);

      pdf.text(
        `Page ${page} of ${totalPages}`,
        pageWidth - 12,
        pageHeight - 7,
        { align: "right" }
      );
    }

    pdf.save(`${safeTitle}.pdf`);
  } catch (error) {
    console.error("PDF download failed:", error);
    window.alert("PDF generation failed. Please try again.");
  } finally {
    if (pdfContainer) {
      pdfContainer.remove();
    }

    setDownloading(false);
  }
};


  const moods = Object.entries(
    report.emotion_distribution || {}
  ).sort((a, b) => b[1] - a[1]);

  const students = report.students || [];

  return (
    <div className="ssr-overlay" onClick={onClose}>
      <div
        className="ssr-modal"
        role="dialog"
        aria-modal="true"
        aria-label={report.title}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="ssr-modal-head">
          <div className="ssr-report-heading">
            <span className="ssr-eyebrow">
              CLASSROOM ANALYTICS / SESSION REPORT
            </span>

            <h2>{report.title}</h2>

            <p>
              {formatDate(report.started_at)} –{" "}
              {formatDate(report.ended_at)}
              <span className="ssr-date-separator"> · </span>
              Duration: {formatDuration(report.duration_seconds)}
            </p>
          </div>

          <div className="ssr-modal-actions">
            <button
              className="ssr-btn ssr-btn--primary"
              onClick={downloadPDF}
              disabled={downloading}
            >
              {downloading ? "Generating PDF..." : "↓ Download PDF"}
            </button>

            <button
              className="ssr-btn ssr-btn--danger"
              onClick={() => onDelete(report)}
            >
              Delete report
            </button>

            <button
              className="ssr-btn"
              onClick={onClose}
              aria-label="Close report"
            >
              Close
            </button>
          </div>
        </header>

        <div className="ssr-report-body">
          <div className="ssr-pdf-content" ref={reportRef}>
            <div className="ssr-pdf-title">
              <span className="ssr-eyebrow">
                CLASSROOM ANALYTICS
              </span>
              <h2>{report.title}</h2>
              <p>
                {formatDate(report.started_at)} –{" "}
                {formatDate(report.ended_at)}
              </p>
              <p>
                Duration: {formatDuration(report.duration_seconds)}
              </p>
            </div>

            <div className="ssr-section-heading">
              <div>
                <span className="ssr-eyebrow">SESSION OVERVIEW</span>
                <h3>Performance summary</h3>
              </div>
            </div>

            <div className="ssr-stats">
              <div className="ssr-stat-card">
                <span className="ssr-stat-label">Total students</span>
                <strong>{report.students_total}</strong>
                <small>Students detected</small>
              </div>

              <div className="ssr-stat-card ssr-stat-card--highlight">
                <span className="ssr-stat-label">Class engagement</span>
                <strong>{report.class_average_engagement}%</strong>
                <small>Average engagement score</small>
              </div>

              <div className="ssr-stat-card">
                <span className="ssr-stat-label">Attention score</span>
                <strong>{report.attention}%</strong>
                <small>Class attention level</small>
              </div>

              <div className="ssr-stat-card">
                <span className="ssr-stat-label">Peak students</span>
                <strong>{report.peak_students}</strong>
                <small>Highest detected at once</small>
              </div>
            </div>

            <section className="ssr-report-section">
              <div className="ssr-section-heading">
                <div>
                  <span className="ssr-eyebrow">
                    ENGAGEMENT BREAKDOWN
                  </span>
                  <h3>Student engagement levels</h3>
                </div>
              </div>

              <div className="ssr-levels">
                {LEVELS.map((level) => (
                  <div
                    key={level}
                    className={`ssr-level ssr-level--${LEVEL_TONE[level]}`}
                  >
                    <span className="ssr-level-dot" />
                    <span>{level}</span>
                    <strong>
                      {report.engagement_levels?.[level] || 0}
                    </strong>
                  </div>
                ))}
              </div>
            </section>

            <div className="ssr-two">
              <section className="ssr-report-panel">
                <div className="ssr-panel-heading">
                  <div>
                    <span className="ssr-eyebrow">
                      SESSION TIMELINE
                    </span>
                    <h3>Engagement trend</h3>
                  </div>
                </div>

                <div className="ssr-chart-area">
                  <div className="ssr-chart-scale">
                    <span>100%</span>
                    <span>50%</span>
                    <span>0%</span>
                  </div>

                  <div className="ssr-chart-content">
                    <div className="ssr-chart-guides">
                      <span />
                      <span />
                      <span />
                    </div>
                    <TrendLine trend={report.engagement_trend} />
                  </div>
                </div>

                {(!report.engagement_trend ||
                  report.engagement_trend.length < 2) && (
                  <p className="ssr-muted">
                    The session was too short to draw a trend.
                  </p>
                )}
              </section>

              <section className="ssr-report-panel">
                <div className="ssr-panel-heading">
                  <div>
                    <span className="ssr-eyebrow">
                      EMOTION ANALYSIS
                    </span>
                    <h3>Class mood distribution</h3>
                  </div>
                </div>

                <div className="ssr-moods">
                  {moods.map(([name, percent]) => (
                    <div className="ssr-mood" key={name}>
                      <div className="ssr-mood-info">
                        <span>{name}</span>
                        <strong>{percent}%</strong>
                      </div>

                      <div className="ssr-track">
                        <div
                          style={{ width: `${percent}%` }}
                        />
                      </div>
                    </div>
                  ))}

                  {moods.length === 0 && (
                    <p className="ssr-muted">
                      No emotion distribution data is available.
                    </p>
                  )}
                </div>
              </section>
            </div>

            <section className="ssr-students-section">
              <div className="ssr-section-heading">
                <div>
                  <span className="ssr-eyebrow">
                    INDIVIDUAL PERFORMANCE
                  </span>
                  <h3>Student-wise analysis</h3>
                  <p>
                    Students grouped by their engagement level.
                  </p>
                </div>
              </div>

              {LEVELS.map((level) => {
                const group = students.filter(
                  (s) => s.engagement?.level === level
                );

                if (group.length === 0) return null;

                return (
                  <div key={level} className="ssr-group">
                    <div className="ssr-group-heading">
                      <div
                        className={`ssr-group-indicator ssr-group-indicator--${LEVEL_TONE[level]}`}
                      />
                      <h4>{level} students</h4>
                      <span>{group.length} students</span>
                    </div>

                    <div className="sr-grid">
                      {group.map((student) => (
                        <StudentReportCard
                          key={student.student_id}
                          student={student}
                        />
                      ))}
                    </div>
                  </div>
                );
              })}
            </section>

            <div className="ssr-pdf-footer">
              <span>ClassroomAI</span>
              <span>Session Analytics Report</span>
            </div>
          </div>
        </div>

        <footer className="ssr-report-footer">
          <span>ClassroomAI · Session analytics report</span>
          <button className="ssr-btn" onClick={onClose}>
            Close report
          </button>
        </footer>
      </div>
    </div>
  );
}

function SessionReports({ backendUrl }) {
  const [reports, setReports] = useState(null);
  const [error, setError] = useState("");
  const [openReport, setOpenReport] = useState(null);
  const [busyId, setBusyId] = useState("");

  const load = useCallback(async () => {
    try {
      const response = await fetch(`${backendUrl}/reports`);

      if (!response.ok) throw new Error("Bad response");

      const data = await response.json();
      setReports(data.reports || []);
      setError("");
    } catch {
      setError(
        "Cannot load saved reports. Make sure the backend is running."
      );
    }
  }, [backendUrl]);

  useEffect(() => {
    load();

    const interval = setInterval(load, POLL_MS);
    return () => clearInterval(interval);
  }, [load]);

  const open = async (id) => {
    setBusyId(id);

    try {
      const response = await fetch(`${backendUrl}/reports/${id}`);

      if (!response.ok) throw new Error("Could not open report");

      const data = await response.json();

      if (data.success) {
        setOpenReport(data.report);
      } else {
        setError("Could not open this report.");
      }
    } catch {
      setError("Could not open this report.");
    } finally {
      setBusyId("");
    }
  };

  const remove = async (report) => {
    if (
      !window.confirm(
        `Delete "${report.title}"? This cannot be undone.`
      )
    ) {
      return;
    }

    try {
      const response = await fetch(
        `${backendUrl}/reports/${report.id}`,
        { method: "DELETE" }
      );

      if (!response.ok) throw new Error("Delete failed");

      setOpenReport(null);
      load();
    } catch {
      setError("Could not delete this report.");
    }
  };

  return (
    <section className="ssr">
      <div className="ssr-head">
        <div>
          <span className="ssr-eyebrow">CLASSROOM ANALYTICS</span>
          <h2>Session reports</h2>
          <p>
            Review classroom performance and engagement from your
            saved sessions.
          </p>
        </div>

        <button className="ssr-btn ssr-refresh-btn" onClick={load}>
          <span aria-hidden="true">↻</span>
          Refresh reports
        </button>
      </div>

      <div className="ssr-list-heading">
        <div>
          <h3>Saved sessions</h3>
          <p>
            {reports
              ? `${reports.length} saved ${
                  reports.length === 1 ? "session" : "sessions"
                }`
              : "Loading your saved sessions"}
          </p>
        </div>

        <span className="ssr-live-indicator">
          <span />
          Auto refresh
        </span>
      </div>

      {error && <div className="ssr-empty ssr-error">{error}</div>}

      {!error && reports === null && (
        <div className="ssr-empty">
          <span className="ssr-empty-icon">◷</span>
          <strong>Loading session reports</strong>
          <p>Please wait while your saved reports are fetched.</p>
        </div>
      )}

      {reports && reports.length === 0 && !error && (
        <div className="ssr-empty">
          <span className="ssr-empty-icon">▤</span>
          <strong>No saved reports yet</strong>
          <p>
            Start a live classroom session, then stop the camera
            to save your first report.
          </p>
        </div>
      )}

      {reports && reports.length > 0 && (
        <div className="ssr-list">
          {reports.map((report) => (
            <article className="ssr-row" key={report.id}>
              <div className="ssr-row-icon" aria-hidden="true">
                <span>▤</span>
              </div>

              <div className="ssr-row-main">
                <span className="ssr-row-label">SESSION REPORT</span>
                <strong>{report.title}</strong>
                <span className="ssr-row-meta">
                  {report.students_total} students
                  <span>·</span>
                  {formatDuration(report.duration_seconds)}
                  <span>·</span>
                  {formatDate(report.ended_at)}
                </span>
              </div>

              <div className="ssr-row-score">
                <span
                  className={`ssr-score ssr-score--${tone(
                    report.class_average_engagement
                  )}`}
                >
                  {report.class_average_engagement}%
                </span>
                <small>Class engagement</small>
              </div>

              <div className="ssr-row-actions">
                <button
                  className="ssr-btn ssr-btn--primary"
                  onClick={() => open(report.id)}
                  disabled={busyId === report.id}
                >
                  {busyId === report.id ? "Opening…" : "View report"}
                  <span aria-hidden="true">↗</span>
                </button>

                <button
                  className="ssr-btn ssr-btn--danger"
                  onClick={() => remove(report)}
                >
                  Delete
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      {openReport && (
        <ReportDetail
          report={openReport}
          onClose={() => setOpenReport(null)}
          onDelete={remove}
        />
      )}
    </section>
  );
}

export default SessionReports;
