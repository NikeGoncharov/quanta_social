// The visible learning phase (Conversions / Engagement objectives only): a progress ring
// with "N more conversions to exit". Renders nothing for objectives without a learning phase.
import type { LineStatus } from "../api/sim";

const R = 20;
const C = 2 * Math.PI * R;

export function LearningBadge({ live }: { live: LineStatus | null }) {
  if (!live || live.in_learning == null) return null;
  const signal = live.signal ?? 0;
  const total = signal + (live.signal_to_exit ?? 0);
  const frac = live.in_learning ? (total > 0 ? signal / total : 0) : 1;
  const done = !live.in_learning;
  return (
    <div className="card panel">
      <div className="learn">
        <svg className="learn-ring" width={48} height={48} viewBox="0 0 48 48">
          <circle cx={24} cy={24} r={R} fill="none" stroke="var(--surface-2)" strokeWidth={5} />
          <circle
            cx={24}
            cy={24}
            r={R}
            fill="none"
            stroke={done ? "var(--good)" : "var(--accent)"}
            strokeWidth={5}
            strokeLinecap="round"
            strokeDasharray={C}
            strokeDashoffset={C * (1 - frac)}
            transform="rotate(-90 24 24)"
          />
        </svg>
        <div className="learn-copy">
          <div className="learn-title">{done ? "Optimized" : "In learning"}</div>
          <div className="learn-sub">
            {done
              ? "Learning complete — delivery has stabilized."
              : `About ${Math.ceil(live.signal_to_exit ?? 0)} more conversions to exit the learning phase.`}
          </div>
        </div>
      </div>
    </div>
  );
}
