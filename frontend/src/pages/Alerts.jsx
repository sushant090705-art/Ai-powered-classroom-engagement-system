
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import ThemeToggle from "../components/ThemeToggle";
import { formatDuration } from "../utils/formatDuration";
import "./Alerts.css";

const BACKEND_URL = "http://127.0.0.1:5000";
const POLL_MS = 3000;

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const ZONE_PRESETS = [
  { label: "Left side", zone: { x1: 0, y1: 0, x2: 0.35, y2: 1 } },
  { label: "Centre", zone: { x1: 0.325, y1: 0, x2: 0.675, y2: 1 } },
  { label: "Right side", zone: { x1: 0.65, y1: 0, x2: 1, y2: 1 } },
  { label: "Top of view", zone: { x1: 0, y1: 0, x2: 1, y2: 0.4 } },
];

const NUMBER_KEYS = [
  "teacher_absent_seconds",
  "disengagement_threshold",
  "disengagement_seconds",
  "drowsy_share_threshold",
  "drowsy_seconds",
  "min_students",
  "smoothing_seconds",
];

const REASON_LABELS = {
  recovered: "Recovered on its own",
  session_ended: "Camera session ended",
  server_restart: "Server restarted",
  alerts_disabled: "Alerts turned off",
  outside_schedule: "Lecture hours ended",
  acknowledged: "Acknowledged",
  replaced: "Replaced by a newer one",
};

const PRIORITY_LABELS = {
  high: "Act now",
  medium: "Consider",
  low: "FYI",
};

function formatClock(seconds) {
  return new Date(seconds * 1000).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatDay(seconds) {
  return new Date(seconds * 1000).toLocaleDateString([], {
    day: "numeric",
    month: "short",
  });
}

function ZonePreview({ zone }) {
  return (
    <div className="al-zone-preview" aria-hidden="true">
      {zone && (
        <div
          className="al-zone-rect"
          style={{
            left: `${zone.x1 * 100}%`,
            top: `${zone.y1 * 100}%`,
            width: `${(zone.x2 - zone.x1) * 100}%`,
            height: `${(zone.y2 - zone.y1) * 100}%`,
          }}
        />
      )}
      <span>{zone ? "Teacher zone" : "No zone chosen"}</span>
    </div>
  );
}

function NumberField({ label, unit, value, min, max, onChange }) {
  return (
    <label className="al-field">
      <span>{label}</span>
      <span className="al-field-input">
        <input
          type="number"
          min={min}
          max={max}
          value={value}
          onChange={(e) =>
            onChange(e.target.value === "" ? "" : Number(e.target.value))
          }
        />
        <em>{unit}</em>
      </span>
    </label>
  );
}

function Recommendation({ rec }) {
  return (
    <li className={`al-rec al-rec--${rec.priority}`}>
      <div className="al-rec-head">
        <strong>{rec.title}</strong>
        <span className="al-tag">{PRIORITY_LABELS[rec.priority]}</span>
      </div>
      <p>{rec.detail}</p>
      <small>{rec.reason}</small>
    </li>
  );
}

function Alerts() {
  const navigate = useNavigate();

  const [status, setStatus] = useState(null);
  const [alerts, setAlerts] = useState({ active: [], history: [] });
  const [offline, setOffline] = useState(false);
  const [tick, setTick] = useState(() => Date.now());

  const [settings, setSettings] = useState(null);
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);
  const [formMessage, setFormMessage] = useState(null);
  const [actionError, setActionError] = useState("");

  const load = useCallback(async () => {
    try {
      const [statusResponse, alertsResponse] = await Promise.all([
        fetch(`${BACKEND_URL}/alerts/status`),
        fetch(`${BACKEND_URL}/alerts`),
      ]);

      if (!statusResponse.ok || !alertsResponse.ok) {
        throw new Error("Bad response");
      }

      setStatus(await statusResponse.json());
      setAlerts(await alertsResponse.json());
      setOffline(false);
      setTick(Date.now());
    } catch {
      setOffline(true);
    }
  }, []);

  const loadSettings = useCallback(async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/alerts/settings`);
      const data = await response.json();

      if (data.success) {
        setSettings(data.settings);
        setDraft(data.settings);
      }
    } catch {
      // Backend offline: the page already shows that state.
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, POLL_MS);
    return () => clearInterval(interval);
  }, [load]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const call = async (path, options) => {
    setActionError("");

    try {
      const response = await fetch(`${BACKEND_URL}${path}`, options);
      const data = await response.json().catch(() => ({}));

      if (!response.ok || data.success === false) {
        throw new Error(data.message || "That did not work.");
      }
    } catch (err) {
      setActionError(err.message || "Cannot reach the backend.");
    }

    load();
  };

  const acknowledge = (id) =>
    call(`/alerts/${id}/acknowledge`, { method: "POST" });

  const remove = (id) => call(`/alerts/${id}`, { method: "DELETE" });

  const sendTest = () => call("/alerts/test", { method: "POST" });

  const clearHistory = () => {
    if (!window.confirm("Remove all resolved alerts from the history?")) return;
    call("/alerts/clear-history", { method: "POST" });
  };

  const setField = (key, value) => {
    setFormMessage(null);
    setDraft((previous) => ({ ...previous, [key]: value }));
  };

  const setZone = (zone) => {
    setFormMessage(null);
    setDraft((previous) => ({
      ...previous,
      teacher_zone: zone,
      teacher_check_enabled: zone ? previous.teacher_check_enabled : false,
    }));
  };

  const setZoneEdge = (edge, percent) => {
    if (percent === "") return;
    const value = Math.min(100, Math.max(0, percent)) / 100;
    setZone({ ...draft.teacher_zone, [edge]: value });
  };

  const toggleDay = (day) => {
    const days = draft.schedule.days.includes(day)
      ? draft.schedule.days.filter((d) => d !== day)
      : [...draft.schedule.days, day];

    setField("schedule", { ...draft.schedule, days });
  };

  const saveSettings = async () => {
    if (NUMBER_KEYS.some((key) => draft[key] === "")) {
      setFormMessage({ type: "error", text: "Fill in every number first." });
      return;
    }

    setSaving(true);
    setFormMessage(null);

    try {
      const response = await fetch(`${BACKEND_URL}/alerts/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draft),
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.message || "Could not save the settings.");
      }

      setSettings(data.settings);
      setDraft(data.settings);
      setFormMessage({ type: "ok", text: "Settings saved." });
    } catch (err) {
      setFormMessage({
        type: "error",
        text: err.message || "Cannot reach the backend.",
      });
    } finally {
      setSaving(false);
    }
  };

  const dirty =
    settings && draft && JSON.stringify(settings) !== JSON.stringify(draft);

  const monitoringState = offline
    ? { tone: "off", text: "Backend offline" }
    : !status?.session_active
    ? { tone: "idle", text: "No camera session running" }
    : status.monitoring
    ? { tone: "live", text: "Monitoring the live class" }
    : { tone: "idle", text: "Alerts paused (off or outside lecture hours)" };

  const running = Boolean(status?.session_active) && !offline;

  const teacher = status
    ? !running
      ? { value: "—", hint: "Starts with a camera session", tone: "" }
      : !status.teacher_monitored
      ? {
          value: "Not monitored",
          hint: "Choose a teacher zone in the settings below",
          tone: "",
        }
      : status.teacher_present
      ? { value: "In the teacher area", hint: "Seen right now", tone: "good" }
      : {
          value: "Not seen",
          hint: `For ${formatDuration(status.teacher_absent_for)}`,
          tone: "bad",
        }
    : { value: "—", hint: "", tone: "" };

  const engagement = status?.engagement;
  const engagementTone =
    engagement == null
      ? ""
      : engagement >= 75
      ? "good"
      : engagement >= 50
      ? "mid"
      : "bad";

  const activeAlerts = alerts.active || [];
  const history = alerts.history || [];
  const recommendations = status?.recommendations || [];

  return (
    <div className="al-page">
      <header className="al-nav">
        <button
          className="al-logo"
          onClick={() => navigate("/dashboard")}
          aria-label="Go to dashboard"
        >
          <span>◉</span>
          <b>ClassroomAI</b>
        </button>

        <div className="al-nav-right">
          <ThemeToggle />
          <button className="al-btn" onClick={() => navigate("/dashboard")}>
            Dashboard <span>↗</span>
          </button>
        </div>
      </header>

      <main className="al-content">
        <section className="al-hero">
          <div>
            <div className="al-eyebrow">
              <span></span> CLASSROOM MONITORING
            </div>

            <h1>Alerts <span>&</span> Recommendations.</h1>

            <p>
              Stay informed when a class needs attention. Review live warnings
              and suggested next steps for the teacher.
            </p>

            <div className={`al-state al-state--${monitoringState.tone}`}>
              <i /> {monitoringState.text}
            </div>
          </div>

          <button className="al-live-btn" onClick={() => navigate("/classroom")}>
            <span>←</span> Live classroom
          </button>
        </section>

        {actionError && (
          <div className="al-banner al-banner--error" role="alert">
            <span>!</span>
            {actionError}
          </div>
        )}

        <section className="al-overview">
          <div className="al-section-kicker">
            <span>01</span> LIVE CLASSROOM STATUS
          </div>

          <div className="al-status">
            <article className={`al-stat ${teacher.tone}`}>
              <small>TEACHER PRESENCE</small>
              <strong>{teacher.value}</strong>
              <em>{teacher.hint}</em>
            </article>

            <article className={`al-stat ${engagementTone}`}>
              <small>CLASS ENGAGEMENT</small>
              <strong>
                {running && engagement != null
                  ? `${Math.round(engagement)}%`
                  : "—"}
              </strong>
              <em>
                {running && engagement != null
                  ? "Average over the last few seconds"
                  : "Needs enough faces in view"}
              </em>
            </article>

            <article
              className={`al-stat ${
                running && status.drowsy_percent >= 20 ? "bad" : ""
              }`}
            >
              <small>DROWSY OR CLOSED EYES</small>
              <strong>
                {running && status.drowsy_percent != null
                  ? `${Math.round(status.drowsy_percent)}%`
                  : "—"}
              </strong>
              <em>Share of visible students</em>
            </article>

            <article className="al-stat">
              <small>FACES IN VIEW</small>
              <strong>{running ? status.students_in_view : "—"}</strong>
              <em>
                {running
                  ? `${status.persons_in_view} ${
                      status.persons_in_view === 1 ? "person" : "people"
                    } detected`
                  : ""}
              </em>
            </article>
          </div>
        </section>

        <section className="al-section" aria-live="polite">
          <div className="al-section-head">
            <div>
              <div className="al-section-kicker">
                <span>02</span> NEEDS ATTENTION
              </div>
              <h2>Active alerts</h2>
            </div>

            {activeAlerts.length > 0 && (
              <span className="al-count">{activeAlerts.length} active</span>
            )}
          </div>

          {activeAlerts.length === 0 ? (
            <div className="al-empty">
              <span className="al-empty-mark">✓</span>
              <strong>Nothing needs attention.</strong>
              <p>
                {running
                  ? "All checks are passing for this session."
                  : "Start a camera session and the checks will run automatically."}
              </p>
            </div>
          ) : (
            <div className="al-alert-list">
              {activeAlerts.map((alert) => (
                <article
                  key={alert.id}
                  className={`al-alert al-alert--${alert.severity}`}
                >
                  <div className="al-alert-main">
                    <div className="al-alert-top">
                      <span className="al-sev">{alert.severity}</span>
                      <h3>{alert.title}</h3>
                    </div>

                    <p>{alert.message}</p>

                    <small>
                      Started {formatClock(alert.started_at)} · open for{" "}
                      {formatDuration(tick / 1000 - alert.started_at)}
                    </small>

                    {alert.recommendations.length > 0 && (
                      <div className="al-alert-recs">
                        <h4>Suggested actions</h4>
                        <ul>
                          {alert.recommendations.map((rec) => (
                            <Recommendation key={rec.id} rec={rec} />
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>

                  <button
                    className="al-btn al-btn--primary"
                    onClick={() => acknowledge(alert.id)}
                    disabled={alert.acknowledged}
                  >
                    {alert.acknowledged ? "Acknowledged" : "Acknowledge"}
                  </button>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="al-section">
          <div className="al-section-head">
            <div>
              <div className="al-section-kicker">
                <span>03</span> TEACHER GUIDANCE
              </div>
              <h2>Suggested actions right now</h2>
              <p>
                Based on recent engagement, eye state and expressions. These
                are prompts for the teacher, not verdicts.
              </p>
            </div>
          </div>

          {recommendations.length === 0 ? (
            <div className="al-empty al-empty--simple">
              <p>
                {running
                  ? "Not enough data yet to suggest anything."
                  : "Suggestions appear while a camera session is running."}
              </p>
            </div>
          ) : (
            <ul className="al-rec-list">
              {recommendations.map((rec) => (
                <Recommendation key={rec.id} rec={rec} />
              ))}
            </ul>
          )}
        </section>

        <section className="al-section">
          <div className="al-section-head al-section-head--row">
            <div>
              <div className="al-section-kicker">
                <span>04</span> PAST ACTIVITY
              </div>
              <h2>Alert history</h2>
              <p>Resolved alerts, newest first.</p>
            </div>

            {history.length > 0 && (
              <button className="al-btn al-btn--danger" onClick={clearHistory}>
                Clear history
              </button>
            )}
          </div>

          {history.length === 0 ? (
            <div className="al-empty al-empty--simple">
              <p>No resolved alerts yet.</p>
            </div>
          ) : (
            <div className="al-history">
              {history.map((alert) => (
                <article className="al-row" key={alert.id}>
                  <span
                    className={`al-dot al-dot--${alert.severity}`}
                    aria-hidden="true"
                  />

                  <div className="al-row-main">
                    <strong>{alert.title}</strong>
                    <span>
                      {formatDay(alert.started_at)}, {formatClock(alert.started_at)}
                      {alert.resolved_at
                        ? ` to ${formatClock(alert.resolved_at)}, lasted ${formatDuration(
                            alert.resolved_at - alert.started_at
                          )}`
                        : ""}
                    </span>
                    <small>
                      {REASON_LABELS[alert.resolved_reason] || "Resolved"}
                      {alert.acknowledged
                        ? " · acknowledged"
                        : " · not acknowledged"}
                    </small>
                  </div>

                  <button
                    className="al-btn al-btn--danger"
                    onClick={() => remove(alert.id)}
                    aria-label={`Delete alert: ${alert.title}`}
                  >
                    Delete
                  </button>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="al-section al-settings-section">
          <div className="al-section-head">
            <div>
              <div className="al-section-kicker">
                <span>05</span> CONFIGURATION
              </div>
              <h2>Alert settings</h2>
              <p>
                Configure when the system should raise alerts. A problem must
                last for the selected duration; a single bad frame will not
                trigger an alert.
              </p>
            </div>
          </div>

          {!draft ? (
            <div className="al-empty al-empty--simple">
              <p>
                {offline
                  ? "Start the backend to edit settings."
                  : "Loading settings…"}
              </p>
            </div>
          ) : (
            <div className="al-form">
              <div className="al-settings-intro">
                <label className="al-switch">
                  <input
                    type="checkbox"
                    checked={draft.enabled}
                    onChange={(e) => setField("enabled", e.target.checked)}
                  />
                  <span>Raise alerts during camera sessions</span>
                </label>
                <span className={draft.enabled ? "al-enabled" : "al-disabled"}>
                  {draft.enabled ? "ENABLED" : "DISABLED"}
                </span>
              </div>

              <fieldset>
                <legend><span>01</span> Teacher presence</legend>

                <p className="al-hint">
                  The system detects people, not roles, so the teacher is the
                  person standing in the zone you mark. Choose the area where
                  the teacher normally teaches. It will be outlined on the live
                  video.
                </p>

                <div className="al-zone-row">
                  <ZonePreview zone={draft.teacher_zone} />

                  <div className="al-zone-controls">
                    <div className="al-presets">
                      {ZONE_PRESETS.map((preset) => (
                        <button
                          key={preset.label}
                          type="button"
                          className="al-btn"
                          onClick={() => setZone(preset.zone)}
                        >
                          {preset.label}
                        </button>
                      ))}
                    </div>

                    {draft.teacher_zone && (
                      <div className="al-edges">
                        {[
                          ["x1", "Left"],
                          ["x2", "Right"],
                          ["y1", "Top"],
                          ["y2", "Bottom"],
                        ].map(([edge, label]) => (
                          <NumberField
                            key={edge}
                            label={label}
                            unit="%"
                            min={0}
                            max={100}
                            value={Math.round(draft.teacher_zone[edge] * 100)}
                            onChange={(value) => setZoneEdge(edge, value)}
                          />
                        ))}
                      </div>
                    )}

                    {draft.teacher_zone && (
                      <button
                        type="button"
                        className="al-link"
                        onClick={() => setZone(null)}
                      >
                        Remove zone
                      </button>
                    )}
                  </div>
                </div>

                <label className="al-switch">
                  <input
                    type="checkbox"
                    checked={draft.teacher_check_enabled}
                    disabled={!draft.teacher_zone}
                    onChange={(e) =>
                      setField("teacher_check_enabled", e.target.checked)
                    }
                  />
                  <span>
                    Alert when nobody is in the zone
                    {!draft.teacher_zone && " (choose a zone first)"}
                  </span>
                </label>

                <NumberField
                  label="Alert after the teacher is missing for"
                  unit="seconds"
                  min={10}
                  max={3600}
                  value={draft.teacher_absent_seconds}
                  onChange={(v) => setField("teacher_absent_seconds", v)}
                />
              </fieldset>

              <fieldset>
                <legend><span>02</span> Class engagement</legend>

                <div className="al-grid">
                  <NumberField
                    label="Low engagement is below"
                    unit="%"
                    min={10}
                    max={90}
                    value={draft.disengagement_threshold}
                    onChange={(v) => setField("disengagement_threshold", v)}
                  />
                  <NumberField
                    label="…and lasts at least"
                    unit="seconds"
                    min={10}
                    max={3600}
                    value={draft.disengagement_seconds}
                    onChange={(v) => setField("disengagement_seconds", v)}
                  />
                  <NumberField
                    label="Drowsy students at or above"
                    unit="% of class"
                    min={5}
                    max={100}
                    value={draft.drowsy_share_threshold}
                    onChange={(v) => setField("drowsy_share_threshold", v)}
                  />
                  <NumberField
                    label="…and lasts at least"
                    unit="seconds"
                    min={10}
                    max={3600}
                    value={draft.drowsy_seconds}
                    onChange={(v) => setField("drowsy_seconds", v)}
                  />
                  <NumberField
                    label="Faces needed to judge the class"
                    unit="students"
                    min={1}
                    max={200}
                    value={draft.min_students}
                    onChange={(v) => setField("min_students", v)}
                  />
                  <NumberField
                    label="Averaging window"
                    unit="seconds"
                    min={5}
                    max={120}
                    value={draft.smoothing_seconds}
                    onChange={(v) => setField("smoothing_seconds", v)}
                  />
                </div>
              </fieldset>

              <fieldset>
                <legend><span>03</span> Lecture hours</legend>

                <label className="al-switch">
                  <input
                    type="checkbox"
                    checked={draft.schedule_enforced}
                    onChange={(e) =>
                      setField("schedule_enforced", e.target.checked)
                    }
                  />
                  <span>Only raise alerts during these hours</span>
                </label>

                <div
                  className={`al-schedule ${
                    draft.schedule_enforced ? "" : "is-off"
                  }`}
                >
                  <div className="al-days" role="group" aria-label="Days">
                    {DAY_LABELS.map((label, day) => (
                      <label key={label} className="al-day">
                        <input
                          type="checkbox"
                          checked={draft.schedule.days.includes(day)}
                          onChange={() => toggleDay(day)}
                          disabled={!draft.schedule_enforced}
                        />
                        <span>{label}</span>
                      </label>
                    ))}
                  </div>

                  <div className="al-time-fields">
                    <label className="al-field">
                      <span>From</span>
                      <input
                        type="time"
                        value={draft.schedule.start}
                        disabled={!draft.schedule_enforced}
                        onChange={(e) =>
                          setField("schedule", {
                            ...draft.schedule,
                            start: e.target.value,
                          })
                        }
                      />
                    </label>

                    <label className="al-field">
                      <span>Until</span>
                      <input
                        type="time"
                        value={draft.schedule.end}
                        disabled={!draft.schedule_enforced}
                        onChange={(e) =>
                          setField("schedule", {
                            ...draft.schedule,
                            end: e.target.value,
                          })
                        }
                      />
                    </label>
                  </div>
                </div>
              </fieldset>

              <fieldset>
                <legend><span>04</span> E-mail notifications</legend>

                <label className="al-field al-email-field">
                  <span>Send each new alert to</span>
                  <input
                    type="email"
                    placeholder="dean@college.edu (optional)"
                    value={draft.notify_email}
                    onChange={(e) => setField("notify_email", e.target.value)}
                  />
                </label>

                <p className="al-hint">
                  E-mail only works once the server has SMTP details (see the
                  Module 5 notes). Alerts always appear on this page.
                </p>
              </fieldset>

              <div className="al-form-actions">
                <button
                  className="al-btn al-btn--primary"
                  onClick={saveSettings}
                  disabled={saving || !dirty}
                >
                  {saving ? "Saving…" : "Save settings"}
                </button>

                <button
                  className="al-btn"
                  onClick={() => setDraft(settings)}
                  disabled={saving || !dirty}
                >
                  Discard changes
                </button>

                <button className="al-btn" onClick={sendTest}>
                  Send a test alert
                </button>

                {formMessage && (
                  <span
                    className={`al-form-message al-form-message--${formMessage.type}`}
                    role="status"
                  >
                    {formMessage.text}
                  </span>
                )}
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default Alerts;
