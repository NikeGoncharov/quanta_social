"""Deterministic randomness for the engine (ported from ua-simulator).

Every stochastic draw comes from a substream keyed by (seed, tick, stage, key), so
stages are statistically independent yet reproducible from a given seed. Quanta's world
is real-time (not seed-reproducible end to end), but the *primitives* are reused: the
world seeds each tick's substreams from the tick index, and the property tests use the
*expectation* mode (stochastic=False) to assert exact numbers.
"""
import hashlib
import math
import random


def substream(seed: int, tick_index: int, stage: str, key: str = "") -> random.Random:
    """A private, reproducible Random stream for one (tick, stage, key)."""
    h = hashlib.blake2b(
        f"{seed}:{tick_index}:{stage}:{key}".encode(), digest_size=8
    ).digest()
    return random.Random(int.from_bytes(h, "big"))


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def binomial(n, p: float, rng: random.Random, stochastic: bool = True) -> int:
    """Number of successes in n trials at probability p.

    Expectation mode returns round(n*p). Stochastic mode uses a normal approximation
    for large n (fast, concentrated) and an exact count for small n.
    """
    n = int(round(n))
    p = _clamp(p, 0.0, 1.0)
    if n <= 0 or p <= 0.0:
        return 0
    if p >= 1.0:
        return n
    if not stochastic:
        return int(round(n * p))
    mean = n * p
    if mean >= 25 and n * (1 - p) >= 25:
        val = rng.gauss(mean, math.sqrt(n * p * (1 - p)))
        return int(_clamp(round(val), 0, n))
    return sum(1 for _ in range(n) if rng.random() < p)


def multinomial(n, weights: dict, rng: random.Random, stochastic: bool = True) -> dict:
    """Split n items across buckets given a weight dict.

    The result always sums to exactly n. Expectation mode distributes the integer
    remainder by largest fractional part (deterministic, no drift).
    """
    n = int(round(n))
    keys = list(weights.keys())
    if n <= 0:
        return {k: 0 for k in keys}

    total_w = sum(w for w in weights.values() if w > 0)
    if total_w <= 0:
        return {k: 0 for k in keys}

    if not stochastic:
        raw = {k: n * max(0.0, weights[k]) / total_w for k in keys}
        floored = {k: int(math.floor(raw[k])) for k in keys}
        remainder = n - sum(floored.values())
        by_frac = sorted(keys, key=lambda k: raw[k] - floored[k], reverse=True)
        for k in by_frac[:remainder]:
            floored[k] += 1
        return floored

    # Stochastic: sequential conditional binomials; the last bucket takes the remainder.
    result = {k: 0 for k in keys}
    remaining = n
    p_remaining = total_w
    for i, k in enumerate(keys):
        if remaining <= 0:
            break
        if i == len(keys) - 1:
            result[k] = remaining
            break
        w = max(0.0, weights[k])
        p = _clamp(w / p_remaining, 0.0, 1.0) if p_remaining > 0 else 0.0
        c = binomial(remaining, p, rng, stochastic=True)
        result[k] = c
        remaining -= c
        p_remaining -= w
    return result
