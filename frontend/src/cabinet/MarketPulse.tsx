// Market pulse — the live competitive picture: the average competitor bid across all
// niches right now, the density knob that drives it, and per-campaign "our bid vs the
// niche" bars. Turn density up and watch every signal on the dashboard move.
import { useEffect, useState } from "react";

import type { SimStatus } from "../api/sim";
import { simApi } from "../api/sim";

const usd = (n: number) => `$${n.toFixed(2)}`;

export function MarketPulse({ status }: { status: SimStatus | null }) {
  const market = status?.market ?? null;
  const lines = status?.lines ?? [];
  const serverDensity = status?.market_density ?? 1;

  // Same commit-on-release pattern as the old SimControls slider: track the finger
  // locally, POST once on release, drop the override when the server echoes it back.
  const [localDensity, setLocalDensity] = useState<number | null>(null);
  const density = localDensity ?? serverDensity;
  useEffect(() => {
    if (localDensity != null && Math.abs(serverDensity - localDensity) < 1e-6) {
      setLocalDensity(null);
    }
  }, [serverDensity, localDensity]);
  // On failure, drop the override so the knob snaps back to the server truth instead of
  // shadowing it forever (the SSE echo is what clears it on success).
  const commit = (v: number) =>
    simApi.control({ market_density: v }).catch(() => setLocalDensity(null));

  // A shared scale keeps the per-line bars comparable to each other.
  const barMax = Math.max(1, ...lines.flatMap((l) => [l.market.niche_bid, l.market.our_bid]));

  return (
    <div className="card panel pulse">
      <div className="panel-head">
        <div>
          <h3 className="panel-title">Market pulse</h3>
          <p className="panel-sub">Live competitive pressure across all niches</p>
        </div>
        <span className={`pill ${market && market.auction_type === 1 ? "ok" : "checking"}`}>
          {market ? (market.auction_type === 1 ? "1st price" : "2nd price") : "…"}
        </span>
      </div>

      <div className="pulse-hero">
        <div>
          <span className="pulse-big tnum">{market ? usd(market.avg_bid) : "—"}</span>
          <span className="pulse-cap">avg competitor bid · eCPM, all niches</span>
        </div>
        <div className="pulse-floor tnum">
          floor {market ? usd(market.floor) : "—"}
        </div>
      </div>

      <div className="knob">
        <div className="knob-head">
          <label htmlFor="density">Market density</label>
          <span className="knob-val tnum">{density.toFixed(1)}×</span>
        </div>
        <input
          id="density"
          type="range"
          min={0}
          max={3}
          step={0.1}
          value={density}
          onChange={(e) => setLocalDensity(Number(e.target.value))}
          onPointerUp={(e) => commit(Number(e.currentTarget.value))}
          onKeyUp={(e) => commit(Number(e.currentTarget.value))}
        />
        <p className="knob-hint">
          More competition → niche bids rise, win rates fall. Watch the table react.
        </p>
      </div>

      <div className="pulse-lines">
        <div className="pulse-legend">
          <span><i className="lg-dot ours" /> our bid</span>
          <span><i className="lg-dot market" /> niche avg</span>
        </div>
        {lines.map((l) => (
          <div key={l.ad_id} className="pulse-line">
            <div className="pulse-line-head">
              <span className="pulse-brand">{l.brand}</span>
              <span className="pulse-nums tnum">
                {usd(l.market.our_bid)} <em>vs {usd(l.market.niche_bid)}</em>
              </span>
            </div>
            <div className="duo">
              <span className="duo-bar ours" style={{ width: `${(l.market.our_bid / barMax) * 100}%` }} />
              <span className="duo-bar market" style={{ width: `${(l.market.niche_bid / barMax) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>

      {market && market.seats.length > 0 && (
        <div className="pulse-seats">
          <span className="pulse-seats-label">Bidding against you</span>
          <div className="pulse-seat-chips">
            {market.seats.map((s) => (
              <span key={s} className="mini-chip ghost">{s}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
