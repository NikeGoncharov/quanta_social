from app.adsim.exchange.notices import fire_loss, fire_win
from app.adsim.models.bid_response import Bid
from app.adsim.models.enums import LossReason
from app.adsim.money import usd_to_micros


def test_win_expands_auction_price_and_bills_on_burl():
    bid = Bid(
        id="b1",
        impid="1",
        price_micros=usd_to_micros(5),
        crid="cr1",
        nurl="https://dsp/win?p=${AUCTION_PRICE}&imp=${AUCTION_IMP_ID}",
        burl="https://dsp/bill?p=${AUCTION_PRICE}",
    )
    events = fire_win("req1", bid, "seatA", clearing_micros=usd_to_micros(3))
    win = next(e for e in events if e.kind == "win")
    assert "p=3.00" in win.url and "imp=1" in win.url
    bill = next(e for e in events if e.kind == "billing")
    assert bill.billed is True
    assert "p=3.00" in bill.url  # spend accrues off burl at the clearing price


def test_loss_expands_loss_reason_and_min_to_win():
    bid = Bid(
        id="b2",
        impid="1",
        price_micros=usd_to_micros(2),
        lurl="https://dsp/loss?r=${AUCTION_LOSS}&min=${AUCTION_MIN_TO_WIN}",
    )
    events = fire_loss("req1", bid, "seatB", int(LossReason.LOST_TO_HIGHER_BID), usd_to_micros(5))
    assert len(events) == 1
    assert "r=102" in events[0].url and "min=5.00" in events[0].url


def test_no_urls_no_events():
    bid = Bid(id="b3", impid="1", price_micros=usd_to_micros(2))
    assert fire_win("r", bid, "s", usd_to_micros(1)) == []
    assert fire_loss("r", bid, "s", 100, usd_to_micros(1)) == []
