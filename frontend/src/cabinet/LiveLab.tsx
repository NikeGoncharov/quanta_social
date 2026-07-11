import { Link } from "react-router-dom";

import { ThemeToggle } from "../app/ThemeToggle";
import { useSimStream } from "../hooks/useSimStream";
import { CampaignRoster } from "./CampaignRoster";
import { DeliveryChart } from "./DeliveryChart";
import { RtbInspector } from "./RtbInspector";
import { SimControls } from "./SimControls";

export default function LiveLab() {
  const { status, points, connected } = useSimStream();

  return (
    <div className="lab">
      <header className="lab-top">
        <Link to="/" className="brand">
          <span className="brand-mark" aria-hidden />
          Quanta Ads
        </Link>
        <div className="lab-top-right">
          <span className={`pill ${connected ? "ok" : "checking"}`}>
            <span className="dot" />
            {connected ? "live" : "connecting…"}
          </span>
          <ThemeToggle />
        </div>
      </header>

      <div className="lab-intro">
        <h1 className="lab-title">The glass-box, live</h1>
        <p className="lab-sub">
          A real-time OpenRTB world runs behind Quanta. Steer the clock and market density,
          watch delivery respond, and open any auction down to its bid request.
        </p>
      </div>

      <div className="lab-grid">
        <main className="lab-main">
          <SimControls status={status} />
          <DeliveryChart points={points} />
          <RtbInspector />
        </main>
        <aside className="lab-side">
          <CampaignRoster status={status} />
        </aside>
      </div>
    </div>
  );
}
