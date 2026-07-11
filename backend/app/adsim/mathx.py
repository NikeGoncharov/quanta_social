"""Small numeric helpers encoding the engine's core dynamics — plain, testable functions.

  win_rate       bidding higher wins a larger share of auctions, saturating;
  fatigue_factor CTR decays as a segment sees the same creative too often;
  cpm_paid_*     what you actually pay per won impression under each auction type.
"""
import math


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def win_rate(bid_micros: int, reference_micros: int) -> float:
    """Share of auctions won: bid / (bid + market reference). Higher bid -> more wins,
    with diminishing returns. Zero bid never wins; zero reference always wins."""
    if bid_micros <= 0:
        return 0.0
    if reference_micros <= 0:
        return 1.0
    return bid_micros / (bid_micros + reference_micros)


def cpm_paid_first_price(bid_micros: int) -> int:
    """First-price: you pay your own bid on every win."""
    return bid_micros


def cpm_paid_second_price(bid_micros: int, reference_micros: int, wr: float) -> int:
    """Second-price aggregate approximation: you pay near the market reference, rising a
    little as you win more of the marginal (pricier) auctions, never above your bid."""
    paid = reference_micros * (0.6 + 0.8 * clamp(wr, 0.0, 1.0))
    return int(min(bid_micros, paid))


def fatigue_factor(frequency: float, free_frequency: float, k: float) -> float:
    """Multiplier on CTR from ad fatigue. 1.0 until a segment has seen the creative
    `free_frequency` times per person; then it decays toward 0 as frequency climbs."""
    over = max(0.0, frequency - free_frequency)
    return 1.0 / (1.0 + k * over)
