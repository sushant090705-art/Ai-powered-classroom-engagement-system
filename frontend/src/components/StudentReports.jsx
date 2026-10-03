import { useEffect, useState } from "react";
import "./StudentReports.css";

const EMOTION_EMOJI = {
  happy: "😊",
  sad: "😢",
  angry: "😠",
  fear: "😨",
  disgust: "🤢",
  surprise: "😮",
  neutral: "😐",
};

const POLL_MS = 1000;

function formatDuration(totalSeconds) {
  const seconds = Math.max(0, Math.round(Number(totalSeconds) || 0));
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function emojiFor(emotion) {
  return EMOTION_EMOJI[String(emotion || "").toLowerCase()] || "🤖";
}

function levelTone(level) {
  switch (level) {
    case "Engaged":
    case "High":
    case "Alert":
    case "Present":
      return "good";
    case "Moderate":
    case "Medium":
    case "Drowsy":
      return "warn";
    case "Low":
    case "Sleeping":
      return "bad";
    default:
      return "muted";
  }
}

function Pill({ tone, children }) {
  return <span className={`sr-pill sr-pill--${tone}`}>{children}</span>;
}

function Bar({ percent, tone }) {
  const width = Math.max(0, Math.min(100, Number(percent) || 0));
  return (
    <div className="sr-bar">
      <div
        className={`sr-bar-fill sr-bar-fill--${tone}`}
        style={{ width: `${width}%` }}
      />
    </div>
  );
}

function StudentCard({ student, backendUrl, onRenamed }) {
  const [editing, setEditing] = useState(false);
  const [draftName, setDraftName] = useState("");

  const { attendance, emotion, attention, eyes, engagement } = student;
  const present = attendance.status === "Present";

  const startEditing = () => {
    setDraftName(student.name);
    setEditing(true);
  };

  const saveName = async () => {
    const name = draftName.trim();
    setEditing(false);

    if (!name || name === student.name) return;

    try {
      const response = await fetch(
        `${backendUrl}/students/${student.student_id}/rename`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name }),
        }
      );
      if (response.ok) onRenamed();
    } catch (error) {
      console.error("Rename error:", error);
    }
  };

  const topEmotions = emotion.distribution.slice(0, 3);

  return (
    <article className={`sr-card ${present ? "" : "sr-card--away"}`}>
      {/* HEADER */}
      <header className="sr-card-head">
        <div className="sr-avatar">{student.student_id}</div>

        <div className="sr-identity">
          {editing ? (
            <input
              className="sr-name-input"
              value={draftName}
              maxLength={40}
              autoFocus
              onChange={(e) => setDraftName(e.target.value)}
              onBlur={saveName}
              onKeyDown={(e) => {
                if (e.key === "Enter") saveName();
                if (e.key === "Escape") setEditing(false);
              }}
            />
          ) : (
            <strong className="sr-name">
              {student.name}
              <button
                type="button"
                className="sr-edit-btn"
                onClick={startEditing}
                title="Rename student"
                aria-label={`Rename ${student.name}`}
              >
                ✎
              </button>
            </strong>
          )}
          <small>ID #{student.student_id}</small>
        </div>

        <Pill tone={present ? "good" : "muted"}>
          {present ? "● Present" : "Left"}
        </Pill>
      </header>

      {/* OVERALL ENGAGEMENT */}
      <section className="sr-engagement">
        <div className="sr-engagement-top">
          <span className="sr-label">Overall engagement</span>
          <Pill tone={levelTone(engagement.level)}>{engagement.level}</Pill>
        </div>
        <div className="sr-engagement-value">
          {engagement.overall_percent}
          <span>%</span>
        </div>
        <Bar
          percent={engagement.overall_percent}
          tone={levelTone(engagement.level)}
        />
        <small className="sr-sub">
          Right now: {present ? `${engagement.current}%` : "—"}
        </small>
      </section>

      {/* DETAILS */}
      <dl className="sr-details">
        <div className="sr-row">
          <dt>Attendance</dt>
          <dd>
            <strong>{attendance.attendance_percent}%</strong> of session
            <small>
              {formatDuration(attendance.present_seconds)} present
              {!present &&
                ` · last seen ${formatDuration(
                  attendance.last_seen_seconds_ago
                )} ago`}
            </small>
          </dd>
        </div>

        <div className="sr-row">
          <dt>Emotion</dt>
          <dd>
            <strong>
              {emojiFor(emotion.dominant)} {emotion.dominant}
            </strong>{" "}
            <small className="sr-inline">overall</small>
            {topEmotions.length > 0 && (
              <small>
                {topEmotions
                  .map((e) => `${e.emotion} ${Math.round(e.percent)}%`)
                  .join(" · ")}
              </small>
            )}
            {present && emotion.current !== "Unknown" && (
              <small>Now: {emotion.current}</small>
            )}
          </dd>
        </div>

        <div className="sr-row">
          <dt>Attention</dt>
          <dd>
            <strong>{attention.percent}%</strong>{" "}
            <Pill tone={levelTone(attention.level)}>{attention.level}</Pill>
            <Bar
              percent={attention.percent}
              tone={levelTone(attention.level)}
            />
            <small>Time with eyes open</small>
          </dd>
        </div>

        <div className="sr-row">
          <dt>Eyes</dt>
          <dd>
            <strong>
              {present ? eyes.current : "Unknown"}
            </strong>{" "}
            <Pill tone={levelTone(eyes.status)}>{eyes.status}</Pill>
            <small>
              Drowsy {eyes.drowsy_events}× · Sleeping {eyes.sleeping_events}×
            </small>
          </dd>
        </div>
      </dl>

      <footer className="sr-foot">
        Face visible {student.face_visibility_percent}% of the time ·{" "}
        {student.samples} samples
      </footer>
    </article>
  );
}

function LiveReports({ backendUrl }) {
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [refreshTick, setRefreshTick] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const response = await fetch(`${backendUrl}/students/report`);

        if (!response.ok) {
          throw new Error(`Server error: ${response.status}`);
        }

        const data = await response.json();

        if (!cancelled && data.success) {
          setReport(data);
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          console.error("Student report error:", err);
          setError("Cannot load student reports from the backend.");
        }
      }
    };

    load();
    const interval = setInterval(load, POLL_MS);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [backendUrl, refreshTick]);

  if (error && !report) {
    return <div className="sr-empty">⚠️ {error}</div>;
  }

  if (!report) {
    return <div className="sr-empty">Loading student reports…</div>;
  }

  return (
    <>
      <div className="sr-summary">
        <div>
          <small>Students seen</small>
          <strong>{report.students_total}</strong>
        </div>
        <div>
          <small>Present now</small>
          <strong>{report.students_present}</strong>
        </div>
        <div>
          <small>Class engagement</small>
          <strong>{report.class_average_engagement}%</strong>
        </div>
        <div>
          <small>Session time</small>
          <strong>{formatDuration(report.session_seconds)}</strong>
        </div>
      </div>

      {error && <div className="sr-empty">⚠️ {error}</div>}

      {report.students.length === 0 ? (
        <div className="sr-empty">
          No students detected yet. Reports appear as soon as someone is in
          view of the camera.
        </div>
      ) : (
        <div className="sr-grid">
          {report.students.map((student) => (
            <StudentCard
              key={student.student_id}
              student={student}
              backendUrl={backendUrl}
              onRenamed={() => setRefreshTick((n) => n + 1)}
            />
          ))}
        </div>
      )}
    </>
  );
}

function StudentReports({ backendUrl, active }) {
  return (
    <section className="emotion-card student-reports">
      <div>
        <small>STUDENT REPORTS</small>
        <h2>Individual Student Reports</h2>
        <p>
          Attendance, emotions, attention and eye status for every student
          detected in this session.
        </p>
      </div>

      {active ? (
        <LiveReports backendUrl={backendUrl} />
      ) : (
        <div className="sr-empty">
          Start the classroom camera to see individual student reports.
        </div>
      )}
    </section>
  );
}

export default StudentReports;
