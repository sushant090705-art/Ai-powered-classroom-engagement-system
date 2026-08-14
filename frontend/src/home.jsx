import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./App.css";

function Home() {
  const navigate = useNavigate();

  const [backendStatus, setBackendStatus] = useState("Connecting...");

  useEffect(() => {
    fetch("http://127.0.0.1:5000/")
      .then((response) => response.text())
      .then(() => {
        setBackendStatus("Connected");
      })
      .catch(() => {
        setBackendStatus("Offline");
      });
  }, []);

  return (
    <div className="app">

      {/* Navbar */}
      <nav className="navbar">

        <div className="logo">
          <span className="logo-icon">◉</span>
          <span>ClassroomAI</span>
        </div>

        <div className="nav-links">
          <a href="#home">Home</a>
          <a href="#features">Features</a>
          <a href="#about">About</a>
        </div>

        <button
          className="login-btn"
          onClick={() => navigate("/login")}
        >
          Teacher Login
        </button>

      </nav>

      {/* Hero */}
      <main id="home" className="hero">

        <div className="hero-content">

          <div className="status">
            <span className="status-dot"></span>
            AI Classroom Analytics
          </div>

          <h1>
            Understand Your
            <span> Classroom Engagement</span>
          </h1>

          <p>
            An AI-powered classroom monitoring system that analyzes
            attention, participation, emotions and activity to provide
            meaningful classroom engagement insights.
          </p>

          <div className="hero-buttons">

            <button
              className="primary-btn"
              onClick={() => navigate("/login")}
            >
              Start Classroom
            </button>

            <button
              className="secondary-btn"
              onClick={() => navigate("/dashboard")}
            >
              View Dashboard
            </button>

          </div>

          <div className="backend-status">
            Backend:

            <span
              className={
                backendStatus === "Connected"
                  ? "online"
                  : "offline"
              }
            >
              ● {backendStatus}
            </span>

          </div>

        </div>

        {/* Dashboard Preview */}
        <div className="dashboard-preview">

          <div className="preview-header">

            <div>
              <small>LIVE CLASSROOM</small>
              <h3>Computer Science — AI</h3>
            </div>

            <div className="live">
              <span></span> LIVE
            </div>

          </div>

          <div className="engagement-circle">

            <div>
              <strong>78%</strong>
              <small>Engagement</small>
            </div>

          </div>

          <div className="stats">

            <div className="stat-card">
              <span className="stat-icon">👁️</span>

              <div>
                <small>Attention</small>
                <strong>82%</strong>
              </div>
            </div>

            <div className="stat-card">
              <span className="stat-icon">🙋</span>

              <div>
                <small>Participation</small>
                <strong>69%</strong>
              </div>
            </div>

            <div className="stat-card">
              <span className="stat-icon">😊</span>

              <div>
                <small>Positive Mood</small>
                <strong>74%</strong>
              </div>
            </div>

          </div>

        </div>

      </main>

      {/* Features */}
      <section id="features" className="features-section">

        <div className="section-heading">

          <span>POWERFUL ANALYTICS</span>

          <h2>
            Everything You Need to Understand Engagement
          </h2>

          <p>
            Turn classroom activity into useful insights with
            AI-powered analysis.
          </p>

        </div>

        <div className="feature-grid">

          <div className="feature-card">
            <div className="feature-icon">👁️</div>

            <h3>Attention Detection</h3>

            <p>
              Analyze student attention and identify changes
              in classroom focus.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon">😊</div>

            <h3>Emotion Analysis</h3>

            <p>
              Analyze facial expressions to understand classroom
              emotional patterns.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon">📊</div>

            <h3>Engagement Analytics</h3>

            <p>
              Convert multiple classroom signals into meaningful
              engagement metrics.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon">📈</div>

            <h3>Real-Time Dashboard</h3>

            <p>
              Monitor classroom engagement through a simple
              teacher dashboard.
            </p>
          </div>

        </div>

      </section>

      {/* Footer */}
      <footer>

        <div className="logo">
          <span className="logo-icon">◉</span>
          ClassroomAI
        </div>

        <p>
          AI-powered classroom engagement analytics
        </p>

      </footer>

    </div>
  );
}

export default Home;