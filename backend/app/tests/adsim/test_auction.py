from app.adsim.exchange import run_auction
from app.adsim.exchange.settlement import SECOND_PRICE_INCREMENT_MICROS
from app.adsim.models.bid_request import BidRequest, Imp, NativeRequest
from app.adsim.models.bid_response import Bid, SeatBid
from app.adsim.models.enums import AuctionType, LossReason
from app.adsim.money import usd_to_micros


def _imp(floor=usd_to_micros(1)) -> Imp:
    return Imp(id="1", native=NativeRequest(), bidfloor_micros=floor)


def test_first_price_auction_end_to_end():
    req = BidRequest(id="reqX", imp=[_imp()], at=int(AuctionType.FIRST_PRICE), badv=["evil.com"])
    seat_bids = [
        SeatBid(seat="acme", bid=[Bid(id="a", impid="1", price_micros=usd_to_micros(4))]),
        SeatBid(
            seat="globex",
            bid=[
                Bid(
                    id="g",
                    impid="1",
                    price_micros=usd_to_micros(6),
                    crid="c2",
                    nurl="win?p=${AUCTION_PRICE}",
                    burl="bill?p=${AUCTION_PRICE}",
                )
            ],
        ),
        # highest raw bid but blocked by badv -> filtered, must not win:
        SeatBid(seat="evil", bid=[Bid(id="e", impid="1", price_micros=usd_to_micros(9), adomain=["evil.com"])]),
        # below floor -> filtered:
        SeatBid(seat="low", bid=[Bid(id="l", impid="1", price_micros=usd_to_micros(0.5))]),
    ]
    res = run_auction(req, seat_bids)

    assert res.won
    assert res.winner.seat == "globex"
    assert res.clearing_micros == usd_to_micros(6)  # first price = own bid

    reasons = {fb.bid.id: fb.reason for fb in res.filtered}
    assert reasons["e"] == LossReason.CREATIVE_FILTERED_ADVERTISER
    assert reasons["l"] == LossReason.BELOW_AUCTION_FLOOR

    billing = [e for e in res.notices if e.billed]
    assert billing and "p=6.00" in billing[0].url


def test_second_price_auction_pays_second_plus_increment():
    req = BidRequest(id="reqY", imp=[_imp()], at=int(AuctionType.SECOND_PRICE_PLUS))
    seat_bids = [
        SeatBid(seat="a", bid=[Bid(id="a", impid="1", price_micros=usd_to_micros(5))]),
        SeatBid(seat="b", bid=[Bid(id="b", impid="1", price_micros=usd_to_micros(3))]),
    ]
    res = run_auction(req, seat_bids)
    assert res.winner.seat == "a"
    assert res.clearing_micros == usd_to_micros(3) + SECOND_PRICE_INCREMENT_MICROS


def test_no_eligible_bids_no_winner():
    req = BidRequest(id="r", imp=[_imp(floor=usd_to_micros(5))])
    seat_bids = [SeatBid(seat="a", bid=[Bid(id="a", impid="1", price_micros=usd_to_micros(1))])]
    res = run_auction(req, seat_bids)
    assert not res.won
    assert res.clearing_micros == 0
    assert res.filtered[0].reason == LossReason.BELOW_AUCTION_FLOOR
