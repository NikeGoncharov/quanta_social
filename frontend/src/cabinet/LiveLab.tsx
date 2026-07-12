// The "Live" tab: the glass-box dashboard. Chrome (brand, theme, live pill) now lives in the
// cabinet shell; this page consumes the shared SSE stream via the SimContext.
import { useSim } from "../hooks/SimContext";
import { CampaignTable } from "./CampaignTable";
import { DeliveryHistory } from "./DeliveryChart";
import { KpiTiles } from "./KpiTiles";
import { MarketPulse } from "./MarketPulse";
import { RtbInspector } from "./RtbInspector";
import { SimControls } from "./SimControls";

export default function LiveLab() {
  const { status, points } = useSim();

  return (
    <div className="lab">
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
        <DeliveryHistory />
        <MarketPulse status={status} />
      </div>

      <CampaignTable status={status} />
      <RtbInspector />
    </div>
  );
}
