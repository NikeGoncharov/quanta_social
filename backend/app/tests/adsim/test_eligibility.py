from app.adsim.exchange.eligibility import filter_bid
from app.adsim.models.bid_request import BidRequest, Imp, NativeRequest
from app.adsim.models.bid_response import Bid
from app.adsim.models.enums import LossReason
from app.adsim.money import usd_to_micros


def _req(**kw) -> BidRequest:
    imp = Imp(id="1", native=NativeRequest(), bidfloor_micros=usd_to_micros(1))
    return BidRequest(id="req1", imp=[imp], **kw)


def _bid(price=usd_to_micros(2), impid="1", cat=None, adomain=None) -> Bid:
    return Bid(id="b", impid=impid, price_micros=price, cat=cat or [], adomain=adomain or [])


def test_eligible_bid_passes():
    req = _req()
    assert filter_bid(_bid(), "seatA", req, req.imp[0]) is None


def test_below_floor_filtered():
    req = _req()
    assert filter_bid(_bid(price=usd_to_micros(0.5)), "seatA", req, req.imp[0]) == (
        LossReason.BELOW_AUCTION_FLOOR
    )


def test_blocked_category_filtered():
    req = _req(bcat=["IAB25"])
    assert filter_bid(_bid(cat=["IAB25"]), "seatA", req, req.imp[0]) == (
        LossReason.CREATIVE_FILTERED_CATEGORY
    )


def test_blocked_advertiser_domain_filtered():
    req = _req(badv=["evil.com"])
    assert filter_bid(_bid(adomain=["evil.com"]), "seatA", req, req.imp[0]) == (
        LossReason.CREATIVE_FILTERED_ADVERTISER
    )


def test_seat_allowlist():
    req = _req(wseat=["allowed"])
    assert filter_bid(_bid(), "other", req, req.imp[0]) is not None
    assert filter_bid(_bid(), "allowed", req, req.imp[0]) is None


def test_wrong_impid_filtered():
    req = _req()
    assert filter_bid(_bid(impid="999"), "seatA", req, req.imp[0]) == LossReason.INTERNAL_ERROR
