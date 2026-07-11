import { Link } from "react-router-dom";

import { ThemeToggle } from "../app/ThemeToggle";
import { useSimStream } from "../hooks/useSimStream";
import { CampaignTable } from "./CampaignTable";
import { DeliveryChart } from "./DeliveryChart";
import { KpiTiles } from "./KpiTiles";
import { MarketPulse } from "./MarketPulse";
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

      <div className="lab-head">
        <div className="lab-intro">
          <h1 className="lab-title">The glass-box, live</h1>
          <p className="lab-sub">
            A real-time OpenRTB world runs behind Quanta. Steer the clock and market
            density, watch delivery respond, and open any auction down to its bid request.
          </p>
        </div>
        <SimControls status={status} />
      </div>

      <KpiTiles points={points} simTime={status?.sim_time ?? null} />

      <div className="dash-row">
        <DeliveryChart points={points} />
        <MarketPulse status={status} />
      </div>

      <CampaignTable status={status} />
      <RtbInspector />
    </div>
  );
}
