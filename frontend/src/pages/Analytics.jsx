import { useNavigate } from "react-router-dom";
import ThemeToggle from "../components/ThemeToggle";
import "./Analytics.css";

function Analytics() {
  const navigate = useNavigate();

  return (
    <div className="analytics-page">

      <header className="analytics-nav">
        <div className="analytics-logo">
          <span>◉</span>
          ClassroomAI
        </div>

        <div className="analytics-nav-right">
          <ThemeToggle />
          <button onClick={() => navigate("/dashboard")}>
            Dashboard
          </button>
        </div>
      </header>

      <main className="analytics-content">

        <div className="analytics-heading">
          <div>
            <p>CLASSROOM ANALYTICS</p>
            <h1>Engagement Overview</h1>
            <span>
              Computer Science — AI
            </span>
          </div>

          <button onClick={() => navigate("/classroom")}>
            ← Live Classroom
          </button>
        </div>

        <div className="analytics-cards">

          <div>
            <small>Overall Engagement</small>
            <strong>78%</strong>
            <span>↑ 6.4% this session</span>
          </div>

          <div>
            <small>Attention</small>
            <strong>82%</strong>
            <span>↑ 4.2% this session</span>
          </div>

          <div>
            <small>Participation</small>
            <strong>69%</strong>
            <span>↑ 8.1% this session</span>
          </div>

          <div>
            <small>Students</small>
            <strong>32</strong>
            <span>Present</span>
          </div>

        </div>

        <section className="chart-card">

          <div className="chart-header">
            <div>
              <small>ENGAGEMENT TREND</small>
              <h2>Engagement Over Time</h2>
            </div>

            <select>
              <option>Current Session</option>
              <option>Today</option>
              <option>This Week</option>
            </select>
          </div>

          <div className="fake-chart">

            <div className="chart-line">
              <span style={{ height: "45%" }}></span>
              <span style={{ height: "58%" }}></span>
              <span style={{ height: "52%" }}></span>
              <span style={{ height: "72%" }}></span>
              <span style={{ height: "65%" }}></span>
              <span style={{ height: "80%" }}></span>
              <span style={{ height: "78%" }}></span>
              <span style={{ height: "90%" }}></span>
            </div>

          </div>

        </section>

        <section className="analysis-grid">

          <div className="analysis-card">
            <small>EMOTION DISTRIBUTION</small>
            <h2>Classroom Mood</h2>

            <div className="emotion-row">
              <span>😊 Positive</span>
              <strong>74%</strong>
            </div>

            <div className="emotion-row">
              <span>😐 Neutral</span>
              <strong>18%</strong>
            </div>

            <div className="emotion-row">
              <span>😕 Confused</span>
              <strong>6%</strong>
            </div>

            <div className="emotion-row">
              <span>😴 Disengaged</span>
              <strong>2%</strong>
            </div>

          </div>

          <div className="analysis-card">
            <small>CLASS INSIGHTS</small>
            <h2>AI Observations</h2>

            <div className="insight">
              <span>✓</span>
              <p>Most students are maintaining good attention.</p>
            </div>

            <div className="insight">
              <span>!</span>
              <p>Participation dropped slightly during the middle of the session.</p>
            </div>

            <div className="insight">
              <span>✓</span>
              <p>Overall classroom engagement is above average.</p>
            </div>

          </div>

        </section>

      </main>

    </div>
  );
}

export default Analytics;