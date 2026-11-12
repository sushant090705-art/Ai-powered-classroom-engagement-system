
import { useNavigate } from "react-router-dom";
import ThemeToggle from "../components/ThemeToggle";
import "./About.css";

const workflow = [
  {
    number: "01",
    icon: "📹",
    title: "Video Input",
    description: "Classroom camera or recorded classroom video is provided as input.",
  },
  {
    number: "02",
    icon: "🎞️",
    title: "Frame Processing",
    description: "Video is divided into frames for computer vision analysis.",
  },
  {
    number: "03",
    icon: "🎯",
    title: "YOLO Detection",
    description: "Students or persons are detected and localized in classroom frames.",
  },
  {
    number: "04",
    icon: "👤",
    title: "Face Processing",
    description: "Detected student or facial regions are prepared for further analysis.",
  },
  {
    number: "05",
    icon: "😊",
    title: "Emotion Analysis",
    description: "FER2013-based facial expression analysis identifies expression categories.",
  },
  {
    number: "06",
    icon: "👁️",
    title: "Eye-State Analysis",
    description: "Eye-related visual information is considered as an additional indicator.",
  },
  {
    number: "07",
    icon: "🧠",
    title: "Engagement Analysis",
    description: "Visual observations are combined into approximate engagement indicators.",
  },
  {
    number: "08",
    icon: "📊",
    title: "Analytics",
    description: "Classroom-level and student-wise summaries are organized.",
  },
  {
    number: "09",
    icon: "📑",
    title: "Reports & Alerts",
    description: "Teachers and authorized personnel can review reports and relevant alerts.",
  },
];

const features = [
  {
    icon: "🎯",
    title: "Student Detection",
    description: "YOLO-based detection helps identify and localize students in classroom frames.",
  },
  {
    icon: "😊",
    title: "Facial Expression Analysis",
    description: "FER2013-based analysis classifies facial expressions into seven categories.",
  },
  {
    icon: "👁️",
    title: "Eye-State Analysis",
    description: "Eye-state information provides an additional visual signal for analysis.",
  },
  {
    icon: "📈",
    title: "Engagement Insights",
    description: "The system combines observations into understandable engagement indicators.",
  },
  {
    icon: "📋",
    title: "Student-wise Reports",
    description: "Separate student-level observations can be organized when sufficient data is available.",
  },
  {
    icon: "🔔",
    title: "Alerts & Recommendations",
    description: "Configured alerts can highlight patterns that may need institutional attention.",
  },
];

const technologies = [
  { name: "React", role: "Frontend", icon: "⚛️" },
  { name: "Python", role: "Programming", icon: "🐍" },
  { name: "Flask", role: "Backend API", icon: "🌶️" },
  { name: "MongoDB", role: "Database", icon: "🍃" },
  { name: "YOLO", role: "Object Detection", icon: "🎯" },
  { name: "OpenCV", role: "Computer Vision", icon: "👁️" },
  { name: "TensorFlow / Keras", role: "Deep Learning", icon: "🧠" },
  { name: "MediaPipe", role: "Visual Features", icon: "🔍" },
];

function About() {
  const navigate = useNavigate();

  return (
    <div className="about-page">
      <nav className="about-navbar">
        <button className="about-brand" onClick={() => navigate("/")}>
          <span className="about-brand-mark">C</span>
          <span>Classroom<span>AI</span></span>
        </button>

        <div className="about-nav-actions">
          <button className="about-home-link" onClick={() => navigate("/")}>
            ← Back to Home
          </button>
          <ThemeToggle />
        </div>
      </nav>

      <main>
        {/* HERO */}
        <section className="about-hero">
          <div className="about-hero-overlay" />
          <div className="about-hero-content">
            <span className="about-eyebrow">
              ABOUT THE PROJECT
            </span>

            <h1>
              Making classrooms
              <span> easier to understand.</span>
            </h1>

            <p>
              An AI-powered classroom engagement detection and analysis
              system designed to turn classroom video observations into
              meaningful insights for educators.
            </p>

            <button
              className="about-primary-btn"
              onClick={() =>
                document.getElementById("about-overview")?.scrollIntoView({
                  behavior: "smooth",
                })
              }
            >
              Discover the Project <span>↓</span>
            </button>
          </div>

          <div className="about-hero-label">
            <span className="hero-label-dot" />
            AI · COMPUTER VISION · EDUCATION
          </div>
        </section>

        {/* OVERVIEW */}
        <section className="about-section about-overview" id="about-overview">
          <div className="about-overview-copy">
            <span className="about-eyebrow">01 — PROJECT OVERVIEW</span>
            <h2>
              Understanding classroom activity through
              <span> artificial intelligence.</span>
            </h2>

            <p>
              ClassroomAI is an AI-powered classroom engagement detection
              and analysis platform. It is designed to process real-time
              classroom camera streams or uploaded classroom recordings.
            </p>

            <p>
              The system uses computer vision and deep-learning techniques
              to analyse student detection, facial expressions and
              eye-state-related information. These observations are
              organized into classroom-level and student-wise insights.
            </p>

            <p>
              Its purpose is to support teachers with additional
              information when reviewing classroom sessions, not to
              replace their judgment.
            </p>
          </div>

          <div className="about-visual-card">
            <div className="visual-card-top">
              <span>CLASSROOM ANALYSIS</span>
              <span className="visual-card-symbol">◉</span>
            </div>

            <div className="visual-classroom">
              <div className="visual-board">
                <span>AI</span>
                <small>CLASSROOM INSIGHTS</small>
              </div>
              <div className="visual-person teacher-person">👩‍🏫</div>
              <div className="visual-students">
                <span>🧑‍🎓</span>
                <span>👩‍🎓</span>
                <span>🧑‍🎓</span>
                <span>👨‍🎓</span>
              </div>
              <div className="visual-scan-line" />
            </div>

            <div className="visual-card-bottom">
              <span>Computer Vision</span>
              <span>AI-based Analysis</span>
            </div>
          </div>
        </section>

        {/* PROBLEM AND SOLUTION */}
        <section className="about-problem-section">
          <div className="about-section-heading">
            <span className="about-eyebrow">02 — WHY CLASSROOMAI?</span>
            <h2>From manual observation to structured insights.</h2>
            <p>
              A classroom has many activities happening at the same time.
              Reviewing them continuously can be challenging.
            </p>
          </div>

          <div className="problem-solution-grid">
            <article className="problem-card">
              <div className="problem-icon">◌</div>
              <span>THE CHALLENGE</span>
              <h3>Classroom observation can be difficult.</h3>
              <p>
                Teachers may find it difficult to continuously observe
                every student and review classroom activity throughout
                an entire session.
              </p>
            </article>

            <div className="solution-arrow">→</div>

            <article className="solution-card">
              <div className="problem-icon">✦</div>
              <span>THE APPROACH</span>
              <h3>AI-assisted classroom analysis.</h3>
              <p>
                ClassroomAI processes video observations and organizes
                available visual indicators into summaries, analytics
                and reports for review.
              </p>
            </article>
          </div>
        </section>

        {/* WORKFLOW */}
        <section className="about-section about-workflow-section" id="workflow">
          <div className="about-section-heading">
            <span className="about-eyebrow">03 — HOW IT WORKS</span>
            <h2>From classroom video to useful insights.</h2>
            <p>
              The system follows an AI-based processing pipeline to
              convert video input into structured classroom information.
            </p>
          </div>

          <div className="workflow-grid">
            {workflow.map((step, index) => (
              <article className="workflow-card" key={step.number}>
                <div className="workflow-card-top">
                  <span className="workflow-number">{step.number}</span>
                  <span className="workflow-icon">{step.icon}</span>
                </div>
                <h3>{step.title}</h3>
                <p>{step.description}</p>
                {index !== workflow.length - 1 && (
                  <span className="workflow-connector">↘</span>
                )}
              </article>
            ))}
          </div>
        </section>

        {/* FEATURES */}
        <section className="about-feature-section">
          <div className="about-section-heading">
            <span className="about-eyebrow">04 — CORE CAPABILITIES</span>
            <h2>Designed around classroom needs.</h2>
            <p>
              The platform brings multiple analysis and reporting
              components together in one application.
            </p>
          </div>

          <div className="about-feature-grid">
            {features.map((feature, index) => (
              <article className="about-feature-card" key={feature.title}>
                <div className="about-feature-icon">{feature.icon}</div>
                <span className="about-feature-index">
                  0{index + 1}
                </span>
                <h3>{feature.title}</h3>
                <p>{feature.description}</p>
              </article>
            ))}
          </div>
        </section>

        {/* TECHNOLOGY */}
        <section className="about-section about-tech-section">
          <div className="about-section-heading">
            <span className="about-eyebrow">05 — TECHNOLOGY STACK</span>
            <h2>Built using modern technologies.</h2>
            <p>
              A combination of web development, computer vision and
              machine-learning tools powers the platform.
            </p>
          </div>

          <div className="about-tech-grid">
            {technologies.map((tech) => (
              <article className="about-tech-card" key={tech.name}>
                <span className="about-tech-icon">{tech.icon}</span>
                <div>
                  <h3>{tech.name}</h3>
                  <p>{tech.role}</p>
                </div>
              </article>
            ))}
          </div>

          <div className="about-dataset-row">
            <div>
              <span className="dataset-icon">📚</span>
              <div>
                <h3>FER2013 Dataset</h3>
                <p>Used for facial-expression recognition.</p>
              </div>
            </div>
            <div>
              <span className="dataset-icon">👁️</span>
              <div>
                <h3>MRL Eye Dataset</h3>
                <p>Used for eye-state-related analysis.</p>
              </div>
            </div>
          </div>
        </section>

        {/* FUTURE SCOPE */}
        <section className="about-future-section">
          <div className="future-content">
            <span className="about-eyebrow">06 — FUTURE SCOPE</span>
            <h2>Built with room to grow.</h2>
            <p>
              The project can be extended with additional capabilities
              to improve classroom analysis and reporting.
            </p>

            <div className="future-tags">
              <span>Multi-person tracking</span>
              <span>Improved gaze estimation</span>
              <span>Posture analysis</span>
              <span>Attendance integration</span>
              <span>Historical dashboards</span>
              <span>Downloadable reports</span>
            </div>
          </div>
          <div className="future-art" aria-hidden="true">
            <div className="future-orbit orbit-one" />
            <div className="future-orbit orbit-two" />
            <div className="future-core">✦</div>
            <span className="future-star star-one">✧</span>
            <span className="future-star star-two">✦</span>
          </div>
        </section>

        {/* RESPONSIBLE USE */}
        <section className="about-note-section">
          <span className="note-icon">ⓘ</span>
          <div>
            <h3>Responsible interpretation of AI insights</h3>
            <p>
              Facial expressions and eye-state observations are visual
              indicators; they do not directly prove whether a student
              is learning or mentally engaged. AI-generated engagement
              scores should be treated as approximate supporting
              information, not as definitive judgments.
            </p>
          </div>
        </section>
      </main>

      <footer className="about-footer">
        <button className="about-brand" onClick={() => navigate("/")}>
          <span className="about-brand-mark">C</span>
          <span>Classroom<span>AI</span></span>
        </button>
        <p>Making classroom engagement easier to understand.</p>
        <button className="footer-back-btn" onClick={() => navigate("/")}>
          Back to Home ↑
        </button>
        <small>© {new Date().getFullYear()} ClassroomAI. All rights reserved.</small>
      </footer>
    </div>
  );
}

export default About;
