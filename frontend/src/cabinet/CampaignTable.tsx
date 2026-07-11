// Campaigns on air — the full-width dashboard table. Every row pairs realized delivery
// (today's funnel, CTR, avg CPM, cost per result) with the live market position (our bid
// vs the niche average, est. win rate) so a limiter is visible at a glance.
import type { LineStatus, SimStatus } from "../api/sim";

const OBJ_LABEL: Record<LineStatus["objective"], string> = {
  awareness: "Awareness",
  traffic: "Traffic",
  engagement: "Engagement",
  conversions: "Conversions",
};

const usd = (n: number) => `$${n.toFixed(2)}`;
const count = (v: number) =>
  v >= 10_000 ? `${(v / 1000).toFixed(1)}k` : v.toLocaleString("en-US");

function StatusCell({ line }: { line: LineStatus }) {
  const capped = (line.budget_util ?? 0) >= 0.98;
  if (capped) return <span className="row-status bad">Budget-capped</span>;
  if (line.in_learning) {
    return (
      <span className="row-status warn">
        <span className="spinner-dot" />
        Learning · {Math.ceil(line.signal_to_exit ?? 0)} to go
      </span>
    );
  }
  if (line.in_learning === false) return <span className="row-status good">✓ Optimized</span>;
  return <span className="row-status good">● Delivering</span>;
}

function BidVsNiche({ line }: { line: LineStatus }) {
  const { our_bid, niche_bid } = line.market;
  if (!niche_bid) return <span className="muted">—</span>;
  const diff = (our_bid / niche_bid - 1) * 100;
  const above = diff >= 0;
  return (
    <div className="bidcell">
      <span className="tnum">
        {usd(our_bid)} <em className="muted">vs {usd(niche_bid)}</em>
      </span>
      <span className={`bid-badge ${above ? "above" : "below"}`}>
        {above ? "▲" : "▼"} {Math.abs(diff).toFixed(0)}%
      </span>
    </div>
  );
}

function WinRate({ wr }: { wr: number }) {
  return (
    <div className="wr">
      <span className="wr-bar">
        <i style={{ width: `${Math.min(100, wr * 100)}%` }} />
      </span>
      <span className="tnum">{(wr * 100).toFixed(0)}%</span>
    </div>
  );
}

function Row({ line }: { line: LineStatus }) {
  const util = Math.min(1, line.budget_util ?? 0);
  const capped = (line.budget_util ?? 0) >= 0.98;
  return (
    <tr>
      <td>
        <div className="row-camp">
          <span className="row-brand">{line.brand}</span>
          <span className="row-name">{line.name}</span>
        </div>
      </td>
      <td>
        <div className="row-chips">
          <span className="mini-chip">{OBJ_LABEL[line.objective]}</span>
          {line.funnel_stage && <span className="mini-chip ghost">{line.funnel_stage}</span>}
          {line.pacing === "asap" && <span className="mini-chip ghost">ASAP</span>}
        </div>
      </td>
      <td><StatusCell line={line} /></td>
      <td className="col-budget">
        <div className="budget-bar">
          <span className={`budget-fill ${capped ? "capped" : ""}`} style={{ width: `${util * 100}%` }} />
        </div>
        <div className="budget-nums tnum">
          <span>{usd(line.spent_today)}</span>
          <span className="muted">/ ${line.daily_budget.toFixed(0)}</span>
        </div>
      </td>
      <td className="tnum num">{count(line.impressions_today)}</td>
      <td className="tnum num">{count(line.clicks_today)}</td>
      <td className="tnum num">{line.ctr == null ? "—" : `${(line.ctr * 100).toFixed(2)}%`}</td>
      <td className="tnum num">{line.avg_cpm == null ? "—" : usd(line.avg_cpm)}</td>
      <td>
        <div className="result-cell">
          <span className="tnum result-num">{count(line.results)}</span>
          <span className="result-label">{line.result_label}</span>
        </div>
      </td>
      <td>
        <div className="result-cell">
          <span className="tnum result-num">
            {line.cost_per_result == null ? "—" : usd(line.cost_per_result)}
          </span>
          <span className="result-label">{line.cost_label}</span>
        </div>
      </td>
      <td><BidVsNiche line={line} /></td>
      <td><WinRate wr={line.market.win_rate} /></td>
    </tr>
  );
}

export function CampaignTable({ status }: { status: SimStatus | null }) {
  const lines = status?.lines ?? [];
  return (
    <div className="card panel ctable-card">
      <div className="panel-head">
        <div>
          <h3 className="panel-title">Campaigns on air</h3>
          <p className="panel-sub">
            Today's delivery + live market position · budgets reset each sim-day
          </p>
        </div>
      </div>
      <div className="ctable-scroll">
        <table className="ctable">
          <thead>
            <tr>
              <th>Campaign</th>
              <th>Objective</th>
              <th>Status</th>
              <th>Budget today</th>
              <th className="num">Impressions</th>
              <th className="num">Clicks</th>
              <th className="num">CTR</th>
              <th className="num">Avg CPM</th>
              <th>Results</th>
              <th>Cost / result</th>
              <th>Bid vs niche</th>
              <th>Est. win rate</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((l) => (
              <Row key={l.ad_id} line={l} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
