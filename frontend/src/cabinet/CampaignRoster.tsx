import type { LineStatus, SimStatus } from "../api/sim";

const OBJ_LABEL: Record<LineStatus["objective"], string> = {
  awareness: "Awareness",
  traffic: "Traffic",
  engagement: "Engagement",
  conversions: "Conversions",
};

function LineCard({ line }: { line: LineStatus }) {
  const util = line.budget_util ?? 0;
  const capped = util >= 0.98;
  return (
    <div className="line-card">
      <div className="line-top">
        <span className="line-brand">{line.brand}</span>
        <span className="line-chips">
          <span className="mini-chip">{OBJ_LABEL[line.objective]}</span>
          {line.funnel_stage && <span className="mini-chip ghost">{line.funnel_stage}</span>}
          <span className="mini-chip ghost">{line.pacing}</span>
        </span>
      </div>

      <div className="budget">
        <div className="budget-bar">
          <span
            className={`budget-fill ${capped ? "capped" : ""}`}
            style={{ width: `${Math.min(100, util * 100)}%` }}
          />
        </div>
        <div className="budget-nums tnum">
          <span>${line.spent_today.toFixed(2)}</span>
          <span className="muted">/ ${line.daily_budget.toFixed(0)}/day</span>
          {capped && <span className="tag-bad">budget-capped</span>}
        </div>
      </div>

      {line.in_learning != null && (
        <div className={`learn ${line.in_learning ? "on" : "done"}`}>
          {line.in_learning ? (
            <>
              <span className="spinner-dot" /> Learning · ~{Math.ceil(line.signal_to_exit ?? 0)} more
              conversions to exit
            </>
          ) : (
            <>✓ Exited learning — optimization stable</>
          )}
        </div>
      )}
    </div>
  );
}

export function CampaignRoster({ status }: { status: SimStatus | null }) {
  const lines = status?.lines ?? [];
  return (
    <div className="card panel roster">
      <div className="panel-head">
        <div>
          <h3 className="panel-title">Campaigns on air</h3>
          <p className="panel-sub">Seed roster · budgets reset each sim-day</p>
        </div>
      </div>
      <div className="line-list">
        {lines.map((l) => (
          <LineCard key={l.ad_id} line={l} />
        ))}
      </div>
    </div>
  );
}
