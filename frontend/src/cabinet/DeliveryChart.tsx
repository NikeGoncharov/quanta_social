// Delivery history — the static, browsable half of the dashboard. Uniform 30-sim-minute
// bins fetched from /sim/history (not the SSE feed): its shape is independent of the sim
// speed, missing bins render as honest zeros, and longer ranges let you scroll back
// through sim-days. The LIVE element of the dashboard is the KPI tile row above.
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
import { simApi } from "../api/sim";

type Metric = "impressions" | "clicks" | "conversions" | "spend" | "revenue";

const METRICS: { key: Metric; label: string; money?: boolean }[] = [
  { key: "impressions", label: "Impressions" },
  { key: "clicks", label: "Clicks" },
  { key: "conversions", label: "Conversions" },
  { key: "spend", label: "Spend", money: true },
  { key: "revenue", label: "Revenue", money: true },
];

const BIN = 30; // sim-minutes per history bin
const REFRESH_MS = 30_000;

const RANGES: { key: string; label: string; bins: number }[] = [
  { key: "12h", label: "12h", bins: 24 },
  { key: "24h", label: "24h", bins: 48 },
  { key: "3d", label: "3d", bins: 144 },
  { key: "7d", label: "7d", bins: 336 },
];

function binLabel(t: number): string {
  const day = Math.floor(t / 1440) + 1;
  const min = ((t % 1440) + 1440) % 1440;
  const hh = String(Math.floor(min / 60)).padStart(2, "0");
  const mm = String(min % 60).padStart(2, "0");
  return `D${day} ${hh}:${mm}`;
}

export function DeliveryHistory({ simTime }: { simTime: number | null }) {
  const [metric, setMetric] = useState<Metric>("impressions");
  const [rangeKey, setRangeKey] = useState("24h");
  const [points, setPoints] = useState<DeliveryPoint[] | null>(null);
  const range = RANGES.find((r) => r.key === rangeKey)!;
  const active = METRICS.find((m) => m.key === metric)!;

  useEffect(() => {
    let alive = true;
    const load = () =>
      simApi
        .history(BIN, range.bins)
        .then((r) => {
          if (alive) setPoints(r.points);
        })
        .catch(() => {});
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [range.bins]);

  // Uniform-bin series with explicit zeros for empty bins, anchored to the world clock so
  // quiet stretches (budget-capped nights) show as flat zero, not a skipped gap.
  const data = useMemo(() => {
    if (!points || points.length === 0) return [];
    const by = new Map(points.map((p) => [p.t, p]));
    const lastData = points[points.length - 1].t;
    const anchor = simTime != null ? Math.floor(simTime / 60 / BIN) * BIN : lastData;
    const end = Math.max(anchor, lastData);
    const first = Math.floor(points[0].t / BIN) * BIN;
    const start = Math.max(end - (range.bins - 1) * BIN, first);
    const out: { t: number; v: number }[] = [];
    for (let t = start; t <= end; t += BIN) {
      const p = by.get(t);
      out.push({ t, v: p ? p[metric] : 0 });
    }
    return out;
  }, [points, metric, simTime, range.bins]);

  return (
    <div className="card panel chart-card">
      <div className="panel-head">
        <div>
          <h3 className="panel-title">Delivery history</h3>
          <p className="panel-sub">Totals per 30 sim-minutes · all campaigns</p>
        </div>
        <div className="chart-controls">
          <div className="seg">
            {RANGES.map((r) => (
              <button
                key={r.key}
                className={`seg-btn ${r.key === rangeKey ? "on" : ""}`}
                onClick={() => setRangeKey(r.key)}
              >
                {r.label}
              </button>
            ))}
          </div>
          <div className="seg">
            {METRICS.map((m) => (
              <button
                key={m.key}
                className={`seg-btn ${m.key === metric ? "on" : ""}`}
                onClick={() => setMetric(m.key)}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="chart-wrap">
        {data.length === 0 ? (
          <div className="chart-empty">Waiting for the world to tick…</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="qFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="var(--accent)" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis
                dataKey="t"
                tickFormatter={binLabel}
                tick={{ fill: "var(--text-muted)", fontSize: 12 }}
                stroke="var(--border)"
                minTickGap={56}
              />
              <YAxis
                tick={{ fill: "var(--text-muted)", fontSize: 12 }}
                stroke="var(--border)"
                width={52}
                tickFormatter={(v) => (active.money ? `$${compact(v)}` : compact(v))}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--elevated)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  color: "var(--text)",
                  fontSize: 13,
                }}
                labelFormatter={(t) => `${binLabel(Number(t))} — ${binLabel(Number(t) + BIN)}`}
                formatter={(v: number) => [
                  `${active.money ? "$" : ""}${compact(v)}`,
                  `${active.label} / 30 min`,
                ]}
              />
              <Area
                type="monotone"
                dataKey="v"
                stroke="var(--accent)"
                strokeWidth={2}
                fill="url(#qFill)"
                isAnimationActive={false}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

function compact(v: number): string {
  if (v >= 1000) return `${(v / 1000).toFixed(v >= 10000 ? 0 : 1)}k`;
  if (v >= 100) return String(Math.round(v));
  return String(Math.round(v * 100) / 100);
}
