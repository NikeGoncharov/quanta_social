import { Navigate, Route, Routes } from "react-router-dom";

import CabinetLayout from "../cabinet/CabinetLayout";
import CampaignDetail from "../cabinet/CampaignDetail";
import CampaignsGrid from "../cabinet/CampaignsGrid";
import CreateWizard from "../cabinet/CreateWizard";
import LiveLab from "../cabinet/LiveLab";
import ReportingDashboard from "../cabinet/ReportingDashboard";
import Landing from "../pages/Landing";
import Login from "../pages/Login";
import Register from "../pages/Register";
import FeedView from "../social/FeedView";
import MessagesView from "../social/MessagesView";
import PostView from "../social/PostView";
import ProfileView from "../social/ProfileView";
import SocialLayout from "../social/SocialLayout";

// Three areas: the marketing landing + auth pages (public), the social network (auth-gated,
// under SocialLayout), and the ad cabinet (nested SSE-backed layout).
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      <Route element={<SocialLayout />}>
        <Route path="/feed" element={<FeedView />} />
        <Route path="/u/:handle" element={<ProfileView />} />
        <Route path="/p/:id" element={<PostView />} />
        <Route path="/messages" element={<MessagesView />} />
        <Route path="/messages/:handle" element={<MessagesView />} />
      </Route>

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
