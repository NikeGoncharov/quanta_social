"""Budget pacing and frequency capping — the delivery gates applied before the auction."""
from ..models.enums import Pacing

# ASAP is front-loaded but velocity-bounded: it may run up to ASAP_RATE× the even pace
# (so it finishes well before the day ends) plus a small headstart it can spend immediately.
# The bound matters because a fresh daily budget resets at midnight — without it, ASAP dumps
# the entire budget into the first tick after the reset, which at fast sim speeds (one tick
# spans many sim-minutes) shows up as a once-a-day spike on the delivery charts. Real
# accelerated delivery is likewise rate-limited, never a whole day's budget in an instant.
ASAP_RATE = 4.0        # multiple of the even (day-fraction) pace
ASAP_HEADSTART = 0.05  # fraction of the daily budget deliverable in the very first tick


def pace_allowed_spend_micros(line, spent_today_micros: int, day_fraction: float) -> int:
    """How much this line may still spend right now.

    EVEN: never outrun the day's elapsed fraction, so spend is smoothed across the sim-day.
    ASAP: front-loaded — up to ASAP_RATE× the even target (plus a small headstart) — so it
    finishes early but never dumps the whole budget in a single tick.
    """
    remaining_daily = max(0, line.daily_budget_micros - spent_today_micros)
    df = min(1.0, max(0.0, day_fraction))
    frac = min(1.0, ASAP_HEADSTART + df * ASAP_RATE) if line.pacing == Pacing.ASAP else df
    target = int(line.daily_budget_micros * frac)
    return max(0, min(remaining_daily, target - spent_today_micros))


def freq_remaining_impressions(line, seg, shown_today: int) -> float:
    """Impressions still deliverable to a segment today under the frequency cap.
    inf when there is no cap."""
    if line.freq_cap is None:
        return float("inf")
    per_days = max(1, line.freq_cap.per_days)
    cap_total = seg.size * line.freq_cap.impressions / per_days
    return max(0.0, cap_total - shown_today)
