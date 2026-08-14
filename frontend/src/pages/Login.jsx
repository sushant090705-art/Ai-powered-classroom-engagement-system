import { useState } from "react";
import { useNavigate } from "react-router-dom";
import "./Login.css";

function Login() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleLogin = (e) => {
    e.preventDefault();

    // Temporary frontend login
    // We will connect MongoDB/backend later.
    if (email && password) {
      navigate("/dashboard");
    }
  };

  return (
    <div className="login-page">

      <div className="login-card">

        <div className="login-logo">
          ◉
        </div>

        <h1>Welcome Back</h1>

        <p className="login-subtitle">
          Sign in to your ClassroomAI dashboard
        </p>

        <form onSubmit={handleLogin}>

          <label>Email</label>

          <input
            type="email"
            placeholder="teacher@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />

          <label>Password</label>

          <input
            type="password"
            placeholder="Enter your password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />

          <button type="submit" className="login-submit">
            Sign In
          </button>

        </form>

        <button
          className="back-home"
          onClick={() => navigate("/")}
        >
          ← Back to Home
        </button>

      </div>

    </div>
  );
}

export default Login;