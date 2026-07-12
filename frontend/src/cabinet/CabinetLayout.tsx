// The cabinet shell: a left sidebar (Live / Campaigns / Reporting + New) that collapses to a
// bottom nav on narrow screens, wrapping every cabinet page in one SSE-backed SimProvider.
import { Link, NavLink, Outlet } from "react-router-dom";

import { ThemeToggle } from "../app/ThemeToggle";
import { SimProvider, useSim } from "../hooks/SimContext";

function Icon({ d }: { d: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  );
}

const ICONS = {
  live: "M3 12h4l3 8 4-16 3 8h4",
  grid: "M4 5h16M4 12h16M4 19h16",
  report: "M4 20V10M10 20V4M16 20v-8M22 20H2",
  plus: "M12 5v14M5 12h14",
};

function LivePill() {
  const { connected, status } = useSim();
  const active = status?.active;
  return (
    <span className={`pill ${connected ? (active ? "ok" : "checking") : "checking"}`}>
      <span className="dot" />
      {connected ? (active ? "live" : "idle") : "connecting…"}
    </span>
  );
}

export default function CabinetLayout() {
  return (
    <SimProvider>
      <div className="cab">
        <aside className="cab-nav">
          <Link to="/" className="brand">
            <span className="brand-mark" aria-hidden />
            Quanta Ads
          </Link>
          <NavLink to="/cabinet" end className="nav-link">
            <Icon d={ICONS.live} /> Live
          </NavLink>
          <NavLink to="/cabinet/campaigns" className="nav-link">
            <Icon d={ICONS.grid} /> Campaigns
          </NavLink>
          <NavLink to="/cabinet/reporting" className="nav-link">
            <Icon d={ICONS.report} /> Reporting
          </NavLink>
          <NavLink to="/cabinet/campaigns/new" className="nav-link cta">
            <Icon d={ICONS.plus} /> New campaign
          </NavLink>
          <div className="cab-nav-foot">
            <LivePill />
            <ThemeToggle />
          </div>
        </aside>
        <main className="cab-main">
          <Outlet />
        </main>
      </div>
    </SimProvider>
  );
}
