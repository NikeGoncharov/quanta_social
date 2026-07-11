// Subscribe to the world loop over SSE. Connecting counts as a viewer, which un-pauses the
// idle loop, so the chart comes alive the moment the cabinet mounts.
import { useEffect, useRef, useState } from "react";

import type { DeliveryPoint, SimStatus } from "../api/sim";

const MAX_POINTS = 240;

export interface SimStream {
  status: SimStatus | null;
  points: DeliveryPoint[];
  connected: boolean;
}

function mergePoint(points: DeliveryPoint[], p: DeliveryPoint): DeliveryPoint[] {
  const last = points[points.length - 1];
  let next: DeliveryPoint[];
  if (last && last.t === p.t) {
    next = [...points.slice(0, -1), p]; // same sim-minute re-emitted — replace
  } else if (last && p.t < last.t) {
    return points; // stale/out-of-order, ignore
  } else {
    next = [...points, p];
  }
  return next.length > MAX_POINTS ? next.slice(next.length - MAX_POINTS) : next;
}

export function useSimStream(): SimStream {
  const [status, setStatus] = useState<SimStatus | null>(null);
  const [points, setPoints] = useState<DeliveryPoint[]>([]);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource("/api/sim/stream");
    esRef.current = es;

    es.addEventListener("snapshot", (e) => {
      const data = JSON.parse((e as MessageEvent).data) as {
        status: SimStatus;
        delivery: DeliveryPoint[];
      };
      setStatus(data.status);
      setPoints(data.delivery.slice(-MAX_POINTS));
      setConnected(true);
    });

    es.addEventListener("status", (e) => {
      setStatus(JSON.parse((e as MessageEvent).data) as SimStatus);
    });

    es.addEventListener("delivery", (e) => {
      const p = JSON.parse((e as MessageEvent).data) as DeliveryPoint;
      setPoints((prev) => mergePoint(prev, p));
    });

    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false); // EventSource auto-reconnects

    return () => {
      es.close();
      esRef.current = null;
    };
  }, []);

  return { status, points, connected };
}
