import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "./context/ThemeProvider";

import Home from "./Home";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Classroom from "./pages/Classroom";
import Analytics from "./pages/Analytics";
import Register from "./pages/Register";
import RecordedVideo from "./pages/RecordedVideo";

function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/register" element={<Register />} />
          <Route path="/classroom" element={<Classroom />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/recorded-video" element={<RecordedVideo />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;