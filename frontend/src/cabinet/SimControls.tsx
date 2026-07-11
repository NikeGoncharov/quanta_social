// The sim control strip: pause/resume, the world clock + state pill, and time speed.
// (The market-density knob lives in MarketPulse, next to the signals it drives.)
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

  return (
    <div className="card controls-strip">
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
  );
}
