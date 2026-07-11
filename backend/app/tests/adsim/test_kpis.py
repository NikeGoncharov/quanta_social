from app.adsim.metrics.kpis import cpm_micros, ctr, cvr, roas, rollup
from app.adsim.money import usd_to_micros
from app.adsim.simulation.delivery import SegmentDelta


def test_basic_ratios():
    assert ctr(10, 1000) == 0.01
    assert cvr(2, 10) == 0.2
    assert ctr(1, 0) is None  # undefined -> None, not a fake 0
    assert roas(usd_to_micros(200), usd_to_micros(100)) == 2.0


def test_cpm_from_spend_and_impressions():
    # $50 over 10,000 impressions -> $5 CPM
    assert cpm_micros(usd_to_micros(50), 10_000) == usd_to_micros(5)


def _delta(interest, geo, gender, **k):
    base = dict(
        ad_id="a", ad_set_id="s", campaign_id="c", account_id="acc",
        interest=interest, geo=geo, age_band="25-34", gender=gender,
        auctions=0, impressions=0, clicks=0, conversions=0, spend_micros=0, revenue_micros=0,
    )
    base.update(k)
    return SegmentDelta(**base)


def test_rollup_and_to_dict():
    d1 = _delta("tech", "USA", "F", auctions=1000, impressions=500, clicks=10, conversions=2,
                spend_micros=usd_to_micros(5), revenue_micros=usd_to_micros(20))
    d2 = _delta("tech", "GBR", "M", auctions=500, impressions=250, clicks=5, conversions=1,
                spend_micros=usd_to_micros(3), revenue_micros=usd_to_micros(10))
    k = rollup([d1, d2])
    assert k.impressions == 750 and k.clicks == 15 and k.conversions == 3
    out = k.to_dict()
    assert out["win_rate"] == 750 / 1500
    assert out["roas"] == usd_to_micros(30) / usd_to_micros(8)
    assert out["spend"] == 8.0
