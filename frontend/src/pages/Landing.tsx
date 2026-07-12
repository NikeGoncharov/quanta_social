import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api/client";
import { useAuth } from "../app/AuthContext";
import { ThemeToggle } from "../app/ThemeToggle";
import { AtomBackground } from "../components/AtomBackground";

type ApiStatus = "checking" | "ok" | "down";

const STATUS_LABEL: Record<ApiStatus, string> = {
  checking: "Checking API…",
  ok: "API online",
  down: "API unreachable",
};

export default function Landing() {
  const [status, setStatus] = useState<ApiStatus>("checking");
  const { me, loading, guest } = useAuth();
  const navigate = useNavigate();
  const [entering, setEntering] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .health()
      .then((h) => alive && setStatus(h.status === "ok" ? "ok" : "down"))
      .catch(() => alive && setStatus("down"));
    return () => {
      alive = false;
    };
  }, []);

  // One click into the live demo: reuse an existing session, else mint a guest, then go. On
  // failure (guest mode off), fall back to the sign-in page.
  async function enterDemo(dest: string) {
    if (entering || loading) return; // wait for /auth/me — never mint a guest over a real session
    if (me) return void navigate(dest);
    setEntering(dest);
    try {
      await guest();
      navigate(dest);
    } catch {
      setEntering(null);
      navigate("/login");
    }
  }

  return (
    <>
      <AtomBackground />

      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden />
          Quanta
        </div>
        <ThemeToggle />
      </header>

      <main className="hero">
        <span className="hero-eyebrow">Martech · built on OpenRTB</span>
        <h1 className="hero-title">
          A social network that makes the ad <span className="grad">auction clear</span>
        </h1>
        <p className="hero-sub">
          Quanta is a playground for growth engineers — a mock social network whose ads
          run on <strong>Quanta Ads</strong>, a real-time engine built on OpenRTB. Launch
          a campaign and watch every bid request, clearing price, and learning phase
          unfold in the open. No more flying by instruments.
        </p>
        <div className="cta-row">
          <button
            className="btn primary lg"
            onClick={() => void enterDemo("/feed")}
            disabled={entering !== null || loading}
          >
            {entering === "/feed" ? "Starting demo…" : "Explore the live demo →"}
          </button>
          <button
            className="btn lg"
            onClick={() => void enterDemo("/cabinet")}
            disabled={entering !== null || loading}
          >
            {entering === "/cabinet" ? "Opening…" : "Open the ad cabinet"}
          </button>
        </div>
        <div className="cta-note muted">
          No sign-up needed — you'll enter as a guest. {" "}
          <Link to="/login">Have an account? Sign in</Link>
        </div>
        <div className="chips">
          <span className="chip">
            <span className="tag">live</span> Real-time delivery
          </span>
          <span className="chip">
            <span className="tag">live</span> RTB inspector
          </span>
          <span className="chip">
            <span className="tag">live</span> Sponsored feed
          </span>
        </div>
        <div className="status-row">
          <span className={`pill ${status}`}>
            <span className="dot" />
            {STATUS_LABEL[status]}
          </span>
        </div>
      </main>
    </>
  );
}
