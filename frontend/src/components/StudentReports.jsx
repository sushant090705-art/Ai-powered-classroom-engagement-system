import { useEffect, useState } from "react";
import StudentReportCard from "./StudentReportCard";
import { formatDuration } from "../utils/formatDuration";
import "./StudentReports.css";

const POLL_MS = 1000;

function LiveReports({ backendUrl }) {
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [refreshTick, setRefreshTick] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const response = await fetch(`${backendUrl}/students/report`);

        if (!response.ok) {
          throw new Error(`Server error: ${response.status}`);
        }

        const data = await response.json();

        if (!cancelled && data.success) {
          setReport(data);
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          console.error("Student report error:", err);
          setError("Cannot load student reports from the backend.");
        }
      }
    };

    load();
    const interval = setInterval(load, POLL_MS);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [backendUrl, refreshTick]);

  const renameStudent = async (studentId, name) => {
    try {
      const response = await fetch(
        `${backendUrl}/students/${studentId}/rename`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name }),
        }
      );
      if (response.ok) setRefreshTick((n) => n + 1);
    } catch (err) {
      console.error("Rename error:", err);
    }
  };

  if (error && !report) {
    return <div className="sr-empty">⚠️ {error}</div>;
  }

  if (!report) {
    return <div className="sr-empty">Loading student reports…</div>;
  }

  return (
    <>
      <div className="sr-summary">
        <div>
          <small>Students seen</small>
          <strong>{report.students_total}</strong>
        </div>
        <div>
          <small>Class engagement</small>
          <strong>{report.class_average_engagement}%</strong>
        </div>
        <div>
          <small>Session time</small>
          <strong>{formatDuration(report.session_seconds)}</strong>
        </div>
      </div>

      {error && <div className="sr-empty">⚠️ {error}</div>}

      {report.students.length === 0 ? (
        <div className="sr-empty">
          No students detected yet. Reports appear as soon as someone is in
          view of the camera.
        </div>
      ) : (
        <div className="sr-grid">
          {report.students.map((student) => (
            <StudentReportCard
              key={student.student_id}
              student={student}
              onRename={(name) => renameStudent(student.student_id, name)}
            />
          ))}
        </div>
      )}
    </>
  );
}

function StudentReports({ backendUrl, active }) {
  return (
    <section className="emotion-card student-reports">
      <div>
        <small>STUDENT REPORTS</small>
        <h2>Individual Student Reports</h2>
        <p>
          Emotions, attention, eye status and engagement for every student
          detected in this session.
        </p>
      </div>

      {active ? (
        <LiveReports backendUrl={backendUrl} />
      ) : (
        <div className="sr-empty">
          Start the classroom camera to see individual student reports.
        </div>
      )}
    </section>
  );
}

export default StudentReports;
