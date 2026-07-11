import { useCallback, useEffect, useRef, useState } from "react";

import type { SampleDetail, SampleSummary } from "../api/sim";
import { simApi } from "../api/sim";

function usd(n: number): string {
  return `$${n.toFixed(2)}`;
}

function SeatBids({ detail }: { detail: SampleDetail }) {
  return (
    <div className="bids">
      <div className="bids-clear tnum">
        {detail.won ? (
          <>
            Cleared at <strong>{usd(detail.clearing)}</strong> · floor {usd(detail.floor)} · min-to-win{" "}
            {usd(detail.min_to_win)}
          </>
        ) : (
          <>No winner · floor {usd(detail.floor)}</>
        )}
      </div>
      <table className="bid-table tnum">
        <thead>
          <tr>
            <th>Seat</th>
            <th>Bid CPM</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {detail.bids.eligible.map((b, i) => (
            <tr key={`e${i}`} className={b.is_winner ? "win" : ""}>
              <td>{b.seat}</td>
              <td>{usd(b.price)}</td>
              <td>{b.is_winner ? <span className="tag-win">WON</span> : "eligible"}</td>
            </tr>
          ))}
          {detail.bids.filtered.map((b, i) => (
            <tr key={`f${i}`} className="filtered">
              <td>{b.seat}</td>
              <td>{usd(b.price)}</td>
              <td>
                <span className="tag-filtered" title={`nbr/loss code ${b.reason_code}`}>
                  {b.reason}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Notices({ detail }: { detail: SampleDetail }) {
  return (
    <div className="notices">
      {detail.notices.map((n, i) => (
        <div key={i} className={`notice ${n.billed ? "billed" : ""}`}>
          <span className={`notice-kind ${n.kind}`}>{n.billed ? "BILLED" : n.kind.toUpperCase()}</span>
          <span className="notice-seat">{n.seat}</span>
          <code className="notice-url">{n.url}</code>
        </div>
      ))}
    </div>
  );
}

function Detail({ detail }: { detail: SampleDetail }) {
  const [showJson, setShowJson] = useState(false);
  return (
    <div className="inspect-detail">
      <div className="inspect-meta">
        <span className="seg-key">{detail.segment_key}</span>
        <span className="muted">imp for {detail.line_ad_id}</span>
      </div>

      <h4 className="inspect-h">Seat bids &amp; settlement</h4>
      <SeatBids detail={detail} />

      <h4 className="inspect-h">Notice lifecycle (macros expanded)</h4>
      <Notices detail={detail} />

      <button className="link-btn" onClick={() => setShowJson((v) => !v)}>
        {showJson ? "Hide" : "Show"} OpenRTB BidRequest
      </button>
      {showJson && <pre className="json">{JSON.stringify(detail.request, null, 2)}</pre>}
    </div>
  );
}

export function RtbInspector() {
  const [samples, setSamples] = useState<SampleSummary[]>([]);
  const [detail, setDetail] = useState<SampleDetail | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  // Monotonic token so a slow response for an earlier click can't clobber a later one.
  const seq = useRef(0);

  const refresh = useCallback(async () => {
    try {
      const { samples } = await simApi.samples(24);
      setSamples(samples);
    } catch {
      /* transient */
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 3500);
    return () => clearInterval(id);
  }, [refresh]);

  const select = async (id: number) => {
    const mine = ++seq.current;
    setSelectedId(id);
    try {
      const d = await simApi.sample(id);
      if (mine === seq.current) setDetail(d);
    } catch {
      if (mine === seq.current) setDetail(null);
    }
  };

  const replay = async () => {
    const mine = ++seq.current;
    setBusy(true);
    try {
      const d = await simApi.replay({});
      if (mine === seq.current) {
        setDetail(d);
        setSelectedId(null);
      }
      refresh();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card panel inspector">
      <div className="panel-head">
        <div>
          <h3 className="panel-title">RTB inspector</h3>
          <p className="panel-sub">Real OpenRTB auctions, sampled live from the world</p>
        </div>
        <button className="btn primary sm" onClick={replay} disabled={busy}>
          {busy ? "Running…" : "⚡ Run a live auction"}
        </button>
      </div>

      <div className="inspect-body">
        <ul className="sample-list">
          {samples.length === 0 && <li className="sample-empty">No auctions sampled yet…</li>}
          {samples.map((s) => (
            <li
              key={s.id}
              className={`sample-row ${s.id === selectedId ? "sel" : ""}`}
              onClick={() => select(s.id)}
            >
              <span className={`dot-badge ${s.won ? "won" : "lost"}`} />
              <span className="sample-seat">{s.won ? s.winner_seat : "no win"}</span>
              <span className="sample-seg">{s.segment_key}</span>
              <span className="sample-price tnum">{usd(s.clearing)}</span>
            </li>
          ))}
        </ul>

        <div className="inspect-pane">
          {detail ? (
            <Detail detail={detail} />
          ) : (
            <div className="inspect-hint">
              Pick an auction on the left, or run one live, to see its bid request, competing
              seats, clearing price and notice lifecycle.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
