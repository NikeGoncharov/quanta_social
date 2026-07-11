"""The glass-box 'why' — plain-language reasons a campaign delivers the way it does.

Instead of leaving the advertiser to fly by instruments, `diagnose` names the single most
binding limiter (audience / budget / frequency / bid / learning) and how to fix it. The
cabinet renders this on every ad set.
"""
from dataclasses import dataclass

# Heuristic thresholds (tunable).
NARROW_AUDIENCE = 50_000
LOW_WIN_RATE = 0.15
BUDGET_SPENT = 0.98
FREQ_SATURATED = 0.9


@dataclass
class Diagnosis:
    delivering: bool
    limiter: str | None   # audience | budget | frequency | bid | learning | None
    headline: str
    detail: str


def diagnose(
    *,
    win_rate: float | None,
    audience_size: int,
    spent_today_micros: int,
    daily_budget_micros: int,
    freq_saturation: float,   # 0..1, share of the audience at the frequency cap
    in_learning: bool,
    signal_to_exit: float = 0.0,
) -> Diagnosis:
    budget_util = (spent_today_micros / daily_budget_micros) if daily_budget_micros else 0.0

    if audience_size < NARROW_AUDIENCE:
        return Diagnosis(
            False, "audience",
            "Audience too narrow",
            f"Only ~{audience_size:,} people match this targeting. Broaden interests or geos to give delivery room.",
        )
    if budget_util >= BUDGET_SPENT:
        return Diagnosis(
            False, "budget",
            "Budget-limited",
            "The daily budget is spent — raise it (or the bid) to win more auctions.",
        )
    if freq_saturation >= FREQ_SATURATED:
        return Diagnosis(
            False, "frequency",
            "Frequency-capped",
            "Most of the audience has hit the frequency cap today. Raise the cap or widen the audience.",
        )
    if win_rate is not None and win_rate < LOW_WIN_RATE:
        return Diagnosis(
            False, "bid",
            "Bid too low",
            f"Winning only {win_rate:.0%} of auctions — competitors are outbidding you. Raise the bid to lift win rate.",
        )
    if in_learning:
        return Diagnosis(
            True, "learning",
            "In learning",
            f"Optimization is still training — about {signal_to_exit:.0f} more conversions to exit the learning phase and stabilize.",
        )
    return Diagnosis(True, None, "Delivering", "No limiter detected — the campaign is delivering normally.")
