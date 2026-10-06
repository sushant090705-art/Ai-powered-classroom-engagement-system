import { useState } from "react";
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

function emojiFor(emotion) {
  return EMOTION_EMOJI[String(emotion || "").toLowerCase()] || "🤖";
}

function levelTone(level) {
  switch (level) {
    case "Engaged":
    case "High":
    case "Alert":
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

function dominantKey(counts) {
  const entries = Object.entries(counts || {});
  if (entries.length === 0) return "Unknown";
  return entries.sort((a, b) => b[1] - a[1])[0][0];
}

/**
 * One student's report.
 *
 * Live classroom: student.in_view is true / false, so the card also shows
 * "right now" values. Recorded video: in_view is null, so the card shows
 * the summary of the whole video only.
 *
 * onRename(newName) is optional; without it the pencil icon is hidden.
 */
function StudentReportCard({ student, onRename }) {
  const [editing, setEditing] = useState(false);
  const [draftName, setDraftName] = useState("");

  const { emotion, attention, eyes, engagement } = student;

  const liveNow = student.in_view === true;
  const outOfView = student.in_view === false;

  const startEditing = () => {
    setDraftName(student.name);
    setEditing(true);
  };

  const saveName = () => {
    const name = draftName.trim();
    setEditing(false);

    if (name && name !== student.name && onRename) {
      onRename(name);
    }
  };

  const topEmotions = emotion.distribution.slice(0, 3);

  // Eyes: live shows the current state; a video shows the overall picture.
  const eyeHeadline = liveNow
    ? eyes.current
    : outOfView
    ? "Unknown"
    : `Mostly ${dominantKey(eyes.counts)}`;

  const eyeStatus = liveNow || outOfView
    ? eyes.status
    : eyes.sleeping_events > 0
    ? "Sleeping"
    : eyes.drowsy_events > 0
    ? "Drowsy"
    : "Alert";

  return (
    <article className={`sr-card ${outOfView ? "sr-card--away" : ""}`}>
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
              {onRename && (
                <button
                  type="button"
                  className="sr-edit-btn"
                  onClick={startEditing}
                  title="Rename student"
                  aria-label={`Rename ${student.name}`}
                >
                  ✎
                </button>
              )}
            </strong>
          )}
          <small>ID #{student.student_id}</small>
        </div>

        {outOfView && <Pill tone="muted">Not in view</Pill>}
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
        {liveNow && (
          <small className="sr-sub">
            Right now: {engagement.current}%
          </small>
        )}
      </section>

      {/* DETAILS */}
      <dl className="sr-details">
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
            {liveNow && emotion.current !== "Unknown" && (
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
            <small>Based on eye state</small>
          </dd>
        </div>

        <div className="sr-row">
          <dt>Eyes</dt>
          <dd>
            <strong>{eyeHeadline}</strong>{" "}
            {eyeStatus !== eyeHeadline && (
              <Pill tone={levelTone(eyeStatus)}>{eyeStatus}</Pill>
            )}
            <small>
              Drowsy {eyes.drowsy_events}× ({Math.round(eyes.drowsy_percent)}%)
              {" · "}
              Sleeping {eyes.sleeping_events}× (
              {Math.round(eyes.sleeping_percent)}%)
            </small>
          </dd>
        </div>
      </dl>

      <footer className="sr-foot">
        {student.in_view === null || student.in_view === undefined
          ? `Detected in ${student.face_samples} analysed frames`
          : `Face visible ${student.face_visibility_percent}% of the time · ${student.samples} samples`}
      </footer>
    </article>
  );
}

export default StudentReportCard;
