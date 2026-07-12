// The live audience gauge: estimated reach for a targeting spec. Pure display — the parent
// (targeting editor / wizard) supplies the numbers so there is one debounced fetch, not many.
import { compact } from "./format";

export function AudienceGauge({
  audience,
  reachPct,
  segments,
  loading,
}: {
  audience: number;
  reachPct: number;
  segments: number;
  loading?: boolean;
}) {
  // Reach is a fraction of the whole network (a single interest is ~10%), so a sqrt scale
  // keeps small-but-real audiences visible while the caption shows the true share.
  const fill = Math.min(1, Math.sqrt(Math.max(0, reachPct)));
  return (
    <div className="gauge">
      <div className="gauge-num">{loading ? "…" : compact(audience)}</div>
      <div className="gauge-meter">
        <div className="gauge-track">
          <span className="gauge-fill" style={{ width: `${fill * 100}%` }} />
        </div>
        <div className="gauge-cap">
          {segments.toLocaleString("en-US")} segments · {(reachPct * 100).toFixed(1)}% of the network
        </div>
      </div>
    </div>
  );
}
