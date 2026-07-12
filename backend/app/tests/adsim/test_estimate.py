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


def test_estimate_tracks_a_stochastic_run_tick_day():
    """The glass-box contract: because the estimate replays run_tick, its daily totals must
    land in the same ballpark as a real (stochastic) full-resolution run_tick day — not the
    several-fold gap the old flat-snapshot closed form had, and not zero.

    Ground truth is a STOCHASTIC day at 30-sim-second ticks: expectation mode at that fine a
    resolution would round every tiny per-tick value to zero, but the world draws binomially
    and accumulates, so this is the honest reference."""
    from app.adsim.simulation.delivery import run_tick
    from app.adsim.simulation.state import DeliveryState

    world = load_world()
    line = _line(objective=Objective.CONVERSIONS, bid_usd=40, budget_usd=100000)  # roomy: not budget-bound
    est = estimate_delivery(world, line)

    st = DeliveryState()
    steps = 2880
    spt = 86_400 / steps
    imps = clicks = convs = 0
    for i in range(steps):
        for d in run_tick(world, [line], st, sim_seconds_per_tick=spt,
                          day_fraction=min(1.0, (i + 1) / steps), tick_index=i + 1, seed=7, stochastic=True):
            imps += d.impressions
            clicks += d.clicks
            convs += d.conversions
    assert imps > 0 and convs > 0
    # Same ballpark (the replay integrates fatigue + the learning ramp); generous bounds keep
    # it robust to the stochastic sample and the coarse-step resolution difference.
    assert 0.5 <= est["impressions"] / imps <= 1.7
    assert 0.4 <= est["conversions"] / convs <= 2.2


def test_estimate_honors_frequency_cap():
    """A tight frequency cap must cut the estimate, exactly as it caps delivery in run_tick —
    the old closed form ignored the cap entirely."""
    from app.adsim.dsp.campaign import FreqCap

    world = load_world()
    base = _line(objective=Objective.AWARENESS, bid_usd=8, budget_usd=1_000_000,
                 targeting=Targeting(interests=frozenset({"tech"})))
    uncapped = estimate_delivery(world, base)
    capped = estimate_delivery(world, replace_freq(base, FreqCap(impressions=1, per_days=1)))
    assert capped["impressions"] < uncapped["impressions"]
    # With ~20 opportunities/person/day, a 1/day cap is a hard, large reduction.
    assert capped["impressions"] <= uncapped["impressions"] * 0.5


def replace_freq(line, freq_cap):
    from dataclasses import replace
    return replace(line, freq_cap=freq_cap)
