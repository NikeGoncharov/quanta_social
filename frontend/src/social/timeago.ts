// Compact relative time from a wall-epoch-seconds timestamp ("3m", "2h", "5d", else a date).
export function timeAgo(epochSeconds: number): string {
  const s = Math.max(0, Date.now() / 1000 - epochSeconds);
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}d`;
  return new Date(epochSeconds * 1000).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
