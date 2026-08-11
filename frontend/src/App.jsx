import { useEffect, useState } from "react";

function App() {
  const [message, setMessage] = useState("Connecting to backend...");

  useEffect(() => {
    fetch("http://127.0.0.1:5000/")
      .then((response) => response.text())
      .then((data) => {
        setMessage(data);
      })
      .catch(() => {
        setMessage("Backend connection failed ❌");
      });
  }, []);

  return (
    <div>
      <h1>Classroom Engagement AI</h1>

      <h2>{message}</h2>
    </div>
  );
}

export default App;