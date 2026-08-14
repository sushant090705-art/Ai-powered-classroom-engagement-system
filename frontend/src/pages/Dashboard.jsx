import { useNavigate } from "react-router-dom";
import "./Dashboard.css";

function Dashboard() {
  const navigate = useNavigate();

  return (
    <div className="dashboard">

      <header className="dashboard-nav">

        <div className="dashboard-logo">
          ◉ ClassroomAI
        </div>

        <button
          onClick={() => navigate("/")}
          className="logout-btn"
        >
          Logout
        </button>

      </header>

      <main className="dashboard-content">

        <div className="dashboard-heading">
          <div>
            <p>TEACHER DASHBOARD</p>
            <h1>Classroom Overview</h1>
          </div>

          <button className="start-class-btn">
            + Start Classroom
          </button>
        </div>

        <div className="dashboard-stats">

          <div className="dashboard-stat">
            <span>👥</span>
            <div>
              <small>Students</small>
              <strong>32</strong>
            </div>
          </div>

          <div className="dashboard-stat">
            <span>👁️</span>
            <div>
              <small>Attention</small>
              <strong>82%</strong>
            </div>
          </div>

          <div className="dashboard-stat">
            <span>📊</span>
            <div>
              <small>Engagement</small>
              <strong>78%</strong>
            </div>
          </div>

          <div className="dashboard-stat">
            <span>🙋</span>
            <div>
              <small>Participation</small>
              <strong>69%</strong>
            </div>
          </div>

        </div>

        <section className="dashboard-panel">

          <div>
            <small>CLASSROOM</small>
            <h2>No active classroom</h2>
            <p>
              Start a classroom session to begin monitoring
              student engagement.
            </p>
          </div>

          <button className="start-class-btn">
            Start Classroom
          </button>

        </section>

      </main>

    </div>
  );
}

export default Dashboard;