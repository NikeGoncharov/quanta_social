"""Runtime unit tests: the world loop's tick/flush/control behavior, driven by hand."""
import pytest

from app.adsim.models.enums import LEARNING_OBJECTIVES
from app.adsim.world import load_world
from app.sim import persistence
from app.sim.runtime import SimRuntime
from app.sim.seed import seed_lines


async def _fresh_runtime(session_maker):
    rt = SimRuntime(load_world(), seed_lines(), session_maker=session_maker)
    await rt._load_or_init_control()
    return rt


async def test_step_produces_delivery_buckets(sim_runtime):
    for _ in range(30):
        sim_runtime.step_once()
    await sim_runtime.flush(final=True)

    points = await sim_runtime.delivery_series(window=500)
    assert points, "expected some delivery buckets after 30 ticks"
    total_imps = sum(p["impressions"] for p in points)
    assert total_imps > 0
    # Buckets are ordered ascending in sim time.
    assert points == sorted(points, key=lambda p: p["t"])


async def test_metrics_funnel_holds(sim_runtime):
    """conversions <= clicks <= impressions <= auctions, per bucket."""
    for _ in range(40):
        sim_runtime.step_once()
    await sim_runtime.flush(final=True)
    for p in await sim_runtime.delivery_series(window=500):
        assert p["conversions"] <= p["clicks"] <= p["impressions"] <= p["auctions"]


async def test_budget_never_exceeded(sim_runtime):
    """Even across many ticks the per-line daily spend stays within budget."""
    for _ in range(60):
        sim_runtime.step_once()
    for ln in sim_runtime.lines:
        spent = sim_runtime.state.spent_today_micros.get(ln.ad_id, 0)
        assert spent <= ln.daily_budget_micros + 1  # +1 for integer rounding slack


async def test_auction_samples_captured(sim_runtime):
    for _ in range(24):  # sampling every 3rd tick -> ~8 samples
        sim_runtime.step_once()
    await sim_runtime.flush(final=True)

    samples = await sim_runtime.list_samples(limit=100)
    assert samples, "expected captured auction samples"
    detail = await sim_runtime.get_sample(samples[0]["id"])
    assert detail is not None
    # A recognizable OpenRTB request shape.
    req = detail["request"]
    assert "imp" in req and req["at"] in (1, 2) and req["cur"] == ["USD"]
    assert "eligible" in detail["bids"] and "filtered" in detail["bids"]


async def test_market_density_control_rebuilds_world(sim_runtime):
    before = sim_runtime.world.economy.market_density
    await sim_runtime.apply_control(market_density=2.5)
    assert sim_runtime.world.economy.market_density == 2.5
    assert sim_runtime.status()["market_density"] == 2.5
    assert sim_runtime.world.economy.market_density != before

    # Density persists to the DB and reloads.
    fresh = SimRuntime(sim_runtime.world, sim_runtime.lines, session_maker=sim_runtime.session_maker)
    await fresh._load_or_init_control()
    assert fresh.control.market_density == 2.5


async def test_density_raises_clearing_price(sim_runtime):
    """More competition (higher density) should not lower the clearing price of a win."""
    low = await sim_runtime.replay(ad_id="seed-nimbus-ad", segment_key="tech|USA|25-34|F")
    await sim_runtime.apply_control(market_density=3.0)
    high = await sim_runtime.replay(ad_id="seed-nimbus-ad", segment_key="tech|USA|25-34|F")
    # Both are valid auctions; with denser competition the min-to-win rises.
    assert high["min_to_win"] >= low["min_to_win"] or high["floor"] == low["floor"]


async def test_pause_resume_control(sim_runtime):
    await sim_runtime.apply_control(running=False)
    assert sim_runtime.status()["running"] is False
    await sim_runtime.apply_control(running=True, speed=120.0)
    st = sim_runtime.status()
    assert st["running"] is True and st["speed"] == 120.0


async def test_viewers_derived_from_subscribers(sim_runtime):
    assert sim_runtime.viewers == 0
    q1 = sim_runtime.subscribe()
    q2 = sim_runtime.subscribe()
    assert sim_runtime.viewers == 2
    sim_runtime.unsubscribe(q1)
    sim_runtime.unsubscribe(q2)
    sim_runtime.unsubscribe(q2)  # idempotent — no negative leak
    assert sim_runtime.viewers == 0


async def test_state_rehydrated_on_restart(temp_session_maker):
    rt1 = await _fresh_runtime(temp_session_maker)
    for _ in range(40):
        rt1.step_once()
    await rt1.flush(final=True)
    spent = {ln.ad_id: rt1.state.spent_today_micros.get(ln.ad_id, 0) for ln in rt1.lines}
    lifetime = {ln.ad_id: rt1.state.spent_lifetime_micros.get(ln.ad_id, 0) for ln in rt1.lines}
    signal = {ln.ad_set_id: rt1.state.learning_signal.get(ln.ad_set_id, 0.0) for ln in rt1.lines}
    day = rt1.sim_day
    assert any(v > 0 for v in spent.values())  # there was real spend to restore

    # A brand-new runtime over the SAME database (a process restart).
    rt2 = await _fresh_runtime(temp_session_maker)
    assert rt2.sim_day == day
    for ln in rt2.lines:
        assert rt2.state.spent_today_micros.get(ln.ad_id, 0) == spent[ln.ad_id]
        assert rt2.state.spent_lifetime_micros.get(ln.ad_id, 0) == lifetime[ln.ad_id]
        if ln.objective in LEARNING_OBJECTIVES:
            assert rt2.state.learning_signal.get(ln.ad_set_id, 0.0) == signal[ln.ad_set_id]


async def test_budget_not_re_spent_across_restart(temp_session_maker):
    rt1 = await _fresh_runtime(temp_session_maker)
    for _ in range(40):
        rt1.step_once()
    await rt1.flush(final=True)

    rt2 = await _fresh_runtime(temp_session_maker)  # restart, same sim-day
    for _ in range(40):
        rt2.step_once()
    # Because spend was rehydrated, continuing the same sim-day never exceeds daily budget.
    for ln in rt2.lines:
        assert rt2.state.spent_today_micros.get(ln.ad_id, 0) <= ln.daily_budget_micros + 1


async def test_restart_snaps_to_bucket_boundary(temp_session_maker):
    rt1 = await _fresh_runtime(temp_session_maker)
    rt1.control.sim_time = 30_030.0  # 30 sim-seconds into bucket 500
    await rt1.flush(final=True)      # persists sim_time mid-bucket
    rt2 = await _fresh_runtime(temp_session_maker)
    assert rt2.control.sim_time == 30_060.0  # resumed at the next whole minute


async def test_flush_retains_buckets_on_db_error(sim_runtime, monkeypatch):
    for _ in range(30):
        sim_runtime.step_once()
    before = set(sim_runtime._accum)
    assert before

    async def boom(*a, **k):
        raise RuntimeError("simulated db failure")

    monkeypatch.setattr(persistence, "upsert_buckets", boom)
    with pytest.raises(RuntimeError):
        await sim_runtime.flush(final=True)
    # Nothing was dropped — the same buckets are still pending for the next flush.
    assert set(sim_runtime._accum) == before
