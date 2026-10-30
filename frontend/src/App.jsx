import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "./context/ThemeContext";

import Home from "./home";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Classroom from "./pages/Classroom";
import Analytics from "./pages/Analytics";
import Register from "./pages/Register";
import RecordedVideo from "./pages/RecordedVideo";
import Alerts from "./pages/Alerts";


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
          <Route path="/alerts" element={<Alerts />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;