"""Bid strategy: turn a line's bid into an eCPM to enter the auction with.

The bid's *meaning* follows the objective:
  Awareness   -> bid is a CPM (enter it directly)
  Traffic     -> bid is a CPC  -> eCPM = CPC * CTR * 1000
  Engagement  -> bid is a cost-per-engagement -> eCPM = bid * engagement_rate * 1000
  Conversions -> bid is a target CPA -> eCPM = CPA * (CTR*CVR) * 1000

For Conversions this couples the learning phase to delivery: as CVR ramps, the eCPM rises,
the campaign wins more, and delivery accelerates — the classic "exiting learning" curve.
"""
from ..money import cpa_to_ecpm_micros, cpc_to_ecpm_micros
from ..models.enums import Objective


def effective_bid_micros(line, ctr: float, cvr: float) -> int:
    """eCPM (micros) the line bids into the auction, given the segment's effective CTR and
    per-click CVR."""
    obj = line.objective
    if obj == Objective.AWARENESS:
        return line.bid_micros  # already a CPM
    if obj in (Objective.TRAFFIC, Objective.ENGAGEMENT):
        return cpc_to_ecpm_micros(line.bid_micros, ctr)
    if obj == Objective.CONVERSIONS:
        conv_per_impression = ctr * cvr
        return cpa_to_ecpm_micros(line.bid_micros, conv_per_impression)
    return line.bid_micros
