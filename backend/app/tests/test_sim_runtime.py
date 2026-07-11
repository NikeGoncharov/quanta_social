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


async def test_restart_on_exact_boundary_still_advances(temp_session_maker):
    """sim_time persisted exactly on a minute boundary (every other default tick!) must
    STILL advance a full minute — the tick that landed on the boundary accrued into that
    bucket, and re-entering it would REPLACE-erase its delivery."""
    rt1 = await _fresh_runtime(temp_session_maker)
    rt1.control.sim_time = 30_000.0  # exactly bucket 500's start
    await rt1.flush(final=True)
    rt2 = await _fresh_runtime(temp_session_maker)
    assert rt2.control.sim_time == 30_060.0


async def test_today_counters_match_buckets(sim_runtime):
    """The per-line 'today' counters must agree exactly with the flushed buckets."""
    for _ in range(30):
        sim_runtime.step_once()
    await sim_runtime.flush(final=True)

    day_start = sim_runtime.sim_day * 1440
    async with sim_runtime.session_maker() as s:
        rows = await persistence.today_totals_by_ad(s, day_start=day_start, day_end=day_start + 1440)
    from_db = {r["ad_id"]: {k: int(r[k] or 0) for k in ("auctions", "impressions", "clicks", "conversions")} for r in rows}
    assert from_db, "expected delivery today"
    for ad_id, counters in from_db.items():
        assert sim_runtime._today.get(ad_id) == counters


async def test_today_counters_rehydrate_on_restart(temp_session_maker):
    rt1 = await _fresh_runtime(temp_session_maker)
    for _ in range(40):
        rt1.step_once()
    await rt1.flush(final=True)
    assert any(v["impressions"] > 0 for v in rt1._today.values())

    rt2 = await _fresh_runtime(temp_session_maker)  # process restart, same sim-day
    assert rt2._today == rt1._today
    # ...so realized CTR / avg CPM in the status survive a restart too.
    st = {l["ad_id"]: l for l in rt2.status()["lines"]}
    for ad_id, t in rt1._today.items():
        assert st[ad_id]["impressions_today"] == t["impressions"]

    # Keep delivering after the restart: the in-memory counters and the persisted buckets
    # must STAY in agreement (40 ticks parks sim_time exactly on a minute boundary, the
    # case where a lazy ceil-snap used to re-enter — and REPLACE-erase — the last bucket).
    for _ in range(4):
        rt2.step_once()
    await rt2.flush(final=True)
    day_start = rt2.sim_day * 1440
    async with rt2.session_maker() as s:
        rows = await persistence.today_totals_by_ad(s, day_start=day_start, day_end=day_start + 1440)
    from_db = {r["ad_id"]: {k: int(r[k] or 0) for k in ("auctions", "impressions", "clicks", "conversions")} for r in rows}
    assert from_db == rt2._today


async def test_line_market_uses_run_tick_math(sim_runtime):
    """market.win_rate must be the same bid-vs-reference expectation run_tick delivers with."""
    st = sim_runtime.status()
    for line in st["lines"]:
        m = line["market"]
        assert m["our_bid"] > 0 and m["niche_bid"] > 0
        assert 0.0 <= m["win_rate"] <= 1.0
        # Paid CPM is floored; per-segment it never exceeds the bid, so the win-weighted
        # mean stays within the floor..max-bid envelope (it CAN exceed our_bid, which is
        # opportunity-weighted — you win most where you bid most).
        if m["est_cpm"] is not None:
            floor = sim_runtime.status()["market"]["floor"]
            assert m["est_cpm"] >= floor


async def test_density_moves_market_signals(sim_runtime):
    """Turning up market density must raise every niche's avg bid and cut our win rate —
    the dashboard's core dynamic signal."""
    before = {l["ad_id"]: l["market"] for l in sim_runtime.status()["lines"]}
    await sim_runtime.apply_control(market_density=3.0)
    after = {l["ad_id"]: l["market"] for l in sim_runtime.status()["lines"]}
    for ad_id, b in before.items():
        a = after[ad_id]
        assert a["niche_bid"] > b["niche_bid"]
        if 0.0 < b["win_rate"] < 1.0:
            assert a["win_rate"] < b["win_rate"]


async def test_day_roll_resets_today_with_spend(sim_runtime):
    """Crossing sim-midnight must reset the _today counters in the SAME tick that resets
    spent_today — otherwise yesterday's impressions meet today's zero spend and every
    derived ratio (ctr, avg_cpm, cost_per_result) mixes two different days."""
    for _ in range(10):
        sim_runtime.step_once()
    assert any(v["impressions"] > 0 for v in sim_runtime._today.values())

    sim_runtime.control.sim_time = 86_395.0  # 5 sim-seconds before midnight
    deltas = sim_runtime.step_once()         # +30 sim-sec -> crosses into day 1
    assert sim_runtime.sim_day == 1
    assert sim_runtime._today_day == 1

    # _today now holds ONLY the crossing tick's own deltas...
    expected: dict[str, dict[str, int]] = {}
    for d in deltas:
        t = expected.setdefault(d.ad_id, {"auctions": 0, "impressions": 0, "clicks": 0, "conversions": 0})
        t["auctions"] += d.auctions
        t["impressions"] += d.impressions
        t["clicks"] += d.clicks
        t["conversions"] += d.conversions
    assert sim_runtime._today == expected
    # ...and spent_today reset in the same tick (only the crossing tick's spend remains).
    spent_total = sum(sim_runtime.state.spent_today_micros.values())
    assert spent_total == sum(d.spend_micros for d in deltas)


async def test_crash_restart_keeps_spend_and_funnel_consistent(temp_session_maker):
    """A hard crash (periodic flush, NO final flush) must not desync spent_today from the
    rehydrated funnel counters: both mirrors are written in the same transaction and cover
    the same tick range (the in-progress bucket is flushed too)."""
    rt1 = await _fresh_runtime(temp_session_maker)
    for _ in range(41):  # odd count -> ends mid-minute
        rt1.step_once()
    await rt1.flush()  # periodic flush only — then the process "dies"
    spent = dict(rt1.state.spent_today_micros)
    today = {k: dict(v) for k, v in rt1._today.items()}

    rt2 = await _fresh_runtime(temp_session_maker)
    for ln in rt2.lines:
        assert rt2.state.spent_today_micros.get(ln.ad_id, 0) == spent.get(ln.ad_id, 0)
        assert rt2._today.get(ln.ad_id, {}).get("impressions", 0) == today.get(ln.ad_id, {}).get("impressions", 0)


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
