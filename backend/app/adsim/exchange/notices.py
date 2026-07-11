"""Notice lifecycle: win (nurl) -> billing (burl) -> loss (lurl).

Transport is stubbed, so "firing" a notice means recording an event with its URL macros
expanded. Spend is authoritative on the BILLING notice (burl), mirroring real accounting:
a win is not yet a billed impression. The winner's nurl/burl carry ${AUCTION_PRICE},
which the exchange expands to the clearing price here.
"""
from dataclasses import dataclass

from ..models import macros
from ..money import micros_to_usd


@dataclass
class NoticeEvent:
    kind: str        # "win" | "billing" | "loss"
    seat: str
    crid: str
    url: str         # the expanded URL that "fired"
    billed: bool = False  # True on the billing notice (spend accrues here)


def _base_ctx(req_id: str, bid, seat: str) -> dict:
    return {
        macros.AUCTION_ID: req_id,
        macros.AUCTION_BID_ID: bid.id,
        macros.AUCTION_IMP_ID: bid.impid,
        macros.AUCTION_SEAT_ID: seat,
        macros.AUCTION_AD_ID: bid.adid or bid.crid,
        macros.AUCTION_CURRENCY: "USD",
    }


def fire_win(req_id: str, bid, seat: str, clearing_micros: int) -> list[NoticeEvent]:
    """Winner: fire nurl then burl, with ${AUCTION_PRICE} = clearing CPM."""
    ctx = _base_ctx(req_id, bid, seat)
    ctx[macros.AUCTION_PRICE] = f"{micros_to_usd(clearing_micros):.2f}"
    events: list[NoticeEvent] = []
    if bid.nurl:
        events.append(NoticeEvent("win", seat, bid.crid, macros.expand(bid.nurl, ctx)))
    if bid.burl:
        events.append(
            NoticeEvent("billing", seat, bid.crid, macros.expand(bid.burl, ctx), billed=True)
        )
    return events


def fire_loss(
    req_id: str, bid, seat: str, loss_reason: int, min_to_win_micros: int
) -> list[NoticeEvent]:
    """Loser: fire lurl with ${AUCTION_LOSS} and ${AUCTION_MIN_TO_WIN}."""
    if not bid.lurl:
        return []
    ctx = _base_ctx(req_id, bid, seat)
    ctx[macros.AUCTION_LOSS] = int(loss_reason)
    ctx[macros.AUCTION_MIN_TO_WIN] = f"{micros_to_usd(min_to_win_micros):.2f}"
    return [NoticeEvent("loss", seat, bid.crid, macros.expand(bid.lurl, ctx))]
