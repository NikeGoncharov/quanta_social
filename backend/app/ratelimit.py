"""A tiny in-process rate limiter for unauthenticated public endpoints.

The deployment runs a single uvicorn worker (mandated by the one in-process world loop), so
one in-memory map is authoritative — no Redis needed. Keyed on the real client IP, which
behind Cloudflare Tunnel arrives in `CF-Connecting-IP` (Caddy forwards it downstream). The
origin is only reachable *through* the tunnel, never by a direct TCP connection, so that
header is trustworthy here — a client can't spoof it to dodge or frame another IP.
"""
import time
from collections import deque

from fastapi import Request


def client_ip(request: Request) -> str:
    """The true client IP. Cloudflare sets CF-Connecting-IP at its edge; we fall back to the
    first X-Forwarded-For hop, then the TCP peer (local dev, where there is no proxy)."""
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class SlidingWindowLimiter:
    """Allow at most `limit` events per `window` seconds per key (sliding window).

    Rejections do NOT extend the window (we only append on an allowed hit), so a caller that
    stops hammering recovers after `window` seconds. Stale keys are swept periodically so the
    map can't grow unbounded under a spray of distinct IPs.
    """

    def __init__(self, *, limit: int, window: float, sweep_every: int = 500):
        self.limit = limit
        self.window = window
        self._sweep_every = sweep_every
        self._ops = 0
        self._hits: dict[str, deque] = {}

    def allow(self, key: str, *, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        self._ops += 1
        if self._ops % self._sweep_every == 0:
            self._sweep(now)
        dq = self._hits.setdefault(key, deque())
        cutoff = now - self.window
        while dq and dq[0] <= cutoff:
            dq.popleft()
        if len(dq) >= self.limit:
            return False
        dq.append(now)
        return True

    def _sweep(self, now: float) -> None:
        cutoff = now - self.window
        stale = [k for k, dq in self._hits.items() if not dq or dq[-1] <= cutoff]
        for k in stale:
            del self._hits[k]

    def reset(self) -> None:
        """Drop all recorded hits (used by tests for a clean window)."""
        self._hits.clear()
        self._ops = 0
