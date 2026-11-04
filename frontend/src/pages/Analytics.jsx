
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import ThemeToggle from "../components/ThemeToggle";
import SessionReports from "../components/SessionReports";
import "./Analytics.css";

const BACKEND_URL = "http://127.0.0.1:5000";

const EMOTION_EMOJIS = {
  Happy: "😊",
  Neutral: "😐",
  Sad: "😢",
  Angry: "😠",
  Fear: "😨",
  Disgust: "🤢",
  Surprise: "😮",
};

const EYE_EMOJIS = {
  Open: "👁️",
  Blink: "👀",
  Close: "🔒",
  Drowsy: "😪",
  Sleeping: "😴",
};

function Analytics() {
  const navigate = useNavigate();

  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchAnalytics = useCallback(async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/analytics`);

      if (!response.ok) {
        throw new Error("Failed to fetch analytics data");
      }

      const data = await response.json();

      setAnalytics(data);
      setError("");
    } catch (err) {
      console.error("Analytics error:", err);
      setError(
        "Unable to connect to the analytics server. Make sure the backend is running."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAnalytics();

    const interval = setInterval(fetchAnalytics, 5000);

    return () => clearInterval(interval);
  }, [fetchAnalytics]);

  const emotionEntries = useMemo(() => {
    if (!analytics?.emotion_distribution) return [];

    return Object.entries(analytics.emotion_distribution).sort(
      (a, b) => b[1] - a[1]
    );
  }, [analytics]);

  const attentionEntries = useMemo(() => {
    if (!analytics?.attention_distribution) return [];

    return Object.entries(analytics.attention_distribution).sort(
      (a, b) => b[1] - a[1]
    );
  }, [analytics]);

  const trend = analytics?.engagement_trend || [];

  const maxTrendValue =
    trend.length > 0
      ? Math.max(...trend.map((item) => Number(item.value) || 0), 100)
      : 100;

  const getTrendHeight = (value) => {
    const numericValue = Number(value) || 0;

    if (maxTrendValue <= 0) return 0;

    return Math.max(
      4,
      Math.min(100, (numericValue / maxTrendValue) * 100)
    );
  };

  const getEngagementLabel = (value) => {
    if (value >= 75) return "High engagement";
    if (value >= 50) return "Moderate engagement";
    return "Low engagement";
  };

  const getAttentionLabel = (value) => {
    if (value >= 75) return "Strong attention";
    if (value >= 50) return "Moderate attention";
    return "Low attention";
  };

  const generateInsights = () => {
    if (!analytics) return [];

    const insights = [];

    const engagement = Number(analytics.overall_engagement) || 0;
    const attention = Number(analytics.attention) || 0;

    if (engagement >= 75) {
      insights.push({
        type: "success",
        icon: "✓",
        text: `Overall engagement is strong at ${engagement}%.`,
      });
    } else if (engagement >= 50) {
      insights.push({
        type: "warning",
        icon: "!",
        text: `Overall engagement is moderate at ${engagement}%.`,
      });
    } else {
      insights.push({
        type: "danger",
        icon: "!",
        text: `Overall engagement is currently low at ${engagement}%.`,
      });
    }

    if (attention >= 75) {
      insights.push({
        type: "success",
        icon: "✓",
        text: `Students are showing strong attention at ${attention}%.`,
      });
    } else if (attention >= 50) {
      insights.push({
        type: "warning",
        icon: "!",
        text: `Attention is moderate at ${attention}%.`,
      });
    } else {
      insights.push({
        type: "danger",
        icon: "!",
        text: `Attention is currently low at ${attention}%.`,
      });
    }

    if (emotionEntries.length > 0) {
      const [emotion, percentage] = emotionEntries[0];

      insights.push({
        type: "info",
        icon: EMOTION_EMOJIS[emotion] || "•",
        text: `${emotion} is the dominant detected emotion at ${percentage}%.`,
      });
    }

    if (attentionEntries.length > 0) {
      const [state, percentage] = attentionEntries[0];

      insights.push({
        type: "info",
        icon: EYE_EMOJIS[state] || "•",
        text: `${state} is the most common eye state at ${percentage}%.`,
      });
    }

    return insights;
  };

  const insights = generateInsights();

  const overallEngagement = Number(analytics?.overall_engagement) || 0;
  const overallAttention = Number(analytics?.attention) || 0;

  return (
    <div className="analytics-page">
      <header className="analytics-nav">
        <button
          className="analytics-brand"
          onClick={() => navigate("/dashboard")}
          aria-label="Go to dashboard"
        >
          <span className="brand-mark">◉</span>
          <span>Classroom<span className="brand-light">AI</span></span>
        </button>

        <div className="analytics-nav-actions">
          <ThemeToggle />

          <button
            className="nav-dashboard-btn"
            onClick={() => navigate("/dashboard")}
          >
            Dashboard <span>↗</span>
          </button>
        </div>
      </header>

      <main className="analytics-content">
        <section className="analytics-hero">
          <div>
            <div className="eyebrow">
              <span className="eyebrow-line"></span>
              CLASSROOM ANALYTICS
            </div>

            <h1>Engagement <span>Overview.</span></h1>

            <p className="analytics-subtitle">
              Computer Science — AI
            </p>
          </div>

          <button
            className="live-classroom-btn"
            onClick={() => navigate("/classroom")}
          >
            <span>←</span> Live Classroom
          </button>
        </section>

        {loading && (
          <div className="analytics-status">
            <div className="analytics-spinner"></div>
            <p>Loading classroom analytics...</p>
          </div>
        )}

        {!loading && error && (
          <div className="analytics-error">
            <div>
              <strong>Analytics unavailable</strong>
              <p>{error}</p>
            </div>

            <button onClick={fetchAnalytics}>Try Again ↻</button>
          </div>
        )}

        {!loading && !error && analytics && (
          <>
            <section className="metrics-section">
              <div className="section-label">
                <span>01</span> PERFORMANCE SNAPSHOT
              </div>

              <div className="analytics-cards">
                <article className="metric-card metric-primary">
                  <div className="metric-top">
                    <span>OVERALL ENGAGEMENT</span>
                    <span className="metric-symbol">↗</span>
                  </div>

                  <div className="metric-value">
                    {overallEngagement}<span>%</span>
                  </div>

                  <div className="metric-bottom">
                    <span className="metric-dot"></span>
                    {getEngagementLabel(overallEngagement)}
                  </div>
                </article>

                <article className="metric-card">
                  <div className="metric-top">
                    <span>ATTENTION</span>
                    <span className="metric-symbol">◎</span>
                  </div>

                  <div className="metric-value">
                    {overallAttention}<span>%</span>
                  </div>

                  <div className="metric-bottom">
                    <span className="metric-dot"></span>
                    {getAttentionLabel(overallAttention)}
                  </div>
                </article>

                <article className="metric-card">
                  <div className="metric-top">
                    <span>ACTIVE STUDENTS</span>
                    <span className="metric-symbol">◌</span>
                  </div>

                  <div className="metric-value">
                    {analytics.active_students ?? 0}
                  </div>

                  <div className="metric-bottom">
                    <span className="metric-dot"></span>
                    Peak: {analytics.peak_students ?? 0}
                  </div>
                </article>
              </div>
            </section>

            <section className="chart-card">
              <div className="section-heading">
                <div>
                  <div className="section-label">
                    <span>02</span> REAL-TIME MONITORING
                  </div>

                  <h2>Engagement Over Time</h2>
                  <p>Classroom engagement observations</p>
                </div>

                <div className="live-indicator">
                  <span></span> LIVE DATA
                </div>
              </div>

              {trend.length === 0 ? (
                <div className="empty-chart">
                  <div className="empty-chart-icon">⌁</div>
                  <h3>Waiting for AI observations</h3>
                  <p>
                    Start the classroom camera to generate engagement data.
                  </p>
                </div>
              ) : (
                <div className="real-chart">
                  <div className="chart-y-axis">
                    <span>100%</span>
                    <span>75%</span>
                    <span>50%</span>
                    <span>25%</span>
                    <span>0%</span>
                  </div>

                  <div className="chart-area">
                    <div className="chart-grid-lines">
                      <span></span>
                      <span></span>
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>

                    <div className="chart-bars">
                      {trend.map((point, index) => {
                        const value = Number(point.value) || 0;

                        return (
                          <div
                            className="chart-point"
                            key={`${point.time}-${index}`}
                            title={`${point.time}: ${value}%`}
                          >
                            <div
                              className="chart-bar"
                              style={{
                                height: `${getTrendHeight(value)}%`,
                              }}
                            >
                              <span>{value}%</span>
                            </div>

                            <small>{point.time}</small>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}

              <div className="chart-summary">
                <span>{trend.length} observations recorded</span>

                {trend.length > 0 && (
                  <strong>
                    Latest reading
                    <span>
                      {Number(trend[trend.length - 1].value) || 0}%
                    </span>
                  </strong>
                )}
              </div>
            </section>

            <section className="distribution-section">
              <div className="section-label">
                <span>03</span> CLASSROOM BEHAVIOUR
              </div>

              <div className="analysis-grid">
                <article className="analysis-card">
                  <div className="section-heading compact-heading">
                    <div>
                      <h2>Classroom Mood</h2>
                      <p>Emotion distribution</p>
                    </div>
                    <span className="panel-index">A</span>
                  </div>

                  {emotionEntries.length === 0 ? (
                    <div className="no-data">
                      No emotion data available yet.
                    </div>
                  ) : (
                    <div className="distribution-list">
                      {emotionEntries.map(([emotion, percentage]) => (
                        <div
                          className="distribution-item"
                          key={emotion}
                        >
                          <div className="distribution-top">
                            <span className="distribution-name">
                              <span className="distribution-icon">
                                {EMOTION_EMOJIS[emotion] || "•"}
                              </span>
                              {emotion}
                            </span>

                            <strong>{percentage}%</strong>
                          </div>

                          <div className="progress-track">
                            <div
                              className="progress-fill"
                              style={{
                                width: `${Math.min(
                                  100,
                                  Math.max(0, Number(percentage) || 0)
                                )}%`,
                              }}
                            ></div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </article>

                <article className="analysis-card">
                  <div className="section-heading compact-heading">
                    <div>
                      <h2>Eye State Analysis</h2>
                      <p>Attention distribution</p>
                    </div>
                    <span className="panel-index">B</span>
                  </div>

                  {attentionEntries.length === 0 ? (
                    <div className="no-data">
                      No attention data available yet.
                    </div>
                  ) : (
                    <div className="distribution-list">
                      {attentionEntries.map(([state, percentage]) => (
                        <div
                          className="distribution-item"
                          key={state}
                        >
                          <div className="distribution-top">
                            <span className="distribution-name">
                              <span className="distribution-icon">
                                {EYE_EMOJIS[state] || "•"}
                              </span>
                              {state}
                            </span>

                            <strong>{percentage}%</strong>
                          </div>

                          <div className="progress-track">
                            <div
                              className="progress-fill"
                              style={{
                                width: `${Math.min(
                                  100,
                                  Math.max(0, Number(percentage) || 0)
                                )}%`,
                              }}
                            ></div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </article>
              </div>
            </section>

            <section className="insights-card">
              <div className="insights-heading">
                <div>
                  <div className="section-label">
                    <span>04</span> AI ANALYSIS
                  </div>

                  <h2>AI Observations</h2>
                  <p>Insights generated from classroom data</p>
                </div>

                <div className="insights-ai-mark">AI</div>
              </div>

              <div className="insights-list">
                {insights.length === 0 ? (
                  <div className="no-data">
                    Not enough data to generate insights.
                  </div>
                ) : (
                  insights.map((insight, index) => (
                    <div
                      className={`insight ${insight.type}`}
                      key={index}
                    >
                      <span className="insight-icon">
                        {insight.icon}
                      </span>

                      <p>{insight.text}</p>
                    </div>
                  ))
                )}
              </div>
            </section>

            <section className="session-section">
              <div className="section-label">
                <span>05</span> SESSION DETAILS
              </div>

              <div className="session-info">
                <div>
                  <small>SESSION STATUS</small>
                  <strong className="session-status-value">
                    <span
                      className={
                        analytics.session_active
                          ? "session-dot active"
                          : "session-dot"
                      }
                    ></span>
                    {analytics.session_active ? "Active" : "Inactive"}
                  </strong>
                </div>

                <div>
                  <small>TOTAL OBSERVATIONS</small>
                  <strong>
                    {analytics.engagement_trend?.length || 0}
                  </strong>
                </div>

                <div>
                  <small>PEAK STUDENTS</small>
                  <strong>{analytics.peak_students ?? 0}</strong>
                </div>
              </div>
            </section>
          </>
        )}

        <section className="reports-section">
          <div className="section-label">
            <span>06</span> SAVED CLASSROOM DATA
          </div>

          <SessionReports backendUrl={BACKEND_URL} />
        </section>
      </main>
    </div>
  );
}

export default Analytics;
