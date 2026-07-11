import { Routes, Route, Navigate } from "react-router-dom";

import Landing from "../pages/Landing";
import LiveLab from "../cabinet/LiveLab";

// Routes grow per phase: /feed, /u/:handle, /messages, /cabinet/* ...
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/cabinet" element={<LiveLab />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
