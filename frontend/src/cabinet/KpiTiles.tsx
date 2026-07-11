// The dashboard's headline row: six KPI tiles computed client-side from the live
// per-sim-minute delivery series — value over the last sim-hour, delta vs the sim-hour
// before it, and a sparkline of the recent shape.
//
// Windows are cut by the points' sim-time `t`, NOT by array position: buckets only exist
// for minutes that delivered, so at fast sim speeds (or after paused/budget-capped
// stretches) N array entries can span far more than N sim-minutes. The window is anchored
// on the world clock when available so zero-delivery minutes correctly age out.
import type { ReactNode } from "react";

import type { DeliveryPoint } from "../api/sim";

const WINDOW = 60; // sim-minutes per comparison window
const SPARK_POINTS = 48;

type Dir = "up-good" | "up-bad" | "neutral";

interface KpiDef {
  key: string;
  label: string;
  icon: ReactNode;
  dir: Dir;
  // per-window aggregate + per-point series value (for the sparkline). Sparkline values
  // for volume metrics are per-minute rates (÷ the bucket's span), so the shape doesn't
  // jump when the sim speed makes buckets fatter; ratios are scale-free already.
  total: (w: DeliveryPoint[]) => number | null;
  point: (p: DeliveryPoint) => number;
  fmt: (v: number) => string;
}

const sum = (w: DeliveryPoint[], k: keyof DeliveryPoint) =>
  w.reduce((a, p) => a + (p[k] as number), 0);

function fmtCount(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 10_000) return `${(v / 1000).toFixed(1)}k`;
  if (v >= 1000) return `${(v / 1000).toFixed(2)}k`;
  return String(Math.round(v));
}
const fmtMoney = (v: number) => `$${v >= 1000 ? fmtCount(v) : v.toFixed(2)}`;
const fmtPct = (v: number) => `${(v * 100).toFixed(2)}%`;

const ICONS = {
  eye: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" /><circle cx="12" cy="12" r="3" /></svg>
  ),
  cursor: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m4 4 7.5 16 2.3-6.8L20.6 11 4 4Z" /></svg>
  ),
  ratio: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 17l6-6 4 4 8-8" /><path d="M15 7h6v6" /></svg>
  ),
  target: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1" /></svg>
  ),
  coins: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M12 6v12" /><path d="M15.5 9.5c-.7-1-1.9-1.5-3.5-1.5-2 0-3.5.9-3.5 2.25S10 12.4 12 12.5s3.5.9 3.5 2.25S14 17 12 17c-1.6 0-2.8-.5-3.5-1.5" /></svg>
  ),
  gavel: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m14 14-7.5 7.5a1.75 1.75 0 0 1-2.5-2.5L11.5 11.5" /><path d="m9.5 6.5 8 8" /><path d="m7 9 5.5-5.5L20 11l-5.5 5.5" /></svg>
  ),
};

const rate = (p: DeliveryPoint, v: number) => v / (p.span || 1);

const KPIS: KpiDef[] = [
  {
    key: "impressions", label: "Impressions", icon: ICONS.eye, dir: "up-good",
    total: (w) => sum(w, "impressions"), point: (p) => rate(p, p.impressions), fmt: fmtCount,
  },
  {
    key: "clicks", label: "Clicks", icon: ICONS.cursor, dir: "up-good",
    total: (w) => sum(w, "clicks"), point: (p) => rate(p, p.clicks), fmt: fmtCount,
  },
  {
    key: "ctr", label: "CTR", icon: ICONS.ratio, dir: "up-good",
    total: (w) => {
      const i = sum(w, "impressions");
      return i > 0 ? sum(w, "clicks") / i : null;
    },
    point: (p) => (p.impressions > 0 ? p.clicks / p.impressions : 0),
    fmt: fmtPct,
  },
  {
    key: "conversions", label: "Conversions", icon: ICONS.target, dir: "up-good",
    total: (w) => sum(w, "conversions"), point: (p) => rate(p, p.conversions), fmt: fmtCount,
  },
  {
    key: "spend", label: "Spend", icon: ICONS.coins, dir: "neutral",
    total: (w) => sum(w, "spend"), point: (p) => rate(p, p.spend), fmt: fmtMoney,
  },
  {
    key: "cpm", label: "Avg CPM", icon: ICONS.gavel, dir: "up-bad",
    total: (w) => {
      const i = sum(w, "impressions");
      return i > 0 ? (sum(w, "spend") * 1000) / i : null;
    },
    point: (p) => (p.impressions > 0 ? (p.spend * 1000) / p.impressions : 0),
    fmt: fmtMoney,
  },
];

function Spark({ values }: { values: number[] }) {
  if (values.length < 2) return <svg className="spark" viewBox="0 0 100 32" />;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = max - min || 1;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * 100;
    const y = 29 - ((v - min) / span) * 26;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return (
    <svg className="spark" viewBox="0 0 100 32" preserveAspectRatio="none" aria-hidden>
      <polygon points={`0,32 ${pts.join(" ")} 100,32`} className="spark-fill" />
      <polyline points={pts.join(" ")} className="spark-line" />
    </svg>
  );
}

function Delta({ cur, prev, dir }: { cur: number | null; prev: number | null; dir: Dir }) {
  if (cur == null || prev == null || prev === 0) return <span className="kpi-delta na">—</span>;
  const pct = ((cur - prev) / prev) * 100;
  if (!isFinite(pct)) return <span className="kpi-delta na">—</span>;
  const up = pct >= 0;
  const cls =
    dir === "neutral" ? "flat" : (dir === "up-good") === up ? "good" : "bad";
  return (
    <span className={`kpi-delta ${cls}`}>
      {up ? "↑" : "↓"} {Math.abs(pct).toFixed(1)}%
    </span>
  );
}

export function KpiTiles({ points, simTime }: { points: DeliveryPoint[]; simTime?: number | null }) {
  // Anchor on the live world clock so minutes with zero delivery age the window; fall
  // back to the newest point when the clock hasn't arrived yet.
  const lastT = points.length ? points[points.length - 1].t : null;
  const anchor = simTime != null ? Math.floor(simTime / 60) : lastT;
  const cur = anchor == null ? [] : points.filter((p) => p.t > anchor - WINDOW && p.t <= anchor);
  const prev =
    anchor == null
      ? []
      : points.filter((p) => p.t > anchor - 2 * WINDOW && p.t <= anchor - WINDOW);
  // Only trust the delta when history genuinely covers the full previous window —
  // otherwise a fresh world compares a full hour against a sliver and shows fake growth.
  const coversPrev = anchor != null && points.length > 0 && points[0].t <= anchor - 2 * WINDOW;
  const sparkSrc = points.slice(-SPARK_POINTS);

  return (
    <div className="kpis">
      {KPIS.map((k) => {
        const value = cur.length ? k.total(cur) : null;
        const before = coversPrev && prev.length ? k.total(prev) : null;
        return (
          <div key={k.key} className="card kpi">
            <div className="kpi-main">
              <span className="kpi-label">{k.label}</span>
              <span className="kpi-value tnum">{value == null ? "—" : k.fmt(value)}</span>
              <Delta cur={value} prev={before} dir={k.dir} />
            </div>
            <div className="kpi-side">
              <span className="kpi-icon">{k.icon}</span>
              <Spark values={sparkSrc.map(k.point)} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
