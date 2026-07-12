// Delivery split along one audience dimension (interest / geo / age / gender), ranked by
// impressions with an inline share bar.
import { useEffect, useState } from "react";

import { cabinetApi, type BreakdownRow } from "../api/cabinet";
import { count, pct, usd } from "./format";

const DIMS: { key: string; label: string }[] = [
  { key: "interest", label: "Interest" },
  { key: "geo", label: "Geo" },
  { key: "age_band", label: "Age" },
  { key: "gender", label: "Gender" },
];

const REFRESH_MS = 8000;

export function BreakdownExplorer({ campaignId, window = 1440 }: { campaignId?: string; window?: number }) {
  const [dim, setDim] = useState("interest");
  const [rows, setRows] = useState<BreakdownRow[]>([]);

  useEffect(() => {
    let alive = true;
    setRows([]); // clear on scope/dimension change so a fresh campaign never shows another's rows
    const load = () =>
      cabinetApi
        .breakdown(dim, campaignId, window)
        .then((r) => alive && setRows(r.rows))
        .catch(() => {});
    load();
    // Poll so a just-published campaign's breakdown fills in as the world delivers, instead
    // of staying stuck on "No delivery yet." until the user clicks another dimension.
    const id = setInterval(load, REFRESH_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [dim, campaignId, window]);

  const max = Math.max(1, ...rows.map((r) => r.impressions));

  return (
    <div className="card panel">
      <div className="panel-head">
        <div>
          <h3 className="panel-title">Breakdown</h3>
          <p className="panel-sub">Where delivery is landing</p>
        </div>
        <div className="seg">
          {DIMS.map((d) => (
            <button key={d.key} className={`seg-btn ${dim === d.key ? "on" : ""}`} onClick={() => setDim(d.key)}>
              {d.label}
            </button>
          ))}
        </div>
      </div>
      <div className="ctable-scroll">
        <table className="ctable">
          <thead>
            <tr>
              <th>{DIMS.find((d) => d.key === dim)?.label}</th>
              <th className="bd-bar-cell num">Impressions</th>
              <th className="num">Clicks</th>
              <th className="num">CTR</th>
              <th className="num">Spend</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="muted" style={{ textAlign: "center", padding: "20px" }}>
                  No delivery yet.
                </td>
              </tr>
            ) : (
              rows.map((r) => (
                <tr key={r.value}>
                  <td>
                    <span className="mini-chip ghost">{r.value}</span>
                  </td>
                  <td className="bd-bar-cell">
                    <div className="bd-bar">
                      <i style={{ width: `${(r.impressions / max) * 100}%` }} />
                    </div>
                    <div className="tnum" style={{ marginTop: 4, fontSize: "0.8rem" }}>
                      {count(r.impressions)}
                    </div>
                  </td>
                  <td className="num tnum">{count(r.clicks)}</td>
                  <td className="num tnum">{pct(r.ctr, 2)}</td>
                  <td className="num tnum">{usd(r.spend)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
