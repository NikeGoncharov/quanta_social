// The reporting page: pick a campaign (or all) and a window, see KPIs with deltas, the
// delivery timeseries, and the audience breakdown. Reads straight from the delivery buckets.
import { useEffect, useState } from "react";

import { cabinetApi, type GridRow, type KpiReport } from "../api/cabinet";
import { BreakdownExplorer } from "./BreakdownExplorer";
import { ReportKpis } from "./ReportKpis";
import { TimeseriesChart } from "./TimeseriesChart";

const WINDOWS = [
  { key: "1d", mins: 1440 },
  { key: "3d", mins: 4320 },
  { key: "7d", mins: 10080 },
];

export default function ReportingDashboard() {
  const [rows, setRows] = useState<GridRow[]>([]);
  const [campaignId, setCampaignId] = useState("");
  const [windowKey, setWindowKey] = useState("1d");
  const [report, setReport] = useState<KpiReport | null>(null);
  const win = WINDOWS.find((w) => w.key === windowKey)!.mins;
  const scope = campaignId || undefined;

  useEffect(() => {
    cabinetApi.grid().then((r) => setRows(r.rows)).catch(() => {});
  }, []);

  useEffect(() => {
    let alive = true;
    setReport(null);
    cabinetApi.kpis(scope, win).then((r) => alive && setReport(r)).catch(() => {});
    return () => {
      alive = false;
    };
  }, [scope, win]);

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Reporting</h1>
          <p className="page-sub">Window-over-window KPIs, delivery over time, and where it lands.</p>
        </div>
        <div className="grid-actions">
          <select
            className="select"
            style={{ width: "auto" }}
            value={campaignId}
            onChange={(e) => setCampaignId(e.target.value)}
          >
            <option value="">All campaigns</option>
            {rows.map((r) => (
              <option key={r.campaign_id} value={r.campaign_id}>
                {r.name}
              </option>
            ))}
          </select>
          <div className="seg">
            {WINDOWS.map((w) => (
              <button key={w.key} className={`seg-btn ${w.key === windowKey ? "on" : ""}`} onClick={() => setWindowKey(w.key)}>
                {w.key}
              </button>
            ))}
          </div>
        </div>
      </div>

      <ReportKpis report={report} />
      <TimeseriesChart campaignId={scope} />
      <BreakdownExplorer campaignId={scope} window={win} />
    </div>
  );
}
