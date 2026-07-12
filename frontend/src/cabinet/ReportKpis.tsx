// Reporting KPI tiles: value + window-over-window delta. Pure display of a KpiReport.
import type { KpiReport } from "../api/cabinet";
import { count, pct, usd } from "./format";

const CARDS: { key: string; label: string; fmt: (v: number | null) => string }[] = [
  { key: "impressions", label: "Impressions", fmt: (v) => count(v) },
  { key: "clicks", label: "Clicks", fmt: (v) => count(v) },
  { key: "conversions", label: "Conversions", fmt: (v) => count(v) },
  { key: "spend", label: "Spend", fmt: (v) => usd(v) },
  { key: "ctr", label: "CTR", fmt: (v) => pct(v, 2) },
  { key: "revenue", label: "Revenue", fmt: (v) => usd(v) },
  { key: "roas", label: "ROAS", fmt: (v) => (v == null ? "—" : `${v.toFixed(2)}×`) },
  { key: "win_rate", label: "Win rate", fmt: (v) => pct(v, 0) },
];

function Delta({ d }: { d: number | null | undefined }) {
  if (d == null) return <span className="rk-delta flat">—</span>;
  if (Math.abs(d) < 0.005) return <span className="rk-delta flat">±0%</span>;
  const up = d > 0;
  return (
    <span className={`rk-delta ${up ? "up" : "down"}`}>
      {up ? "▲" : "▼"} {Math.abs(d * 100).toFixed(0)}%
    </span>
  );
}

export function ReportKpis({ report }: { report: KpiReport | null }) {
  const cur = report?.current;
  return (
    <div className="rk-grid">
      {CARDS.map((c) => (
        <div className="card rk" key={c.key}>
          <div className="rk-lbl">{c.label}</div>
          <div className="rk-val tnum">{cur ? c.fmt((cur as unknown as Record<string, number | null>)[c.key]) : "—"}</div>
          <Delta d={report?.deltas?.[c.key]} />
        </div>
      ))}
    </div>
  );
}
