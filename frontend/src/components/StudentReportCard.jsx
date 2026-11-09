
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
  return entries.sort((a, b) => Number(b[1]) - Number(a[1]))[0][0];
}

function getPhotoUrl(photoUrl, backendUrl) {
  if (!photoUrl || typeof photoUrl !== "string") {
    return "";
  }

  const path = photoUrl.trim();

  if (!path) {
    return "";
  }

  // Already a complete URL or browser-supported image URL.
  if (
    path.startsWith("http://") ||
    path.startsWith("https://") ||
    path.startsWith("data:") ||
    path.startsWith("blob:")
  ) {
    return path;
  }

  const baseUrl = backendUrl.replace(/\/+$/, "");
  const cleanPath = path.replace(/^\/+/, "");

  return `${baseUrl}/${cleanPath}`;
}

function StudentReportCard({ student, backendUrl = BACKEND_URL }) {
  const [photoFailed, setPhotoFailed] = useState(false);

  const emotion = student.emotion || {};
  const attention = student.attention || {};
  const eyes = student.eyes || {};
  const engagement = student.engagement || {};

  const liveNow = student.in_view === true;
  const outOfView = student.in_view === false;

  const emotionDistribution = Array.isArray(emotion.distribution)
    ? emotion.distribution
    : [];

  const topEmotions = emotionDistribution.slice(0, 3);

  const eyeCounts = eyes.counts || {};

  const eyeHeadline = liveNow
    ? eyes.current || "Unknown"
    : outOfView
      ? "Unknown"
      : `Mostly ${dominantKey(eyeCounts)}`;

  const eyeStatus = liveNow || outOfView
    ? eyes.status || "Unknown"
    : Number(eyes.sleeping_events || 0) > 0
      ? "Sleeping"
      : Number(eyes.drowsy_events || 0) > 0
        ? "Drowsy"
        : "Alert";

  const photoUrl = getPhotoUrl(student.photo_url, backendUrl);

  const engagementPercent = Number(engagement.overall_percent) || 0;
  const attentionPercent = Number(attention.percent) || 0;

  return (
    <article className={`sr-card ${outOfView ? "sr-card--away" : ""}`}>
      <header className="sr-card-head">
        <div className="sr-avatar">
          {photoUrl && !photoFailed ? (
            <img
              src={photoUrl}
              alt={`Student ${student.student_id}`}
              loading="lazy"
              onError={() => {
                console.error(
                  `Photo failed for Student ${student.student_id}:`,
                  photoUrl
                );
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
            {engagement.level || "Unknown"}
          </Pill>
        </div>

        <div className="sr-engagement-value">
          {engagementPercent}<span>%</span>
        </div>

        <Bar
          percent={engagementPercent}
          tone={levelTone(engagement.level)}
        />

        {liveNow && (
          <small className="sr-sub">
            Right now: {Number(engagement.current) || 0}%
          </small>
        )}
      </section>

      <dl className="sr-details">
        <div className="sr-row">
          <dt>Emotion</dt>
          <dd>
            <strong>
              {emojiFor(emotion.dominant)} {emotion.dominant || "Unknown"}
            </strong>

            <small className="sr-inline">Overall</small>

            {topEmotions.length > 0 && (
              <small>
                {topEmotions
                  .map(
                    (item) =>
                      `${item.emotion || "Unknown"} ${Math.round(
                        Number(item.percent) || 0
                      )}%`
                  )
                  .join(" · ")}
              </small>
            )}

            {liveNow && emotion.current && emotion.current !== "Unknown" && (
              <small>Now: {emotion.current}</small>
            )}
          </dd>
        </div>

        <div className="sr-row">
          <dt>Attention</dt>
          <dd>
            <strong>{attentionPercent}%</strong>{" "}
            <Pill tone={levelTone(attention.level)}>
              {attention.level || "Unknown"}
            </Pill>

            <Bar
              percent={attentionPercent}
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
              Drowsy {Number(eyes.drowsy_events) || 0}× (
              {Math.round(Number(eyes.drowsy_percent) || 0)}%)
              {" · "}
              Sleeping {Number(eyes.sleeping_events) || 0}× (
              {Math.round(Number(eyes.sleeping_percent) || 0)}%)
            </small>
          </dd>
        </div>
      </dl>

      <footer className="sr-foot">
        {student.in_view == null
          ? `Detected in ${student.face_samples || 0} analysed frames`
          : `Face visible ${Number(student.face_visibility_percent) || 0}% of the time · ${student.samples || 0} samples`}
      </footer>
    </article>
  );
}

export default StudentReportCard;
