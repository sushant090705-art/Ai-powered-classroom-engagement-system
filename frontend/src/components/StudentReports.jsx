
import { useEffect, useState } from "react";
import StudentReportCard from "./StudentReportCard";

const BACKEND_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:5000"
).replace(/\/$/, "");

function StudentReports({ onRename = () => {} }) {
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    const fetchReports = async () => {
      try {
        const response = await fetch(`${BACKEND_URL}/students/report`);

        if (!response.ok) {
          throw new Error("Unable to load student reports");
        }

        const data = await response.json();

        if (active) {
          setStudents(Array.isArray(data.students) ? data.students : []);
          setError("");
          setLoading(false);
        }
      } catch (err) {
        if (active) {
          setError(err.message);
          setLoading(false);
        }
      }
    };

    fetchReports();
    const interval = setInterval(fetchReports, 2000);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  if (loading) {
    return <p>Loading student reports...</p>;
  }

  if (error && students.length === 0) {
    return <p style={{ color: "#ef4444" }}>{error}</p>;
  }

  if (students.length === 0) {
    return <p>No student reports available yet.</p>;
  }

  return (
    <div className="student-reports-grid">
      {students.map((student) => (
        <StudentReportCard
          key={student.student_id}
          student={student}
          backendUrl={BACKEND_URL}
          onRename={onRename}
        />
      ))}
    </div>
  );
}

export default StudentReports;
