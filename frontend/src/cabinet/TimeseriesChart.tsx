// A reporting timeseries: uniform 30-sim-minute bins from /cabinet/reporting/timeseries,
// with a metric + range toggle. Scoped to one campaign (or all, when campaignId is undefined).
import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { DeliveryPoint } from "../api/sim";
import { cabinetApi } from "../api/cabinet";
import { compact } from "./format";

type Metric = "impressions" | "clicks" | "conversions" | "spend" | "revenue";
const METRICS: { key: Metric; label: string; money?: boolean }[] = [
  { key: "impressions", label: "Impressions" },
  { key: "clicks", label: "Clicks" },
  { key: "conversions", label: "Conversions" },
  { key: "spend", label: "Spend", money: true },
  { key: "revenue", label: "Revenue", money: true },
];
const BIN = 30;
const RANGES = [
  { key: "12h", bins: 24 },
  { key: "24h", bins: 48 },
  { key: "3d", bins: 144 },
  { key: "7d", bins: 336 },
];
const REFRESH_MS = 30_000;

function binLabel(t: number): string {
  const day = Math.floor(t / 1440) + 1;
  const min = ((t % 1440) + 1440) % 1440;
  return `D${day} ${String(Math.floor(min / 60)).padStart(2, "0")}:${String(min % 60).padStart(2, "0")}`;
}

export function TimeseriesChart({ campaignId }: { campaignId?: string }) {
  const [metric, setMetric] = useState<Metric>("impressions");
  const [rangeKey, setRangeKey] = useState("24h");
  const [points, setPoints] = useState<DeliveryPoint[] | null>(null);
  const range = RANGES.find((r) => r.key === rangeKey)!;
  const active = METRICS.find((m) => m.key === metric)!;

  useEffect(() => {
    let alive = true;
    const load = () =>
      cabinetApi
        .timeseries(campaignId, BIN, range.bins)
        .then((r) => alive && setPoints(r.points))
        .catch(() => {});
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [campaignId, range.bins]);

  const data = useMemo(() => {
    if (!points || points.length === 0) return [];
    const by = new Map(points.map((p) => [p.t, p]));
    const end = points[points.length - 1].t;
    const start = Math.max(end - (range.bins - 1) * BIN, points[0].t);
    const out: { t: number; v: number }[] = [];
    for (let t = start; t <= end; t += BIN) out.push({ t, v: by.get(t)?.[metric] ?? 0 });
    return out;
  }, [points, metric, range.bins]);

  return (
    <div className="card panel chart-card">
      <div className="panel-head">
        <div>
          <h3 className="panel-title">Delivery over time</h3>
          <p className="panel-sub">Totals per 30 sim-minutes</p>
        </div>
        <div className="chart-controls">
          <div className="seg">
            {RANGES.map((r) => (
              <button key={r.key} className={`seg-btn ${r.key === rangeKey ? "on" : ""}`} onClick={() => setRangeKey(r.key)}>
                {r.key}
              </button>
            ))}
          </div>
          <div className="seg">
            {METRICS.map((m) => (
              <button key={m.key} className={`seg-btn ${m.key === metric ? "on" : ""}`} onClick={() => setMetric(m.key)}>
                {m.label}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="chart-wrap">
        {data.length === 0 ? (
          <div className="chart-empty">No delivery in this range yet.</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="qFillR" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="var(--accent)" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis dataKey="t" tickFormatter={binLabel} tick={{ fill: "var(--text-muted)", fontSize: 12 }} stroke="var(--border)" minTickGap={56} />
              <YAxis
                tick={{ fill: "var(--text-muted)", fontSize: 12 }}
                stroke="var(--border)"
                width={52}
                tickFormatter={(v) => (active.money ? `$${compact(v)}` : compact(v))}
              />
              <Tooltip
                contentStyle={{ background: "var(--elevated)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text)", fontSize: 13 }}
                labelFormatter={(t) => binLabel(Number(t))}
                formatter={(v: number) => [`${active.money ? "$" : ""}${compact(v)}`, `${active.label} / 30 min`]}
              />
              <Area type="monotone" dataKey="v" stroke="var(--accent)" strokeWidth={2} fill="url(#qFillR)" isAnimationActive={false} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
