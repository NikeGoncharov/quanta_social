import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
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
          <Link to="/cabinet" className="btn primary lg">
            Open the live lab →
          </Link>
        </div>
        <div className="chips">
          <span className="chip">
            <span className="tag">live</span> Real-time delivery
          </span>
          <span className="chip">
            <span className="tag">live</span> RTB inspector
          </span>
          <span className="chip">
            <span className="tag">soon</span> News feed
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
