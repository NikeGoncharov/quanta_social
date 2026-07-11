import { useEffect, useState } from "react";

import type { ControlPatch, SimStatus } from "../api/sim";
import { simApi } from "../api/sim";

const SPEEDS: { label: string; value: number }[] = [
  { label: "1 min/s", value: 60 },
  { label: "10 min/s", value: 600 },
  { label: "1 h/s", value: 3600 },
];

// Fire-and-forget control POST; the SSE `status` echo is the source of truth, so a failed
// call just leaves the UI on the last known state instead of throwing an unhandled rejection.
function post(patch: ControlPatch) {
  simApi.control(patch).catch(() => {});
}

export function SimControls({ status }: { status: SimStatus | null }) {
  const running = status?.running ?? false;
  const active = status?.active ?? false;
  const serverDensity = status?.market_density ?? 1;

  // The slider tracks the finger locally while dragging; we only POST on release, then drop
  // the local override once the server echoes our value back (avoids rubber-banding and the
  // ~20-commits-per-drag write storm of a controlled input bound straight to the SSE echo).
  const [localDensity, setLocalDensity] = useState<number | null>(null);
  const density = localDensity ?? serverDensity;

  useEffect(() => {
    if (localDensity != null && Math.abs(serverDensity - localDensity) < 1e-6) {
      setLocalDensity(null);
    }
  }, [serverDensity, localDensity]);

  const commitDensity = (v: number) => post({ market_density: v });

  return (
    <div className="card panel controls">
      <div className="controls-row">
        <button className={`btn ${running ? "" : "primary"}`} onClick={() => post({ running: !running })}>
          {running ? "❚❚ Pause" : "▶ Resume"}
        </button>

        <div className="clock">
          <span className="clock-time tnum">{status?.sim_clock ?? "—"}</span>
          <span className={`pill ${active ? "ok" : "checking"}`}>
            <span className="dot" />
            {active ? "world running" : running ? "idle (no viewers)" : "paused"}
          </span>
        </div>

        <div className="seg speed-seg">
          {SPEEDS.map((s) => (
            <button
              key={s.value}
              className={`seg-btn ${status?.speed === s.value ? "on" : ""}`}
              onClick={() => post({ speed: s.value })}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      <div className="knob">
        <div className="knob-head">
          <label htmlFor="density">Market density</label>
          <span className="knob-val tnum">{density.toFixed(1)}×</span>
        </div>
        <input
          id="density"
          type="range"
          min={0}
          max={3}
          step={0.1}
          value={density}
          onChange={(e) => setLocalDensity(Number(e.target.value))}
          onPointerUp={(e) => commitDensity(Number(e.currentTarget.value))}
          onKeyUp={(e) => commitDensity(Number(e.currentTarget.value))}
        />
        <p className="knob-hint">
          Turn up competition and watch clearing prices rise and win rates fall — the auction,
          in the open.
        </p>
      </div>
    </div>
  );
}
