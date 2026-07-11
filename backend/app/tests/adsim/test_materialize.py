import random

from app.adsim.dsp.campaign import Targeting
from app.adsim.materialize import sampled_auction
from app.adsim.world import load_world

from ._factories import make_line

WORLD = load_world()


def test_sampled_auction_produces_a_full_trace():
    seg = WORLD.segments["tech|USA|25-34|F"]
    line = make_line(bid_usd=8, targeting=Targeting(interests=frozenset({"tech"})))
    req, res = sampled_auction(
        WORLD, seg, line, ctr=0.02, cvr=0.04, rng=random.Random(0), n_phantoms=4, request_id="auc-1"
    )
    assert res.won
    assert res.clearing_micros >= WORLD.economy.default_floor_micros
    # 1 real seat + up to 4 phantom seats all accounted for (eligible or filtered)
    assert len(res.eligible) + len(res.filtered) >= 3
    # the winner fired at least one notice
    assert res.notices


def test_bid_request_serializes_to_openrtb_shape():
    seg = WORLD.segments["finance|USA|25-34|F"]
    line = make_line(bid_usd=10, targeting=Targeting(interests=frozenset({"finance"})))
    req, _ = sampled_auction(WORLD, seg, line, ctr=0.01, cvr=0.05, rng=random.Random(1))
    d = req.to_dict()
    assert d["site"]["domain"] == "quanta-social.com"
    assert d["imp"][0]["bidfloor"] == 1.0            # micros serialized back to USD float
    assert d["imp"][0]["native"]["ver"] == "1.2"
    assert d["user"]["data"][0]["segment"][0]["id"] == "finance"
    assert d["at"] == WORLD.economy.auction_type


def test_winning_native_markup_carries_creative_assets():
    seg = WORLD.segments["tech|USA|25-34|F"]
    line = make_line(bid_usd=12, targeting=Targeting(interests=frozenset({"tech"})))
    _, res = sampled_auction(WORLD, seg, line, ctr=0.03, cvr=0.05, rng=random.Random(2), n_phantoms=2)
    # With a strong bid and few weak phantoms, the real advertiser should win here.
    assert res.won and res.winner.seat == line.seat
    adm = res.winner.bid.adm
    assert adm and adm["assets"][0]["title"]["text"] == "Great product"
