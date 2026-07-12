"""estimate_delivery must obey the funnel and the budget cap, and move monotonically with
the bid — it is the number the wizard promises, so it has to behave like run_tick."""
from app.adsim.dsp.campaign import Line, Targeting
from app.adsim.metrics.estimate import estimate_delivery
from app.adsim.models.enums import OBJECTIVE_BILLING, Objective
from app.adsim.money import usd_to_micros
from app.adsim.world import load_world
from app.adsim.dsp.targeting import audience_size


def _line(*, objective=Objective.TRAFFIC, bid_usd=1.0, budget_usd=1000.0, targeting=None):
    obj = objective
    return Line(
        ad_id="e", ad_set_id="e", campaign_id="e", account_id="e", seat="e",
        objective=obj, bid_micros=usd_to_micros(bid_usd), billing_event=OBJECTIVE_BILLING[obj],
        targeting=targeting or Targeting(interests=frozenset({"tech"})),
        daily_budget_micros=usd_to_micros(budget_usd), baseline_conv_value_micros=usd_to_micros(60),
        creative=None,  # estimate never touches the creative
    )


def test_estimate_funnel_holds():
    world = load_world()
    est = estimate_delivery(world, _line(objective=Objective.CONVERSIONS, bid_usd=40, budget_usd=1000))
    assert est["conversions"] <= est["clicks"] <= est["impressions"] <= est["auctions"]
    assert est["audience"] == audience_size(_line().targeting, world)


def test_estimate_respects_budget_cap():
    world = load_world()
    # A tiny budget against a rich audience -> the estimate must clamp spend to the budget.
    est = estimate_delivery(world, _line(bid_usd=2.0, budget_usd=5.0))
    assert est["budget_capped"] is True
    assert est["spend"] <= 5.0 + 0.01


def test_estimate_monotonic_in_bid():
    world = load_world()
    # Broad, generous budget so budget capping doesn't mask the bid effect.
    low = estimate_delivery(world, _line(objective=Objective.AWARENESS, bid_usd=3.0, budget_usd=100000))
    high = estimate_delivery(world, _line(objective=Objective.AWARENESS, bid_usd=9.0, budget_usd=100000))
    assert high["win_rate"] >= low["win_rate"]
    assert high["impressions"] >= low["impressions"]


def test_narrow_targeting_smaller_audience():
    world = load_world()
    broad = estimate_delivery(world, _line(targeting=Targeting(interests=frozenset({"tech", "gaming", "finance"}))))
    narrow = estimate_delivery(world, _line(targeting=Targeting(interests=frozenset({"finance"}), geos=frozenset({"USA"}))))
    assert broad["audience"] > narrow["audience"]
