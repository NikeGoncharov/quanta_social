"""Bid eligibility filtering — brand-safety and auction hygiene.

A bid is rejected (and never ranked) if it is below the floor, targets the wrong
impression, or trips a block list (bcat / badv / wseat). Returns the LossReason so the
RTB Inspector can show *why* each bid was filtered.
"""
from ..models.bid_request import BidRequest, Imp
from ..models.bid_response import Bid
from ..models.enums import LossReason


def filter_bid(bid: Bid, seat: str, req: BidRequest, imp: Imp) -> LossReason | None:
    """Return a LossReason if the bid is ineligible, else None."""
    if bid.impid != imp.id:
        return LossReason.INTERNAL_ERROR

    if bid.price_micros < imp.bidfloor_micros:
        return LossReason.BELOW_AUCTION_FLOOR

    if req.bcat and (set(bid.cat) & set(req.bcat)):
        return LossReason.CREATIVE_FILTERED_CATEGORY

    if req.badv and (set(bid.adomain) & set(req.badv)):
        return LossReason.CREATIVE_FILTERED_ADVERTISER

    # Seat allow-list: if present, the bid's seat must be on it.
    if req.wseat and seat not in set(req.wseat):
        return LossReason.CREATIVE_FILTERED_ADVERTISER

    return None
