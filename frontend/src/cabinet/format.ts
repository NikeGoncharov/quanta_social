// Small number/format helpers shared across cabinet views.
export function compact(v: number): string {
  const a = Math.abs(v);
  if (a >= 1_000_000) return `${(v / 1_000_000).toFixed(a >= 10_000_000 ? 0 : 1)}M`;
  if (a >= 1000) return `${(v / 1000).toFixed(a >= 10_000 ? 0 : 1)}k`;
  return String(Math.round(v));
}

export function usd(v: number | null | undefined): string {
  if (v == null) return "—";
  return `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function usdCompact(v: number | null | undefined): string {
  if (v == null) return "—";
  return `$${compact(v)}`;
}

export function pct(v: number | null | undefined, digits = 1): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

export function count(v: number | null | undefined): string {
  if (v == null) return "—";
  return v >= 10_000 ? compact(v) : v.toLocaleString("en-US");
}

export const OBJ_LABEL: Record<string, string> = {
  awareness: "Awareness",
  traffic: "Traffic",
  engagement: "Engagement",
  conversions: "Conversions",
};
