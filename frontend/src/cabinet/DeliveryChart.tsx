import { useState } from "react";
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

type Metric = "impressions" | "clicks" | "conversions" | "spend" | "revenue";

const METRICS: { key: Metric; label: string; money?: boolean }[] = [
  { key: "impressions", label: "Impressions" },
  { key: "clicks", label: "Clicks" },
  { key: "conversions", label: "Conversions" },
  { key: "spend", label: "Spend", money: true },
  { key: "revenue", label: "Revenue", money: true },
];

function clock(t: number): string {
  const min = ((t % 1440) + 1440) % 1440;
  return `${String(Math.floor(min / 60)).padStart(2, "0")}:${String(min % 60).padStart(2, "0")}`;
}

export function DeliveryChart({ points }: { points: DeliveryPoint[] }) {
  const [metric, setMetric] = useState<Metric>("impressions");
  const active = METRICS.find((m) => m.key === metric)!;

  return (
    <div className="card panel chart-card">
      <div className="panel-head">
        <div>
          <h3 className="panel-title">Live delivery</h3>
          <p className="panel-sub">Aggregated across all campaigns, per sim-minute</p>
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

      <div className="chart-wrap">
        {points.length === 0 ? (
          <div className="chart-empty">Waiting for the world to tick…</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="qFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="var(--accent)" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis
                dataKey="t"
                tickFormatter={clock}
                tick={{ fill: "var(--text-muted)", fontSize: 12 }}
                stroke="var(--border)"
                minTickGap={40}
              />
              <YAxis
                tick={{ fill: "var(--text-muted)", fontSize: 12 }}
                stroke="var(--border)"
                width={52}
                tickFormatter={(v) => (active.money ? `$${v}` : compact(v))}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--elevated)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  color: "var(--text)",
                  fontSize: 13,
                }}
                labelFormatter={(t) => `Sim ${clock(Number(t))}`}
                formatter={(v: number) => [active.money ? `$${v}` : v, active.label]}
              />
              <Area
                type="monotone"
                dataKey={metric}
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
  return String(v);
}
