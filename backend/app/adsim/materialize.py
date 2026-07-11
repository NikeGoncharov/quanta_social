"""Assemble a full, materialized auction: build the BidRequest, the advertiser's real
SeatBid, and phantom competitor bids, then run the exchange. Returns (request, result) —
exactly what the RTB Inspector renders and what a real feed view records.
"""
from .dsp.bidder import build_seatbid, phantom_seat_bids
from .exchange import run_auction
from .ssp.request_gen import build_bid_request


def sampled_auction(
    world,
    segment,
    line,
    *,
    ctr: float,
    cvr: float,
    rng,
    n_phantoms: int = 4,
    request_id: str = "sample",
    user_id: str = "u-synthetic",
):
    req = build_bid_request(
        request_id=request_id,
        world_segment=segment,
        user_id=user_id,
        floor_micros=world.economy.default_floor_micros,
        auction_type=world.economy.auction_type,
    )
    real = build_seatbid(line, req, ctr, cvr)
    phantoms = phantom_seat_bids(world, segment, req, n=n_phantoms, rng=rng)
    result = run_auction(req, [real] + phantoms)
    return req, result
