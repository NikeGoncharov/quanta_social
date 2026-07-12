import { Navigate, Route, Routes } from "react-router-dom";

import CabinetLayout from "../cabinet/CabinetLayout";
import CampaignDetail from "../cabinet/CampaignDetail";
import CampaignsGrid from "../cabinet/CampaignsGrid";
import CreateWizard from "../cabinet/CreateWizard";
import LiveLab from "../cabinet/LiveLab";
import ReportingDashboard from "../cabinet/ReportingDashboard";
import Landing from "../pages/Landing";

// The cabinet is a nested layout: /cabinet renders the shell (sidebar + SSE provider) with
// the active page in its outlet.
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/cabinet" element={<CabinetLayout />}>
        <Route index element={<LiveLab />} />
        <Route path="campaigns" element={<CampaignsGrid />} />
        <Route path="campaigns/new" element={<CreateWizard />} />
        <Route path="campaigns/:id" element={<CampaignDetail />} />
        <Route path="reporting" element={<ReportingDashboard />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
