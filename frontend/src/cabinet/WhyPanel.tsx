// The plain-language "why" for a campaign: the single binding limiter + the signals behind it.
import type { Diagnosis } from "../api/cabinet";
import { pct } from "./format";

const TONE: Record<string, "good" | "warn" | "bad"> = {
  audience: "bad",
  budget: "warn",
  frequency: "warn",
  bid: "bad",
  learning: "warn",
};
const ICON: Record<string, string> = {
  audience: "👥",
  budget: "💰",
  frequency: "🔁",
  bid: "⚖️",
  learning: "🎯",
};

export function WhyPanel({ why }: { why: Diagnosis | null }) {
  if (!why) {
    return (
      <div className="card panel">
        <div className="panel-head">
          <h3 className="panel-title">Why it's delivering this way</h3>
        </div>
        <p className="muted">Loading diagnosis…</p>
      </div>
    );
  }
  const tone = why.limiter ? TONE[why.limiter] : why.delivering ? "good" : "warn";
  const icon = why.limiter ? ICON[why.limiter] : "✓";
  return (
    <div className="card panel">
      <div className="panel-head">
        <h3 className="panel-title">Why it's delivering this way</h3>
      </div>
      <div className={`why ${tone}`}>
        <div className="why-ico">{icon}</div>
        <div>
          <div className="why-head">{why.headline}</div>
          <div className="why-detail">{why.detail}</div>
        </div>
      </div>
      <div className="why-signals">
        <div className="why-sig">
          <b>{pct(why.win_rate, 0)}</b>
          <span>Win rate</span>
        </div>
        <div className="why-sig">
          <b>{why.audience.toLocaleString("en-US")}</b>
          <span>Audience</span>
        </div>
        <div className="why-sig">
          <b>{why.budget_util == null ? "—" : pct(why.budget_util, 0)}</b>
          <span>Budget used today</span>
        </div>
      </div>
    </div>
  );
}
