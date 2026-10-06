import { useCallback, useEffect, useState } from "react";
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
    .map((p, i) => `${(i * step).toFixed(1)},${(H - 8 - (p.value / 100) * (H - 16)).toFixed(1)}`)
    .join(" ");

  return (
    <svg className="ssr-trend" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label="Engagement during the session">
      <polyline points={points} fill="none" stroke="var(--accent-color)" strokeWidth="3" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function ReportDetail({ report, onClose, onDelete }) {
  useEffect(() => {
    const onKey = (event) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const moods = Object.entries(report.emotion_distribution || {}).sort((a, b) => b[1] - a[1]);

  return (
    <div className="ssr-overlay" onClick={onClose}>
      <div className="ssr-modal" role="dialog" aria-modal="true" aria-label={report.title} onClick={(e) => e.stopPropagation()}>
        <header className="ssr-modal-head">
          <div>
            <h2>{report.title}</h2>
            <p>
              {formatDate(report.started_at)} to {formatDate(report.ended_at)}, lasted{" "}
              {formatDuration(report.duration_seconds)}
            </p>
          </div>
          <div className="ssr-modal-actions">
            <button className="ssr-btn ssr-btn--danger" onClick={() => onDelete(report)}>Delete report</button>
            <button className="ssr-btn" onClick={onClose} aria-label="Close report">Close</button>
          </div>
        </header>

        <div className="ssr-stats">
          <div><small>Students</small><strong>{report.students_total}</strong></div>
          <div><small>Class engagement</small><strong>{report.class_average_engagement}%</strong></div>
          <div><small>Attention</small><strong>{report.attention}%</strong></div>
          <div><small>Most at once</small><strong>{report.peak_students}</strong></div>
        </div>

        <div className="ssr-levels">
          {LEVELS.map((level) => (
            <span key={level} className={`ssr-level ssr-level--${LEVEL_TONE[level]}`}>
              {level}: {report.engagement_levels?.[level] || 0}
            </span>
          ))}
        </div>

        <div className="ssr-two">
          <section>
            <h3>Engagement during the session</h3>
            <TrendLine trend={report.engagement_trend} />
            {(!report.engagement_trend || report.engagement_trend.length < 2) && (
              <p className="ssr-muted">The session was too short to draw a trend.</p>
            )}
          </section>

          <section>
            <h3>Class mood</h3>
            {moods.map(([name, percent]) => (
              <div className="ssr-mood" key={name}>
                <span>{name}</span>
                <div className="ssr-track"><div style={{ width: `${percent}%` }} /></div>
                <strong>{percent}%</strong>
              </div>
            ))}
          </section>
        </div>

        {LEVELS.map((level) => {
          const group = report.students.filter((s) => s.engagement.level === level);
          if (group.length === 0) return null;

          return (
            <section key={level} className="ssr-group">
              <h3>{level} students ({group.length})</h3>
              <div className="sr-grid">
                {group.map((student) => (
                  <StudentReportCard key={student.student_id} student={student} />
                ))}
              </div>
            </section>
          );
        })}
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
      setError("Cannot load saved reports. Make sure the backend is running.");
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
      const data = await response.json();
      if (data.success) setOpenReport(data.report);
    } catch {
      setError("Could not open this report.");
    } finally {
      setBusyId("");
    }
  };

  const remove = async (report) => {
    if (!window.confirm(`Delete "${report.title}"? This cannot be undone.`)) return;

    try {
      const response = await fetch(`${backendUrl}/reports/${report.id}`, { method: "DELETE" });
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
          <h2>Saved session reports</h2>
          <p>A report is saved each time you stop the classroom camera.</p>
        </div>
        <button className="ssr-btn" onClick={load}>Refresh list</button>
      </div>

      {error && <div className="ssr-empty">{error}</div>}

      {!error && reports === null && <div className="ssr-empty">Loading reports…</div>}

      {reports && reports.length === 0 && !error && (
        <div className="ssr-empty">
          No saved reports yet. Start a live classroom, then stop the camera to
          save the first one.
        </div>
      )}

      {reports && reports.length > 0 && (
        <div className="ssr-list">
          {reports.map((report) => (
            <article className="ssr-row" key={report.id}>
              <div className="ssr-row-main">
                <strong>{report.title}</strong>
                <span>
                  {report.students_total} students, {formatDuration(report.duration_seconds)} long, saved {formatDate(report.ended_at)}
                </span>
              </div>

              <div className="ssr-row-score">
                <span className={`ssr-score ssr-score--${tone(report.class_average_engagement)}`}>
                  {report.class_average_engagement}%
                </span>
                <small>class engagement</small>
              </div>

              <div className="ssr-row-actions">
                <button className="ssr-btn ssr-btn--primary" onClick={() => open(report.id)} disabled={busyId === report.id}>
                  {busyId === report.id ? "Opening…" : "View report"}
                </button>
                <button className="ssr-btn ssr-btn--danger" onClick={() => remove(report)}>Delete</button>
              </div>
            </article>
          ))}
        </div>
      )}

      {openReport && (
        <ReportDetail report={openReport} onClose={() => setOpenReport(null)} onDelete={remove} />
      )}
    </section>
  );
}

export default SessionReports;