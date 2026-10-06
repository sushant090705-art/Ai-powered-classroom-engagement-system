import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import ThemeToggle from "../components/ThemeToggle";
import "./Dashboard.css";

const BACKEND_URL = "http://127.0.0.1:5000";
const POLL_MS = 4000;

// Ring geometry
const RADIUS = 84;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

// Trend chart geometry
const CHART_W = 640;
const CHART_H = 170;
const CHART_PAD = 14;

function prefersReducedMotion() {
  return (
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  );
}

// Smoothly animates a number toward `target`.
function useCountUp(target, duration = 900, resetKey = 0) {
  const [value, setValue] = useState(0);
  const lastReset = useRef(resetKey);
  const reduce = prefersReducedMotion();

  useEffect(() => {
    if (reduce) return undefined;

    let frame;
    // After a refresh, count up from zero instead of from the old value.
    let startValue = lastReset.current !== resetKey ? 0 : undefined;
    lastReset.current = resetKey;
    const startTime = performance.now();

    const tick = (now) => {
      const progress = Math.min(1, (now - startTime) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);

      setValue((current) => {
        if (startValue === undefined) startValue = current;
        return startValue + (target - startValue) * eased;
      });

      if (progress < 1) frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, duration, reduce, resetKey]);

  return reduce ? target : Math.round(value);
}

function getLevel(score) {
  if (score >= 75) return { label: "High engagement", tone: "good" };
  if (score >= 50) return { label: "Moderate engagement", tone: "mid" };
  return { label: "Low engagement", tone: "low" };
}

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

function buildTrend(trend) {
  const values = trend.map((item) => Number(item.value) || 0);
  if (values.length < 2) return null;

  const step = CHART_W / (values.length - 1);
  const points = values.map((v, i) => [
    i * step,
    CHART_H - CHART_PAD - (v / 100) * (CHART_H - CHART_PAD * 2),
  ]);

  const line = points
    .map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`)
    .join(" ");

  return {
    line,
    area: `${line} L${CHART_W},${CHART_H} L0,${CHART_H} Z`,
    last: points[points.length - 1],
  };
}

// Card that tilts toward the pointer. The outer wrapper plays the entrance
// animation; the inner element does the 3D tilt (so they never fight).
function Tilt({ className = "", index = 0, children }) {
  const ref = useRef(null);

  const enabled =
    typeof window !== "undefined" &&
    !prefersReducedMotion() &&
    !window.matchMedia?.("(pointer: coarse)").matches;

  const handleMove = (event) => {
    const el = ref.current;
    if (!enabled || !el) return;

    const box = el.getBoundingClientRect();
    const x = (event.clientX - box.left) / box.width;
    const y = (event.clientY - box.top) / box.height;

    el.style.setProperty("--ry", `${(x - 0.5) * 14}deg`);
    el.style.setProperty("--rx", `${(0.5 - y) * 14}deg`);
    el.style.setProperty("--gx", `${x * 100}%`);
    el.style.setProperty("--gy", `${y * 100}%`);
  };

  const handleLeave = () => {
    const el = ref.current;
    if (!el) return;
    el.style.setProperty("--rx", "0deg");
    el.style.setProperty("--ry", "0deg");
  };

  return (
    <div className="db-tilt-wrap rise" style={{ "--i": index }}>
      <div
        ref={ref}
        className={`${className} db-tilt`}
        onMouseMove={handleMove}
        onMouseLeave={handleLeave}
      >
        {children}
      </div>
    </div>
  );
}

function Dashboard() {
  const navigate = useNavigate();

  const [data, setData] = useState(null);
  const [offline, setOffline] = useState(false);
  const [ringReady, setRingReady] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  // Fetch real session numbers from the backend.
  const load = useCallback(async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/analytics`);
      if (!response.ok) throw new Error("Bad response");
      const json = await response.json();
      setData(json);
      setOffline(false);
    } catch {
      setOffline(true);
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, POLL_MS);
    return () => clearInterval(interval);
  }, [load]);

  // Refresh: reset every value to zero on the backend, then reload.
  const handleRefresh = async () => {
    if (refreshing) return;

    setRefreshing(true);
    setRingReady(false);
    setData(null);
    setRefreshKey((key) => key + 1);

    try {
      await fetch(`${BACKEND_URL}/analytics/reset`, { method: "POST" });
    } catch {
      // Backend offline: load() below will show the offline state.
    }

    await Promise.all([load(), new Promise((resolve) => setTimeout(resolve, 700))]);

    setRingReady(true);
    setRefreshing(false);
  };

  // Let the ring draw in after the first paint.
  useEffect(() => {
    const timer = setTimeout(() => setRingReady(true), 250);
    return () => clearTimeout(timer);
  }, []);

  const live = Boolean(data?.session_active) && !offline;

  const engagement = live ? Number(data.overall_engagement) || 0 : 0;
  const attention = live ? Number(data.attention) || 0 : 0;
  const inView = live ? Number(data.active_students) || 0 : 0;
  const peak = live ? Number(data.peak_students) || 0 : 0;

  const engagementShown = useCountUp(engagement, 1200, refreshKey);
  const attentionShown = useCountUp(attention, 900, refreshKey);
  const inViewShown = useCountUp(inView, 900, refreshKey);
  const peakShown = useCountUp(peak, 900, refreshKey);

  const level = getLevel(engagement);
  const trendList = data?.engagement_trend;
  const trend = useMemo(() => buildTrend(trendList || []), [trendList]);

  const ringOffset = ringReady
    ? CIRCUMFERENCE * (1 - engagement / 100)
    : CIRCUMFERENCE;

  const status = offline ? "offline" : live ? "live" : "idle";
  const statusText = {
    offline: "Backend offline",
    live: "Session running",
    idle: "No session running",
  }[status];

  const dash = (value) => (live ? value : "—");

  return (
    <div className="dashboard">
      <div className="db-glow a" aria-hidden="true" />
      <div className="db-glow b" aria-hidden="true" />

      <header className="dashboard-nav">
        <div className="dashboard-logo">
          <span className="db-logo-mark">◉</span> ClassroomAI
        </div>

        <div className="dashboard-nav-right">
          <ThemeToggle />
          <button onClick={() => navigate("/")} className="logout-btn">
            Logout
          </button>
        </div>
      </header>

      <main className="db-content">
        {/* ---------- Heading ---------- */}
        <div className="db-heading rise" style={{ "--i": 0 }}>
          <div>
            <span className={`db-status ${status}`}>
              <i /> {statusText}
            </span>
            <h1>{greeting()}, teacher</h1>
            <p>
              {live
                ? "Here is how your class is doing right now."
                : offline
                ? "Start the backend server to see live numbers."
                : "Start a session and your live class numbers will appear here."}
            </p>
          </div>

          <div className="db-cube-scene" aria-hidden="true">
            <div className="db-cube">
              {["😊", "😐", "😮", "😴", "👁️", "📊"].map((face, i) => (
                <span key={i} className={`db-face f${i}`}>{face}</span>
              ))}
            </div>
          </div>

          <div className="db-heading-actions">
            <button
              className={`db-refresh ${refreshing ? "spinning" : ""}`}
              onClick={handleRefresh}
              disabled={refreshing}
              aria-label="Refresh dashboard"
            >
              <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                <path
                  d="M20 12a8 8 0 1 1-2.6-5.9M20 4v5h-5"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              {refreshing ? "Refreshing" : "Refresh"}
            </button>

            <button
              className={`db-cta ${live ? "" : "pulse"}`}
              onClick={() => navigate("/classroom")}
            >
              {live ? "Open live classroom" : "Start classroom"}
            </button>
          </div>
        </div>

        {/* ---------- Hero: ring + trend ---------- */}
        <section className="db-hero">
          <Tilt className="db-card db-ring-card" index={1}>
            <div className={`db-ring ${level.tone} ${live ? "is-live" : ""}`}>
              <svg viewBox="0 0 200 200" role="img" aria-label={`Engagement ${engagement} percent`}>
                <circle className="db-orbit" cx="100" cy="100" r="96" />
                <circle className="db-track" cx="100" cy="100" r={RADIUS} />
                <circle
                  className="db-progress"
                  cx="100"
                  cy="100"
                  r={RADIUS}
                  strokeDasharray={CIRCUMFERENCE}
                  strokeDashoffset={ringOffset}
                />
              </svg>
              <div className="db-ring-center">
                <strong>
                  {live ? engagementShown : "—"}
                  {live && <small>%</small>}
                </strong>
                <span>Engagement</span>
              </div>
            </div>
            <p className={`db-level ${live ? level.tone : ""}`}>
              {live ? level.label : "Waiting for a session"}
            </p>
          </Tilt>

          <Tilt className="db-card db-trend-card" index={2}>
            <div className="db-card-head">
              <div>
                <h2>Engagement over time</h2>
                <p>A new point about every 5 seconds</p>
              </div>
              {live && trend && <span className="db-chip">Live</span>}
            </div>

            {trend ? (
              <>
                <svg
                  key={refreshKey}
                  className="db-chart"
                  viewBox={`0 0 ${CHART_W} ${CHART_H}`}
                  preserveAspectRatio="none"
                  role="img"
                  aria-label="Engagement trend"
                >
                  <defs>
                    <linearGradient id="dbFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" style={{ stopColor: "var(--accent-color)", stopOpacity: 0.35 }} />
                      <stop offset="100%" style={{ stopColor: "var(--accent-color)", stopOpacity: 0 }} />
                    </linearGradient>
                  </defs>
                  {[25, 50, 75].map((g) => (
                    <line
                      key={g}
                      className="db-grid"
                      x1="0"
                      x2={CHART_W}
                      y1={CHART_H - CHART_PAD - (g / 100) * (CHART_H - CHART_PAD * 2)}
                      y2={CHART_H - CHART_PAD - (g / 100) * (CHART_H - CHART_PAD * 2)}
                    />
                  ))}
                  <path className="db-area" d={trend.area} fill="url(#dbFill)" />
                  <path className="db-line" d={trend.line} pathLength="1" />
                </svg>
                <div className="db-axis">
                  <span>{trendList[0].time}</span>
                  <span>{trendList[trendList.length - 1].time}</span>
                </div>
              </>
            ) : (
              <div className="db-empty">
                <span aria-hidden="true">📈</span>
                <p>
                  {live
                    ? "Collecting data. The chart appears after a few seconds."
                    : "The chart appears once a session is running."}
                </p>
              </div>
            )}
          </Tilt>
        </section>

        {/* ---------- Key numbers ---------- */}
        <section className="db-tiles">
          {[
            { icon: "👁️", label: "Attention", value: dash(`${attentionShown}%`), hint: "Based on open and closed eyes" },
            { icon: "👥", label: "Students in view", value: dash(inViewShown), hint: "Faces the camera sees now" },
            { icon: "🏔️", label: "Most at once", value: dash(peakShown), hint: "Highest count this session" },
           ,
          ].map((tile, index) => (
            <Tilt className="db-card db-tile" index={3 + index} key={tile.label}>
              <span className="db-tile-icon" aria-hidden="true">{tile.icon}</span>
              <small>{tile.label}</small>
              <strong>{tile.value}</strong>
              <em>{tile.hint}</em>
            </Tilt>
          ))}
        </section>

        {/* ---------- Where to next ---------- */}
        <section className="db-actions">
          {[
            { icon: "🎥", title: "Live classroom", text: "Watch the camera feed with emotion and eye tracking.", to: "/classroom", primary: true },
            { icon: "📼", title: "Analyze a recording", text: "Upload a class video and get a report per student.", to: "/recorded-video" },
            { icon: "📊", title: "Full analytics", text: "Emotion mix, attention breakdown and insights.", to: "/analytics" },
          ].map((action, index) => (
            <button
              key={action.to}
              className={`db-action rise ${action.primary ? "primary" : ""}`}
              style={{ "--i": 7 + index }}
              onClick={() => navigate(action.to)}
            >
              <span className="db-action-icon" aria-hidden="true">{action.icon}</span>
              <span className="db-action-text">
                <strong>{action.title}</strong>
                <em>{action.text}</em>
              </span>
              <span className="db-action-arrow" aria-hidden="true">→</span>
            </button>
          ))}
        </section>
      </main>
    </div>
  );
}

export default Dashboard;