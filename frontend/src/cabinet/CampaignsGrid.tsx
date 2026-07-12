// The campaigns grid: DB source-of-truth (name / status / budget / bid) paired with live
// delivery for on-air campaigns. Budget and bid are inline-editable; the status toggle
// pauses/resumes. Every edit is an optimistic PATCH that re-fetches to reconcile.
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../api/client";
import { cabinetApi, type CampaignPatch, type GridRow } from "../api/cabinet";
import { count, OBJ_LABEL, pct, usd } from "./format";

const REFRESH_MS = 6000;

function InlineNumber({
  value,
  prefix,
  onCommit,
}: {
  value: number;
  prefix?: string;
  onCommit: (v: number) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(String(value));

  const start = () => {
    setDraft(String(value));
    setEditing(true);
  };
  const commit = () => {
    setEditing(false);
    const v = parseFloat(draft);
    if (!Number.isNaN(v) && v > 0 && v !== value) onCommit(v);
  };
  if (!editing) {
    return (
      <button className="cell-btn tnum" onClick={start} title="Click to edit">
        {prefix}
        {value.toLocaleString("en-US", { maximumFractionDigits: 2 })}
      </button>
    );
  }
  return (
    <span className="cell-edit">
      <input
        autoFocus
        value={draft}
        inputMode="decimal"
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") commit();
          if (e.key === "Escape") setEditing(false);
        }}
      />
    </span>
  );
}

export default function CampaignsGrid() {
  const [rows, setRows] = useState<GridRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const alive = useRef(true);

  const load = useCallback(async () => {
    try {
      const r = await cabinetApi.grid();
      if (alive.current) setRows(r.rows);
    } catch (e) {
      if (alive.current) setError(e instanceof ApiError ? e.message : "Failed to load campaigns");
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => {
      alive.current = false;
      clearInterval(id);
    };
  }, [load]);

  const patch = async (id: string, body: CampaignPatch, optimistic: (r: GridRow) => GridRow) => {
    setError(null);
    setRows((rs) => rs?.map((r) => (r.campaign_id === id ? optimistic(r) : r)) ?? rs);
    try {
      await cabinetApi.patch(id, body);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Edit failed");
    } finally {
      load(); // reconcile with the server (and pick up live metrics)
    }
  };

  const toggleStatus = (r: GridRow) => {
    const next = r.status === "active" ? "paused" : "active";
    patch(r.campaign_id, { status: next }, (row) => ({ ...row, status: next }));
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Campaigns</h1>
          <p className="page-sub">
            Live delivery meets the controls that shape it. Click a budget or bid to edit;
            flip the switch to pause.
          </p>
        </div>
        <Link to="/cabinet/campaigns/new" className="btn primary">
          + New campaign
        </Link>
      </div>

      {error && <div className="err-line">{error}</div>}

      <div className="card panel">
        {rows && rows.length === 0 ? (
          <div className="empty-state">
            <h3>No campaigns yet</h3>
            <p>Create your first campaign and watch it enter the live auction.</p>
            <Link to="/cabinet/campaigns/new" className="btn primary" style={{ marginTop: 12 }}>
              + New campaign
            </Link>
          </div>
        ) : (
          <div className="ctable-scroll">
            <table className="ctable">
              <thead>
                <tr>
                  <th>Campaign</th>
                  <th>Objective</th>
                  <th>Status</th>
                  <th className="num">Daily budget</th>
                  <th className="num">Bid</th>
                  <th className="num">Spent today</th>
                  <th className="num">Impressions</th>
                  <th className="num">Results</th>
                  <th className="num">Cost / result</th>
                  <th>Win rate</th>
                </tr>
              </thead>
              <tbody>
                {(rows ?? []).map((r) => {
                  const live = r.live;
                  return (
                    <tr key={r.campaign_id}>
                      <td>
                        <div className="row-camp">
                          <Link to={`/cabinet/campaigns/${r.campaign_id}`} className="linky">
                            {r.name}
                          </Link>
                          <span className="row-name">{r.brand || r.account_id}</span>
                        </div>
                      </td>
                      <td>
                        <div className="row-chips">
                          <span className="mini-chip">{OBJ_LABEL[r.objective]}</span>
                          {r.funnel_stage && <span className="mini-chip ghost">{r.funnel_stage}</span>}
                          {r.pacing === "asap" && <span className="mini-chip ghost">ASAP</span>}
                        </div>
                      </td>
                      <td>
                        <span
                          className="row-toggle"
                          role="switch"
                          aria-checked={r.status === "active"}
                          tabIndex={0}
                          onClick={() => toggleStatus(r)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault(); // Space would otherwise scroll the page
                              toggleStatus(r);
                            }
                          }}
                          title={r.status === "active" ? "Pause" : "Activate"}
                        >
                          <span className={`switch ${r.status === "active" ? "on" : ""}`} />
                          &nbsp;<span className={`st-chip ${r.status}`}>{r.status}</span>
                        </span>
                      </td>
                      <td className="num editable">
                        <InlineNumber
                          value={r.daily_budget}
                          prefix="$"
                          onCommit={(v) =>
                            patch(r.campaign_id, { daily_budget_usd: v }, (row) => ({ ...row, daily_budget: v }))
                          }
                        />
                      </td>
                      <td className="num editable">
                        <InlineNumber
                          value={r.bid}
                          prefix="$"
                          onCommit={(v) => patch(r.campaign_id, { bid_usd: v }, (row) => ({ ...row, bid: v }))}
                        />
                      </td>
                      <td className="num tnum">{live ? usd(live.spent_today) : "—"}</td>
                      <td className="num tnum">{live ? count(live.impressions_today) : "—"}</td>
                      <td className="num tnum">
                        {live ? `${count(live.results)} ${live.result_label}` : "—"}
                      </td>
                      <td className="num tnum">{live ? usd(live.cost_per_result) : "—"}</td>
                      <td>
                        {live ? (
                          <div className="wr">
                            <span className="wr-bar">
                              <i style={{ width: `${Math.min(100, live.market.win_rate * 100)}%` }} />
                            </span>
                            <span className="tnum">{pct(live.market.win_rate, 0)}</span>
                          </div>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
