// The social shell: a top bar (Home / Messages / Profile + a link into the ad cabinet) over a
// centered column, with a bottom nav on narrow screens. Gated on auth — an unauthenticated
// visitor is bounced to /login.
import { useEffect } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../app/AuthContext";
import { ThemeToggle } from "../app/ThemeToggle";
import { Avatar } from "./Avatar";

function Icon({ d }: { d: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  );
}

const ICONS = {
  home: "M3 11l9-8 9 8M5 10v10h5v-6h4v6h5V10",
  messages: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
  profile: "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  ads: "M3 12h4l3 8 4-16 3 8h4",
};

export default function SocialLayout() {
  const { me, loading, logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loading && !me) navigate("/login", { replace: true });
  }, [loading, me, navigate]);

  if (loading) return <div className="sn-loading">Loading…</div>;
  if (!me) return null;

  return (
    <div className="sn">
      <header className="sn-top">
        <div className="sn-top-inner">
          <Link to="/feed" className="brand">
            <span className="brand-mark" aria-hidden /> Quanta
          </Link>
          <nav className="sn-nav">
            <NavLink to="/feed" end className="sn-link"><Icon d={ICONS.home} /> Home</NavLink>
            <NavLink to="/messages" className="sn-link"><Icon d={ICONS.messages} /> Messages</NavLink>
            <NavLink to={`/u/${me.handle}`} className="sn-link"><Icon d={ICONS.profile} /> Profile</NavLink>
          </nav>
          <div className="sn-top-right">
            <Link to="/cabinet" className="sn-cabinet"><Icon d={ICONS.ads} /> Ads cabinet</Link>
            <ThemeToggle />
            <button className="sn-logout" onClick={() => void logout()}>Log out</button>
            <Link to={`/u/${me.handle}`} className="sn-me" title={me.display_name}>
              <Avatar seed={me.avatar_seed} name={me.display_name} size={34} />
            </Link>
          </div>
        </div>
      </header>

      <main className="sn-main">
        <Outlet />
      </main>

      <nav className="sn-bottom">
        <NavLink to="/feed" end className="sn-bt"><Icon d={ICONS.home} /><span>Home</span></NavLink>
        <NavLink to="/messages" className="sn-bt"><Icon d={ICONS.messages} /><span>Messages</span></NavLink>
        <NavLink to={`/u/${me.handle}`} className="sn-bt"><Icon d={ICONS.profile} /><span>Profile</span></NavLink>
        <NavLink to="/cabinet" className="sn-bt"><Icon d={ICONS.ads} /><span>Ads</span></NavLink>
      </nav>
    </div>
  );
}
