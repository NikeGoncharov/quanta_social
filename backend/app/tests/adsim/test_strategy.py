from app.adsim.dsp.strategy import effective_bid_micros
from app.adsim.models.enums import BillingEvent, Objective
from app.adsim.money import usd_to_micros

from ._factories import make_line


def test_awareness_bid_is_a_cpm():
    line = make_line(objective=Objective.AWARENESS, bid_usd=5, billing=BillingEvent.CPM)
    assert effective_bid_micros(line, ctr=0.01, cvr=0.03) == usd_to_micros(5)


def test_traffic_cpc_becomes_ecpm():
    line = make_line(objective=Objective.TRAFFIC, bid_usd=1, billing=BillingEvent.CPC)
    # eCPM = CPC * CTR * 1000 = 1 * 0.02 * 1000 = $20
    assert effective_bid_micros(line, ctr=0.02, cvr=0.0) == usd_to_micros(20)


def test_conversions_target_cpa_becomes_ecpm():
    line = make_line(objective=Objective.CONVERSIONS, bid_usd=20, billing=BillingEvent.CPM)
    # conv/impression = ctr*cvr = 0.01*0.05 = 0.0005 -> eCPM = 20 * 0.0005 * 1000 = $10
    assert effective_bid_micros(line, ctr=0.01, cvr=0.05) == usd_to_micros(10)


def test_higher_cvr_raises_conversion_bid():
    line = make_line(objective=Objective.CONVERSIONS, bid_usd=20, billing=BillingEvent.CPM)
    low = effective_bid_micros(line, ctr=0.01, cvr=0.02)
    high = effective_bid_micros(line, ctr=0.01, cvr=0.06)
    assert high > low  # learning that lifts CVR raises the bid
