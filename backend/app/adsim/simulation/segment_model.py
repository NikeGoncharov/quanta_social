"""How a segment behaves for a given line: effective CTR/CVR after relevance, fatigue and
the learning lift, plus the per-conversion value."""
from ..mathx import clamp, fatigue_factor


def frequency(cum_impressions: int, seg) -> float:
    """Average impressions per person in the segment so far (drives fatigue)."""
    return cum_impressions / seg.size if seg.size > 0 else 0.0


def effective_ctr(seg, relevant: bool, cum_impressions: int, world) -> float:
    ctr = seg.base_ctr
    if relevant:
        ctr *= world.relevance_uplift
    ctr *= fatigue_factor(
        frequency(cum_impressions, seg), world.fatigue.free_frequency, world.fatigue.k
    )
    return clamp(ctr, 0.0, 1.0)


def effective_cvr(seg, relevant: bool, learning_lift_value: float, world) -> float:
    cvr = seg.base_cvr
    if relevant:
        # Relevance helps CVR too, but half as strongly as CTR (interest -> intent, weaker).
        cvr *= 1.0 + (world.relevance_uplift - 1.0) * 0.5
    cvr *= learning_lift_value
    return clamp(cvr, 0.0, 1.0)


def conversion_value_micros(line, seg) -> int:
    """Advertiser's baseline conversion value scaled by the segment's value multiplier
    (finance/autos audiences convert to higher-value orders)."""
    return int(line.baseline_conv_value_micros * seg.value_multiplier)
