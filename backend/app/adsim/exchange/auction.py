"""run_auction — collect seat bids, filter for eligibility, rank, settle, fire notices.

Pure and stateless per call, so the world loop and the request path can both call it
concurrently. The returned AuctionResult carries everything the RTB Inspector shows:
the ranked eligible bids, the filtered bids *with reasons*, the winner, the clearing
price, and the notice log.
"""
from dataclasses import dataclass, field

from ..models.bid_request import BidRequest, Imp
from ..models.bid_response import Bid, SeatBid
from ..models.enums import AuctionType, LossReason
from .eligibility import filter_bid
from .notices import NoticeEvent, fire_loss, fire_win
from .settlement import SECOND_PRICE_INCREMENT_MICROS, settle


@dataclass
class RankedBid:
    bid: Bid
    seat: str


@dataclass
class FilteredBid:
    bid: Bid
    seat: str
    reason: LossReason


@dataclass
class AuctionResult:
    request: BidRequest
    imp: Imp
    auction_type: AuctionType
    floor_micros: int
    eligible: list[RankedBid]      # sorted desc by price
    filtered: list[FilteredBid]
    winner: RankedBid | None
    clearing_micros: int
    min_to_win_micros: int
    notices: list[NoticeEvent] = field(default_factory=list)

    @property
    def won(self) -> bool:
        return self.winner is not None


def run_auction(
    request: BidRequest,
    seat_bids: list[SeatBid],
    auction_type: int | None = None,
) -> AuctionResult:
    """Run a single-impression auction. `auction_type` overrides request.at if given."""
    imp = request.imp[0]
    floor = imp.bidfloor_micros
    at = AuctionType(auction_type) if auction_type is not None else AuctionType(request.at)

    eligible: list[RankedBid] = []
    filtered: list[FilteredBid] = []
    for sb in seat_bids:
        for bid in sb.bid:
            reason = filter_bid(bid, sb.seat, request, imp)
            if reason is None:
                eligible.append(RankedBid(bid, sb.seat))
            else:
                filtered.append(FilteredBid(bid, sb.seat, reason))

    eligible.sort(key=lambda rb: rb.bid.price_micros, reverse=True)
    prices = [rb.bid.price_micros for rb in eligible]
    clearing = settle(prices, floor, at)

    winner = eligible[0] if eligible else None
    min_to_win = (prices[0] + SECOND_PRICE_INCREMENT_MICROS) if prices else floor

    notices: list[NoticeEvent] = []
    if winner:
        notices += fire_win(request.id, winner.bid, winner.seat, clearing)
        for rb in eligible[1:]:
            notices += fire_loss(
                request.id, rb.bid, rb.seat, int(LossReason.LOST_TO_HIGHER_BID), min_to_win
            )
    for fb in filtered:
        notices += fire_loss(request.id, fb.bid, fb.seat, int(fb.reason), min_to_win)

    return AuctionResult(
        request=request,
        imp=imp,
        auction_type=at,
        floor_micros=floor,
        eligible=eligible,
        filtered=filtered,
        winner=winner,
        clearing_micros=clearing,
        min_to_win_micros=min_to_win,
        notices=notices,
    )
