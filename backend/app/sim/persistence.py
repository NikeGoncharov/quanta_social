"""DB reads/writes for the live sim, isolated from the loop mechanics.

Every function takes an `AsyncSession` so the runtime can bind a temp database in tests.
Writes are UPSERTs (completed buckets and state mirrors are idempotent); the auction-sample
table is a ring buffer trimmed to the newest N rows.
"""
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ..models import (
    AuctionSample,
    BudgetState,
    DeliveryBucket,
    LearningState,
    SimControl,
)

_BUCKET_METRICS = ("auctions", "impressions", "clicks", "conversions", "spend_micros", "revenue_micros")


# --- sim_control (singleton id=1) --------------------------------------------
async def load_control(session) -> dict | None:
    row = await session.get(SimControl, 1)
    if row is None:
        return None
    return {
        "running": row.running,
        "speed": row.speed,
        "tick_hz": row.tick_hz,
        "sim_time": row.sim_time,
        "market_density": row.market_density,
    }


async def save_control(session, *, running, speed, tick_hz, sim_time, market_density) -> None:
    stmt = sqlite_insert(SimControl).values(
        id=1, running=running, speed=speed, tick_hz=tick_hz,
        sim_time=sim_time, market_density=market_density,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "running": stmt.excluded.running,
            "speed": stmt.excluded.speed,
            "tick_hz": stmt.excluded.tick_hz,
            "sim_time": stmt.excluded.sim_time,
            "market_density": stmt.excluded.market_density,
        },
    )
    await session.execute(stmt)


# --- delivery buckets --------------------------------------------------------
async def upsert_buckets(session, rows: list[dict]) -> None:
    """Write delivery buckets. Completed buckets are final; the current in-progress bucket
    is REPLACE-rewritten with growing totals every flush (never re-entered after a restart —
    the runtime resumes at the NEXT whole sim-minute), so DO UPDATE simply replaces."""
    if not rows:
        return
    stmt = sqlite_insert(DeliveryBucket).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["ad_id", "bucket_start", "source"],
        set_={
            **{m: getattr(stmt.excluded, m) for m in _BUCKET_METRICS},
            "breakdowns": stmt.excluded.breakdowns,
        },
    )
    await session.execute(stmt)


async def read_delivery(session, *, window: int = 180, campaign_id: str | None = None) -> list[dict]:
    """The aggregate delivery series: metrics summed across ads per sim-minute, newest
    `window` buckets, returned ascending in time."""
    q = select(
        DeliveryBucket.bucket_start.label("t"),
        # The bucket's time span is a world-wide property (all ads share the tick cadence);
        # MAX tolerates ads that skipped some of the bucket's ticks.
        func.max(DeliveryBucket.covered_seconds).label("covered_seconds"),
        *[func.sum(getattr(DeliveryBucket, m)).label(m) for m in _BUCKET_METRICS],
    )
    if campaign_id:
        q = q.where(DeliveryBucket.campaign_id == campaign_id)
    q = (
        q.group_by(DeliveryBucket.bucket_start)
        .order_by(DeliveryBucket.bucket_start.desc())
        .limit(window)
    )
    rows = (await session.execute(q)).all()
    return [dict(r._mapping) for r in reversed(rows)]


async def read_history(
    session, *, bin_minutes: int, bins: int, campaign_id: str | None = None
) -> list[dict]:
    """Delivery history rolled up into uniform `bin_minutes`-wide bins (SQLite integer
    division), newest `bins` bins, ascending. Uniform bins make the series independent of
    the sim speed's bucket density — the static long-range view of the dashboard."""
    bin_expr = (DeliveryBucket.bucket_start.op("/")(bin_minutes)).op("*")(bin_minutes)
    q = select(
        bin_expr.label("t"),
        *[func.sum(getattr(DeliveryBucket, m)).label(m) for m in _BUCKET_METRICS],
    )
    if campaign_id:
        q = q.where(DeliveryBucket.campaign_id == campaign_id)
    q = q.group_by("t").order_by(bin_expr.desc()).limit(bins)
    rows = (await session.execute(q)).all()
    return [dict(r._mapping) for r in reversed(rows)]


async def today_totals_by_ad(session, *, day_start: int, day_end: int) -> list[dict]:
    """Per-ad delivery totals for buckets in [day_start, day_end) sim-minutes — rehydrates
    the runtime's per-line 'today' counters after a restart."""
    q = (
        select(
            DeliveryBucket.ad_id,
            *[func.sum(getattr(DeliveryBucket, m)).label(m) for m in _BUCKET_METRICS],
        )
        .where(DeliveryBucket.bucket_start >= day_start, DeliveryBucket.bucket_start < day_end)
        .group_by(DeliveryBucket.ad_id)
    )
    rows = (await session.execute(q)).all()
    return [dict(r._mapping) for r in rows]


# --- state mirrors -----------------------------------------------------------
async def snapshot_budget(session, entries: list[dict]) -> None:
    if not entries:
        return
    stmt = sqlite_insert(BudgetState).values(entries)
    stmt = stmt.on_conflict_do_update(
        index_elements=["ad_id"],
        set_={
            "sim_day": stmt.excluded.sim_day,
            "spent_today_micros": stmt.excluded.spent_today_micros,
            "spent_lifetime_micros": stmt.excluded.spent_lifetime_micros,
            "daily_budget_micros": stmt.excluded.daily_budget_micros,
        },
    )
    await session.execute(stmt)


async def snapshot_learning(session, entries: list[dict]) -> None:
    if not entries:
        return
    stmt = sqlite_insert(LearningState).values(entries)
    stmt = stmt.on_conflict_do_update(
        index_elements=["ad_set_id"],
        set_={
            "accumulated_signal": stmt.excluded.accumulated_signal,
            "threshold": stmt.excluded.threshold,
            "in_learning": stmt.excluded.in_learning,
        },
    )
    await session.execute(stmt)


async def load_budget_states(session) -> list[dict]:
    """Rehydrate spend on restart (the world loop's DeliveryState is otherwise reset)."""
    rows = (await session.execute(select(BudgetState))).scalars().all()
    return [
        {
            "ad_id": r.ad_id,
            "sim_day": r.sim_day,
            "spent_today_micros": r.spent_today_micros,
            "spent_lifetime_micros": r.spent_lifetime_micros,
        }
        for r in rows
    ]


async def load_learning_states(session) -> list[dict]:
    rows = (await session.execute(select(LearningState))).scalars().all()
    return [{"ad_set_id": r.ad_set_id, "accumulated_signal": r.accumulated_signal} for r in rows]


# --- auction samples (ring buffer) -------------------------------------------
async def insert_samples(session, samples: list[dict]) -> None:
    if not samples:
        return
    await session.execute(sqlite_insert(AuctionSample), samples)


async def trim_samples(session, *, keep: int) -> None:
    newest = select(AuctionSample.id).order_by(AuctionSample.id.desc()).limit(keep)
    await session.execute(delete(AuctionSample).where(AuctionSample.id.not_in(newest)))


_SAMPLE_SUMMARY_COLS = (
    AuctionSample.id, AuctionSample.sim_time, AuctionSample.segment_key,
    AuctionSample.line_ad_id, AuctionSample.won, AuctionSample.winner_seat,
    AuctionSample.winner_ad_id, AuctionSample.clearing_micros, AuctionSample.floor_micros,
    AuctionSample.min_to_win_micros, AuctionSample.eligible_count, AuctionSample.filtered_count,
)


async def list_samples(session, *, limit: int = 40) -> list[dict]:
    q = select(*_SAMPLE_SUMMARY_COLS).order_by(AuctionSample.id.desc()).limit(limit)
    rows = (await session.execute(q)).all()
    return [dict(r._mapping) for r in rows]


async def get_sample(session, sample_id: int) -> AuctionSample | None:
    return await session.get(AuctionSample, sample_id)
