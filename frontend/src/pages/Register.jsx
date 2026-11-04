
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import ThemeToggle from "../components/ThemeToggle";
import "./Register.css";

function Register() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // Existing backend registration logic preserved
  const handleRegister = async (e) => {
    e.preventDefault();

    try {
      const response = await fetch("http://127.0.0.1:5000/register", {
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
        alert("Account created successfully!");
        navigate("/login");
      } else {
        alert(data.message);
      }
    } catch (error) {
      console.error("Registration error:", error);
      alert("Cannot connect to backend");
    }
  };

  return (
    <div className="register-page">

      <div className="register-theme-toggle">
        <ThemeToggle />
      </div>

      <div className="register-layout">

        {/* LEFT SHOWCASE */}
        <section className="register-showcase">

          <button
            className="register-brand"
            onClick={() => navigate("/")}
          >
            <span className="register-brand-mark">C</span>
            <span>
              Classroom<span>AI</span>
            </span>
          </button>

          <div className="register-showcase-content">

            <span className="register-eyebrow">
              GET STARTED WITH CLASSROOMAI
            </span>

            <h1>
              A clearer view of
              <span> classroom engagement.</span>
            </h1>

            <p>
              Create your teacher account and access an organized
              platform for understanding classroom attention,
              emotion patterns and engagement insights.
            </p>

            <div className="register-benefits">

              <div className="register-benefit">
                <span>01</span>
                <div>
                  <strong>Simple Access</strong>
                  <small>Your classroom tools in one place.</small>
                </div>
              </div>

              <div className="register-benefit">
                <span>02</span>
                <div>
                  <strong>AI-Powered Insights</strong>
                  <small>Understand classroom engagement patterns.</small>
                </div>
              </div>

              <div className="register-benefit">
                <span>03</span>
                <div>
                  <strong>Organized Reports</strong>
                  <small>Review classroom session information.</small>
                </div>
              </div>

            </div>
          </div>

          <div className="register-showcase-footer">
            ClassroomAI · Intelligent classroom insights
          </div>

        </section>

        {/* RIGHT REGISTRATION FORM */}
        <section className="register-form-section">

          <div className="register-card">

            <div className="register-logo">+</div>

            <span className="register-form-eyebrow">
              TEACHER REGISTRATION
            </span>

            <h2>Create your account</h2>

            <p className="register-subtitle">
              Enter your details to get started.
            </p>

            <form onSubmit={handleRegister}>

              <label htmlFor="register-email">
                Email address
              </label>

              <input
                id="register-email"
                type="email"
                placeholder="teacher@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
              />

              <label htmlFor="register-password">
                Password
              </label>

              <input
                id="register-password"
                type="password"
                placeholder="Create your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                required
              />

              <button type="submit" className="register-submit">
                Create Account
                <span>→</span>
              </button>

            </form>

            <div className="register-divider">
              ALREADY HAVE AN ACCOUNT?
            </div>

            <button
              type="button"
              className="register-login"
              onClick={() => navigate("/login")}
            >
              Sign In Instead
            </button>

            <button
              type="button"
              className="register-home"
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

export default Register;
