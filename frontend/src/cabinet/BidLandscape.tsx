// Win rate + projected results across a sweep of bids around the current one — the explicit
// "raise the bid to win more" lesson. The current bid's row is highlighted.
import type { BidLandscape as BidLandscapeData } from "../api/cabinet";
import { compact, usd } from "./format";

export function BidLandscape({ data }: { data: BidLandscapeData | null }) {
  if (!data) {
    return (
      <div className="card panel">
        <div className="panel-head">
          <h3 className="panel-title">Bid landscape</h3>
        </div>
        <p className="muted">Available while the campaign is on air.</p>
      </div>
    );
  }
  return (
    <div className="card panel">
      <div className="panel-head">
        <div>
          <h3 className="panel-title">Bid landscape</h3>
          <p className="panel-sub">
            Win rate &amp; est. {data.result_label}/day across {data.bid_label.toLowerCase()}s
          </p>
        </div>
      </div>
      <div className="land">
        {data.points.map((p) => (
          <div className={`land-row ${p.is_current ? "cur" : ""}`} key={p.multiplier}>
            <span className="land-bid">{usd(p.bid)}</span>
            <span className="land-bar">
              <i style={{ width: `${Math.min(100, p.win_rate * 100)}%` }} />
            </span>
            <span className="land-meta">
              {Math.round(p.win_rate * 100)}% · <b>{compact(p.est_results)}</b> {data.result_label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
