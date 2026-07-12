// Deterministic gradient avatar (no uploads in v1) — same stock-gradient trick creatives use,
// so every user has a stable, distinct tile derived from their avatar_seed.
import { stockGradient } from "../cabinet/stock";

export function Avatar({
  seed, name, size = 40,
}: {
  seed: string;
  name: string;
  size?: number;
}) {
  const initial = (name || "?").trim().charAt(0).toUpperCase() || "?";
  return (
    <div
      className="avatar"
      style={{
        width: size,
        height: size,
        background: stockGradient(seed || name),
        fontSize: size * 0.42,
      }}
      aria-hidden
    >
      {initial}
    </div>
  );
}
