"""DB reads/writes for the live sim, isolated from the loop mechanics.

Every function takes an `AsyncSession` so the runtime can bind a temp database in tests.
Writes are UPSERTs (completed buckets and state mirrors are idempotent); the auction-sample
table is a ring buffer trimmed to the newest N rows.
"""
import json

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


_BREAKDOWN_METRICS = ("impressions", "clicks", "conversions", "spend_micros", "revenue_micros")


def _merge_breakdown(bd: dict, cell_key: dict, delta: dict) -> dict:
    """Add `delta`'s metrics into each dimension cell named by `cell_key` (interest/geo/
    age_band/gender -> value), matching the JSON shape the synthetic writer and
    read_breakdowns use. Mutates and returns `bd`."""
    for dim, value in cell_key.items():
        cell = bd.setdefault(dim, {}).setdefault(value, dict.fromkeys(_BREAKDOWN_METRICS, 0))
        for m in _BREAKDOWN_METRICS:
            cell[m] = int(cell.get(m, 0) or 0) + int(delta.get(m, 0) or 0)
    return bd


async def add_real_delivery(
    session,
    *,
    ad_id: str,
    ad_set_id: str,
    campaign_id: str,
    account_id: str,
    bucket_start: int,
    covered_seconds: int,
    cell_key: dict,
    auctions: int = 0,
    impressions: int = 0,
    clicks: int = 0,
    conversions: int = 0,
    spend_micros: int = 0,
    revenue_micros: int = 0,
) -> None:
    """Additively record a REAL (friend-feed) delivery event into the source='real' bucket for
    (ad, sim-minute). Unlike the synthetic path — which rewrites a growing in-memory accumulator
    every flush and so can REPLACE on conflict — real events arrive one at a time, so this
    read-modify-writes the existing row (merging its breakdowns JSON). Real volume is low, so
    the extra read is negligible. The row coexists with the synthetic row via the
    (ad_id, bucket_start, source) unique key, and folds into dashboard totals for free."""
    delta = {
        "auctions": auctions, "impressions": impressions, "clicks": clicks,
        "conversions": conversions, "spend_micros": spend_micros, "revenue_micros": revenue_micros,
    }
    row = (
        await session.execute(
            select(DeliveryBucket).where(
                DeliveryBucket.ad_id == ad_id,
                DeliveryBucket.bucket_start == bucket_start,
                DeliveryBucket.source == "real",
            )
        )
    ).scalar_one_or_none()
    if row is None:
        bd = _merge_breakdown({}, cell_key, delta)
        session.add(
            DeliveryBucket(
                ad_id=ad_id, ad_set_id=ad_set_id, campaign_id=campaign_id, account_id=account_id,
                bucket_start=bucket_start, source="real", covered_seconds=covered_seconds,
                breakdowns=json.dumps(bd), **delta,
            )
        )
    else:
        for m in _BUCKET_METRICS:
            setattr(row, m, getattr(row, m) + delta[m])
        row.covered_seconds = max(row.covered_seconds, covered_seconds)
        row.breakdowns = json.dumps(
            _merge_breakdown(json.loads(row.breakdowns or "{}"), cell_key, delta)
        )


async def read_source_totals(session, *, window: int = 1440, campaign_id: str | None = None) -> dict:
    """Split delivery totals by source ('synthetic' vs 'real') over the newest `window`
    sim-minutes — powers the cabinet's 'real vs simulated' badge without a row explosion."""
    latest = await latest_bucket(session, campaign_id=campaign_id)
    if latest is None:
        return {}
    q = select(
        DeliveryBucket.source,
        *[func.sum(getattr(DeliveryBucket, m)).label(m) for m in _BUCKET_METRICS],
    ).where(DeliveryBucket.bucket_start > latest - window)
    if campaign_id:
        q = q.where(DeliveryBucket.campaign_id == campaign_id)
    q = q.group_by(DeliveryBucket.source)
    rows = (await session.execute(q)).all()
    return {r._mapping["source"]: {k: int(r._mapping.get(k) or 0) for k in _BUCKET_METRICS} for r in rows}


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


# --- cabinet reporting reads -------------------------------------------------
async def latest_bucket(session, *, campaign_id: str | None = None) -> int | None:
    """Newest recorded sim-minute (optionally for one campaign) — the anchor for windowed
    reporting so a quiet 'now' still reports against real delivery, not the live clock."""
    q = select(func.max(DeliveryBucket.bucket_start))
    if campaign_id:
        q = q.where(DeliveryBucket.campaign_id == campaign_id)
    return (await session.execute(q)).scalar()


async def kpi_totals(session, *, start: int, end: int, campaign_id: str | None = None) -> dict:
    """Summed delivery metrics over the sim-minute range [start, end) (all campaigns or one)."""
    q = select(
        *[func.sum(getattr(DeliveryBucket, m)).label(m) for m in _BUCKET_METRICS]
    ).where(DeliveryBucket.bucket_start >= start, DeliveryBucket.bucket_start < end)
    if campaign_id:
        q = q.where(DeliveryBucket.campaign_id == campaign_id)
    row = (await session.execute(q)).first()
    m = row._mapping if row else {}
    return {k: int(m.get(k) or 0) for k in _BUCKET_METRICS}


async def read_breakdowns(
    session, *, dimension: str, campaign_id: str | None = None, window: int = 1440
) -> list[dict]:
    """Aggregate the buckets' `breakdowns` JSON along one dimension (interest / geo /
    age_band / gender) over the newest `window` sim-minutes. Returned per dimension value,
    unsorted — the caller ranks and USD-normalizes."""
    latest = await latest_bucket(session, campaign_id=campaign_id)
    if latest is None:
        return []
    q = select(DeliveryBucket.breakdowns).where(DeliveryBucket.bucket_start > latest - window)
    if campaign_id:
        q = q.where(DeliveryBucket.campaign_id == campaign_id)
    rows = (await session.execute(q)).scalars().all()
    metrics = ("impressions", "clicks", "conversions", "spend_micros", "revenue_micros")
    agg: dict[str, dict] = {}
    for raw in rows:
        dim = json.loads(raw or "{}").get(dimension, {})
        for value, cell in dim.items():
            cur = agg.setdefault(value, dict.fromkeys(metrics, 0))
            for k in metrics:
                cur[k] += int(cell.get(k, 0) or 0)
    return [{"value": v, **cells} for v, cells in agg.items()]


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
