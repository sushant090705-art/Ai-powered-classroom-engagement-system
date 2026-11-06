
import { useState } from "react";
import "./StudentReports.css";

const BACKEND_URL = "http://127.0.0.1:5000";

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
  if (!entries.length) return "Unknown";
  return entries.sort((a, b) => b[1] - a[1])[0][0];
}

function StudentReportCard({ student, backendUrl = BACKEND_URL }) {
  const [photoFailed, setPhotoFailed] = useState(false);

  const { emotion, attention, eyes, engagement } = student;

  const liveNow = student.in_view === true;
  const outOfView = student.in_view === false;

  const topEmotions = emotion.distribution.slice(0, 3);

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

  const photoUrl = student.photo_url
    ? `${backendUrl.replace(/\/$/, "")}/${student.photo_url.replace(/^\//, "")}`
    : "";

  return (
    <article className={`sr-card ${outOfView ? "sr-card--away" : ""}`}>
      <header className="sr-card-head">
        <div className="sr-avatar">
          {photoUrl && !photoFailed ? (
            <img
              src={photoUrl}
              alt={`Student ${student.student_id}`}
              onError={() => {
                console.error("Student photo failed to load:", photoUrl);
                setPhotoFailed(true);
              }}
            />
          ) : (
            <span>{student.student_id}</span>
          )}
        </div>

        <div className="sr-identity">
          <strong className="sr-name">
            {student.name || `Student ${student.student_id}`}
          </strong>
          <small>Student ID: {student.student_id}</small>
        </div>
      </header>

      <section className="sr-engagement">
        <div className="sr-engagement-top">
          <span className="sr-label">Overall Engagement</span>
          <Pill tone={levelTone(engagement.level)}>
            {engagement.level}
          </Pill>
        </div>

        <div className="sr-engagement-value">
          {engagement.overall_percent}<span>%</span>
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

      <dl className="sr-details">
        <div className="sr-row">
          <dt>Emotion</dt>
          <dd>
            <strong>
              {emojiFor(emotion.dominant)} {emotion.dominant}
            </strong>
            <small className="sr-inline">Overall</small>

            {topEmotions.length > 0 && (
              <small>
                {topEmotions
                  .map(e => `${e.emotion} ${Math.round(e.percent)}%`)
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
            <Pill tone={levelTone(attention.level)}>
              {attention.level}
            </Pill>
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
              Drowsy {eyes.drowsy_events}× (
              {Math.round(eyes.drowsy_percent)}%)
              {" · "}
              Sleeping {eyes.sleeping_events}× (
              {Math.round(eyes.sleeping_percent)}%)
            </small>
          </dd>
        </div>
      </dl>

      <footer className="sr-foot">
        {student.in_view == null
          ? `Detected in ${student.face_samples} analysed frames`
          : `Face visible ${student.face_visibility_percent}% of the time · ${student.samples} samples`}
      </footer>
    </article>
  );
}

export default StudentReportCard;
