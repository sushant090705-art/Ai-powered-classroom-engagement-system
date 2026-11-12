import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import ThemeToggle from "./components/ThemeToggle";
import "./Home.css";

function Home() {
  const navigate = useNavigate();
  const [backendStatus, setBackendStatus] = useState("Connecting...");

  useEffect(() => {
    fetch("http://127.0.0.1:5000/")
      .then((response) => {
        if (!response.ok) {
          throw new Error("Backend unavailable");
        }
        setBackendStatus("Connected");
      })
      .catch(() => {
        setBackendStatus("Offline");
      });
  }, []);

  const features = [
    {
      icon: "◉",
      title: "Attention Detection",
      description:
        "Understand classroom focus by analyzing student eye states and attention patterns.",
    },
    {
      icon: "◎",
      title: "Emotion Analysis",
      description:
        "Identify facial emotion patterns to better understand the classroom environment.",
    },
    {
      icon: "▥",
      title: "Engagement Insights",
      description:
        "Combine AI-detected signals into easy-to-understand engagement indicators.",
    },
    {
      icon: "⌁",
      title: "Live Analytics",
      description:
        "View classroom trends, session summaries and student-level reports.",
    },
  ];

  return (
    <div className="home-page" id="home">
      <nav className="home-navbar">
        <button
          className="home-brand"
          onClick={() => navigate("/")}
          aria-label="ClassroomAI home"
        >
          <span className="brand-mark">C</span>
          <span>
            Classroom<span className="brand-highlight">AI</span>
          </span>
        </button>

        <div className="home-nav-links">
          <Link to="/">Home</Link>
          <a href="#features">Features</a>
          <a href="#how-it-works">How it works</a>
          <Link to="/about">About</Link>
        </div>

        <div className="home-nav-actions">
          <ThemeToggle />
          <button
            className="home-login-btn"
            onClick={() => navigate("/login")}
          >
            Teacher Login <span>↗</span>
          </button>
        </div>
      </nav>

      <main>
        <section className="home-hero">
          <div className="hero-copy">
            <div className="hero-eyebrow">
              <span className="eyebrow-dot"></span>
              AI-POWERED CLASSROOM INTELLIGENCE
            </div>

            <h1>
              See beyond the
              <span> classroom.</span>
              <br />
              Understand engagement.
            </h1>

            <p className="hero-description">
              Make classroom engagement easier to understand.
              Analyze attention, facial emotion patterns and
              classroom activity with AI-powered insights.
            </p>

            <div className="hero-actions">
              <button
                className="hero-primary-btn"
                onClick={() => navigate("/login")}
              >
                Start a classroom <span>→</span>
              </button>

              <a className="hero-secondary-btn" href="#features">
                Explore features <span>↓</span>
              </a>
            </div>

            <div className="hero-trust-row">
              <div className="backend-indicator">
                <span
                  className={
                    backendStatus === "Connected"
                      ? "backend-dot is-online"
                      : backendStatus === "Offline"
                      ? "backend-dot is-offline"
                      : "backend-dot"
                  }
                ></span>
                Backend: {backendStatus}
              </div>

              <span className="trust-divider"></span>
              <span>Built for educators</span>
            </div>
          </div>

          <div className="hero-visual">
            <div className="visual-glow"></div>

            <div className="preview-window">
              <div className="preview-topbar">
                <div className="window-dots">
                  <i></i>
                  <i></i>
                  <i></i>
                </div>
                <span>CLASSROOM OVERVIEW</span>
                <span className="preview-tag">SAMPLE</span>
              </div>

              <div className="preview-content">
                <div className="preview-heading">
                  <div>
                    <span className="preview-label">SESSION PREVIEW</span>
                    <h3>Computer Science</h3>
                    <p>Introduction to Artificial Intelligence</p>
                  </div>
                  <span className="preview-live">● PREVIEW</span>
                </div>

                <div className="preview-main-stat">
                  <div className="preview-score">
                    <div className="score-ring">
                      <div className="score-ring-inner">
                        <strong>78%</strong>
                        <span>Engagement</span>
                      </div>
                    </div>
                  </div>

                  <div className="preview-summary">
                    <span className="summary-label">SESSION INSIGHT</span>
                    <h4>Classroom engagement</h4>
                    <p>
                      A sample view of the insights available
                      during a classroom session.
                    </p>
                    <div className="summary-line">
                      <span></span>
                      <span></span>
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  </div>
                </div>

                <div className="preview-metrics">
                  <div className="metric-box">
                    <span className="metric-symbol">◉</span>
                    <span>Attention</span>
                    <strong>82%</strong>
                  </div>
                  <div className="metric-box">
                    <span className="metric-symbol">◎</span>
                    <span>Positive mood</span>
                    <strong>74%</strong>
                  </div>
                  <div className="metric-box">
                    <span className="metric-symbol">▥</span>
                    <span>Participation</span>
                    <strong>69%</strong>
                  </div>
                </div>

                <div className="preview-footnote">
                  Illustrative data · Not a live session
                </div>
              </div>
            </div>

            <div className="floating-note">
              <span className="floating-note-icon">✦</span>
              <div>
                <strong>AI-powered insights</strong>
                <small>Understand classroom patterns</small>
              </div>
            </div>
          </div>
        </section>

        <section className="home-features" id="features">
          <div className="home-section-heading">
            <span className="section-eyebrow">WHAT THE SYSTEM OFFERS</span>
            <h2>
              Everything you need to
              <span> understand engagement.</span>
            </h2>
            <p>
              Turn classroom activity into meaningful information
              that helps teachers understand student engagement.
            </p>
          </div>

          <div className="home-feature-grid">
            {features.map((feature, index) => (
              <article className="home-feature-card" key={feature.title}>
                <div className="feature-card-top">
                  <span className="feature-card-icon">{feature.icon}</span>
                  <span className="feature-number">0{index + 1}</span>
                </div>
                <h3>{feature.title}</h3>
                <p>{feature.description}</p>
                <span className="feature-arrow">↗</span>
              </article>
            ))}
          </div>
        </section>

        <section className="home-process" id="how-it-works">
          <div className="home-section-heading">
            <span className="section-eyebrow">SIMPLE WORKFLOW</span>
            <h2>From classroom to insights.</h2>
            <p>
              A simple process designed to help teachers understand
              classroom activity.
            </p>
          </div>

          <div className="process-grid">
            <article className="process-step">
              <span className="process-number">01</span>
              <h3>Start a session</h3>
              <p>
                The teacher opens the classroom and starts the
                camera-based monitoring session.
              </p>
            </article>

            <article className="process-step">
              <span className="process-number">02</span>
              <h3>AI analyzes activity</h3>
              <p>
                The system analyzes visible faces, eye states and
                facial emotion patterns.
              </p>
            </article>

            <article className="process-step">
              <span className="process-number">03</span>
              <h3>Review insights</h3>
              <p>
                Teachers can review engagement indicators and
                classroom reports through the dashboard.
              </p>
            </article>
          </div>
        </section>

        <section className="home-about" id="about">
          <div>
            <span className="section-eyebrow">ABOUT CLASSROOMAI</span>
            <h2>Better visibility into classroom engagement.</h2>
            <p>
              ClassroomAI is an AI-powered classroom engagement
              analysis system designed to help educators review
              attention, emotion patterns and classroom activity
              through an organized dashboard.
            </p>
          </div>

          <button
            className="about-cta"
            onClick={() => navigate("/about")}
          >
            Explore the platform <span>→</span>
          </button>
        </section>
      </main>

      <footer className="home-footer">
        <button
          className="home-brand footer-brand"
          onClick={() => navigate("/")}
        >
          <span className="brand-mark">C</span>
          <span>
            Classroom<span className="brand-highlight">AI</span>
          </span>
        </button>

        <p>Making classroom engagement easier to understand.</p>

        <span className="footer-copyright">
          © {new Date().getFullYear()} ClassroomAI. All rights reserved.
        </span>
      </footer>
    </div>
  );
}

export default Home;