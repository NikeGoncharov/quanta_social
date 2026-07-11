"""Turn an active line into an OpenRTB SeatBid, and synthesize phantom competitor bids.

Used by the materialized path (real feed views + the sampled auctions in the RTB Inspector)
— NOT by the statistical aggregate, which never builds per-impression objects.
"""
import math

from ..dsp.strategy import effective_bid_micros
from ..models.bid_response import Bid, SeatBid
from ..models.enums import MarkupType

_WIN = "https://quanta-social.com/rtb/win?imp=${AUCTION_IMP_ID}&price=${AUCTION_PRICE}"
_BILL = "https://quanta-social.com/rtb/bill?imp=${AUCTION_IMP_ID}&price=${AUCTION_PRICE}"
_LOSS = "https://quanta-social.com/rtb/loss?imp=${AUCTION_IMP_ID}&reason=${AUCTION_LOSS}&mtw=${AUCTION_MIN_TO_WIN}"


def build_seatbid(line, request, ctr: float, cvr: float) -> SeatBid:
    imp = request.imp[0]
    price = effective_bid_micros(line, ctr, cvr)
    bid = Bid(
        id=f"bid-{line.ad_id}",
        impid=imp.id,
        price_micros=price,
        nurl=_WIN,
        burl=_BILL,
        lurl=_LOSS,
        adm=line.creative.to_native_markup(),
        adomain=[line.adomain] if line.adomain else [],
        cid=line.campaign_id,
        crid=line.ad_id,
        cat=list(line.cats),
        mtype=int(MarkupType.NATIVE),
    )
    return SeatBid(seat=line.seat, bid=[bid])


def phantom_seat_bids(world, segment, request, *, n: int, rng, spread: float = 0.35) -> list[SeatBid]:
    """Draw up to n synthetic competitor bids around the segment's reference bid — this is
    what makes a lone campaign face real price pressure, and populates the inspector."""
    imp = request.imp[0]
    ref = int(segment.reference_bid_micros * world.economy.market_density)
    chosen = rng.sample(list(world.phantom_seats), min(n, len(world.phantom_seats)))
    seats: list[SeatBid] = []
    for i, ps in enumerate(chosen):
        mult = math.exp(rng.gauss(0.0, spread))  # lognormal dispersion
        price = max(0, int(ref * ps.aggressiveness * mult))
        domain = ps.name.split()[0].lower() + ".example"
        bid = Bid(
            id=f"ph-{i}",
            impid=imp.id,
            price_micros=price,
            nurl=f"https://{domain}/win?price=" + "${AUCTION_PRICE}",
            lurl=f"https://{domain}/loss?reason=" + "${AUCTION_LOSS}",
            adomain=[domain],
            cid=f"ph-cmp-{i}",
            crid=f"ph-cr-{i}",
            mtype=int(MarkupType.NATIVE),
        )
        seats.append(SeatBid(seat=ps.name, bid=[bid]))
    return seats
