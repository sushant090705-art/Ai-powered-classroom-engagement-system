
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import ThemeToggle from "../components/ThemeToggle";
import "./Login.css";

function Login() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // Existing backend login logic - unchanged
  const handleLogin = async (e) => {
    e.preventDefault();

    try {
      const response = await fetch("http://127.0.0.1:5000/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: email,
          password: password,
        }),
      });

      const data = await response.json();

      if (data.success) {
        navigate("/dashboard");
      } else {
        alert(data.message);
      }
    } catch (error) {
      console.error("Login error:", error);
      alert("Cannot connect to backend");
    }
  };

  return (
    <div className="login-page">

      <div className="login-theme-toggle">
        <ThemeToggle />
      </div>

      <div className="login-layout">

        {/* LEFT SIDE */}
        <section className="login-showcase">

          <button
            className="login-brand"
            onClick={() => navigate("/")}
          >
            <span className="login-brand-mark">C</span>
            <span>
              Classroom<span>AI</span>
            </span>
          </button>

          <div className="login-showcase-content">

            <span className="login-eyebrow">
              AI-POWERED CLASSROOM INTELLIGENCE
            </span>

            <h1>
              Understand your
              <span> classroom.</span>
              <br />
              Empower better
              <span> learning.</span>
            </h1>

            <p>
              Access your classroom engagement dashboard.
              Monitor attention, understand emotion patterns
              and review meaningful classroom insights.
            </p>

            <div className="login-benefits">

              <div className="login-benefit">
                <span>01</span>
                <div>
                  <strong>Attention Monitoring</strong>
                  <small>Understand classroom focus patterns.</small>
                </div>
              </div>

              <div className="login-benefit">
                <span>02</span>
                <div>
                  <strong>Emotion Analysis</strong>
                  <small>Review facial emotion patterns.</small>
                </div>
              </div>

              <div className="login-benefit">
                <span>03</span>
                <div>
                  <strong>Engagement Reports</strong>
                  <small>Explore classroom performance insights.</small>
                </div>
              </div>

            </div>
          </div>

          <div className="login-showcase-footer">
            ClassroomAI · Intelligent classroom insights
          </div>

        </section>

        {/* RIGHT SIDE */}
        <section className="login-form-section">

          <div className="login-card">

            <div className="login-form-icon">↗</div>

            <span className="login-form-eyebrow">
              TEACHER PORTAL
            </span>

            <h2>Welcome back</h2>

            <p className="login-subtitle">
              Sign in to continue to your dashboard.
            </p>

            <form onSubmit={handleLogin}>

              <label htmlFor="login-email">
                Email address
              </label>

              <input
                id="login-email"
                type="email"
                placeholder="teacher@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
              />

              <label htmlFor="login-password">
                Password
              </label>

              <input
                id="login-password"
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />

              <button type="submit" className="login-submit">
                Sign In
                <span>→</span>
              </button>

            </form>

            <div className="login-register-divider">
              <span>NEW TO CLASSROOMAI?</span>
            </div>

            <button
              type="button"
              className="create-account"
              onClick={() => navigate("/register")}
            >
              Create an Account
            </button>

            <button
              type="button"
              className="back-home"
              onClick={() => navigate("/")}
            >
              ← Back to Home
            </button>

          </div>

        </section>

      </div>
    </div>
  );
}

export default Login;
