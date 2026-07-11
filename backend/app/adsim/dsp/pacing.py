"""Budget pacing and frequency capping — the delivery gates applied before the auction."""
from ..models.enums import Pacing


def pace_allowed_spend_micros(line, spent_today_micros: int, day_fraction: float) -> int:
    """How much this line may still spend right now.

    ASAP: whatever is left of the daily budget. EVEN: never outrun the day's elapsed
    fraction, so spend is smoothed across the sim-day.
    """
    remaining_daily = max(0, line.daily_budget_micros - spent_today_micros)
    if line.pacing == Pacing.ASAP:
        return remaining_daily
    target = int(line.daily_budget_micros * min(1.0, max(0.0, day_fraction)))
    return max(0, min(remaining_daily, target - spent_today_micros))


def freq_remaining_impressions(line, seg, shown_today: int) -> float:
    """Impressions still deliverable to a segment today under the frequency cap.
    inf when there is no cap."""
    if line.freq_cap is None:
        return float("inf")
    per_days = max(1, line.freq_cap.per_days)
    cap_total = seg.size * line.freq_cap.impressions / per_days
    return max(0.0, cap_total - shown_today)
