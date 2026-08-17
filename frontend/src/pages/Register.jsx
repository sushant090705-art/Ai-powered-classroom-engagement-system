import { useState } from "react";
import { useNavigate } from "react-router-dom";
import ThemeToggle from "../components/ThemeToggle";
import "./Register.css";

function Register() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

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
       <div className="auth-theme-toggle">
         <ThemeToggle />
       </div>
       <div className="register-card">

        <div className="register-logo">
          ◉
        </div>

        <h1>Create Account</h1>

        <p className="register-subtitle">
          Create your ClassroomAI account
        </p>

        <form onSubmit={handleRegister}>

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
            placeholder="Enter password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />

          <button
  type="submit"
  className="register-submit"
>
  Create Account
</button>

        </form>

        <button
          type="button"
          className="back-login"
          onClick={() => navigate("/login")}
        >
          Already have an account? Login
        </button>

      </div>
    </div>
  );
}

export default Register;