from app.adsim.dsp.campaign import FreqCap, Targeting
from app.adsim.models.enums import BillingEvent, Objective, Pacing
from app.adsim.money import usd_to_micros
from app.adsim.simulation.delivery import run_tick
from app.adsim.simulation.segment_model import effective_ctr
from app.adsim.simulation.state import DeliveryState
from app.adsim.world import load_world

from ._factories import make_line

WORLD = load_world()


def test_delivery_conserves_the_funnel():
    st = DeliveryState()
    deltas = run_tick(
        WORLD, [make_line()], st,
        sim_seconds_per_tick=60, day_fraction=0.5, tick_index=1, stochastic=False,
    )
    assert deltas
    for d in deltas:
        assert 0 <= d.conversions <= d.clicks <= d.impressions <= d.auctions
        assert d.spend_micros >= 0
        assert d.revenue_micros >= 0


def test_even_pacing_never_exceeds_daily_budget():
    st = DeliveryState()
    line = make_line(budget_usd=500, pacing=Pacing.EVEN)
    for i in range(1, 121):
        run_tick(
            WORLD, [line], st,
            sim_seconds_per_tick=60, day_fraction=i / 120, tick_index=i, stochastic=False,
        )
        assert st.spent_today_micros.get("a1", 0) <= usd_to_micros(500)


def test_frequency_cap_bounds_cumulative_impressions():
    st = DeliveryState()
    line = make_line(
        budget_usd=1_000_000,
        targeting=Targeting(interests=frozenset({"education"})),
        freq_cap=FreqCap(impressions=1, per_days=1),
    )
    for i in range(1, 60):
        run_tick(
            WORLD, [line], st,
            sim_seconds_per_tick=600, day_fraction=1.0, tick_index=i, stochastic=False,
        )
    for (_campaign, seg_id), shown in st.freq_shown_today.items():
        assert shown <= WORLD.segments[seg_id].size  # cap = size * 1 impression/person


def test_learning_lift_raises_delivery():
    # Isolate learning from fatigue: two identical FRESH ticks (no accumulated impressions),
    # one with zero signal (start_lift) vs one fully trained (target_lift).
    line = make_line(
        objective=Objective.CONVERSIONS,
        bid_usd=40,  # $40 target CPA
        billing=BillingEvent.CPM,
        budget_usd=1_000_000,
        targeting=Targeting(interests=frozenset({"finance"})),
    )
    fresh = DeliveryState()
    trained = DeliveryState()
    trained.learning_signal["s1"] = WORLD.learning.threshold  # fully out of learning

    d_fresh = run_tick(
        WORLD, [line], fresh,
        sim_seconds_per_tick=600, day_fraction=1.0, tick_index=1, stochastic=False,
    )
    d_trained = run_tick(
        WORLD, [line], trained,
        sim_seconds_per_tick=600, day_fraction=1.0, tick_index=1, stochastic=False,
    )
    assert sum(d.conversions for d in d_trained) > sum(d.conversions for d in d_fresh)
    assert sum(d.impressions for d in d_trained) >= sum(d.impressions for d in d_fresh)


def test_conversions_accumulate_learning_signal():
    # Stochastic (seeded, deterministic): rare conversions accrue via Bernoulli draws, so
    # the campaign bootstraps out of the learning phase over ticks.
    st = DeliveryState()
    line = make_line(
        objective=Objective.CONVERSIONS, bid_usd=40, billing=BillingEvent.CPM,
        budget_usd=1_000_000, targeting=Targeting(interests=frozenset({"finance"})),
    )
    for i in range(1, 20):
        run_tick(
            WORLD, [line], st,
            sim_seconds_per_tick=600, day_fraction=1.0, tick_index=i, seed=0, stochastic=True,
        )
    assert st.learning_signal.get("s1", 0) > 0


def test_fatigue_lowers_ctr_as_frequency_rises():
    seg = next(s for s in WORLD.segment_list() if s.interest == "tech")
    fresh = effective_ctr(seg, relevant=False, cum_impressions=0, world=WORLD)
    worn = effective_ctr(seg, relevant=False, cum_impressions=seg.size * 10, world=WORLD)
    assert worn < fresh  # the same audience seeing the creative too often clicks less
