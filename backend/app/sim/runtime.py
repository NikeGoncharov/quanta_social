"""SimRuntime — the single real-time world loop and everything around it.

One `asyncio.Task` advances a global sim clock, calls the pure `run_tick`, aggregates the
resulting per-segment deltas into minute buckets, occasionally materializes a full auction
for the RTB Inspector, flushes to the DB every ~1.5s, and fans the results out to SSE
subscribers. The loop is *viewer-gated*: it only advances while `running` is set AND at
least one client is watching (the product's "pause when idle" rule), so the world isn't
burning cycles for an empty room.

Everything DB-touching goes through `persistence` and the runtime's `session_maker`, so a
test can bind a temp database and drive `step_once()` / `flush()` by hand — no wall clock.
"""
import asyncio
import json
import logging
import random
from dataclasses import dataclass, field, replace

from ..adsim.dsp.strategy import effective_bid_micros
from ..adsim.dsp.targeting import is_interest_relevant, matching_segments
from ..adsim.mathx import clamp, cpm_paid_first_price, cpm_paid_second_price, win_rate
from ..adsim.materialize import sampled_auction
from ..adsim.models.enums import (
    FUNNEL_STAGE,
    LEARNING_OBJECTIVES,
    AuctionType,
    Objective,
)
from ..adsim.money import micros_to_usd
from ..adsim.simulation import segment_model as sm
from ..adsim.simulation.delivery import run_tick
from ..adsim.simulation.learning import in_learning, learning_lift, signal_to_exit
from ..adsim.simulation.state import DeliveryState
from ..database import async_session_maker
from . import persistence
from .seed import LINE_LABELS

log = logging.getLogger("quanta.sim")

WORLD_SEED = 42
FLUSH_INTERVAL_S = 1.5
SAMPLE_EVERY_N_TICKS = 3
SAMPLE_RING = 200
QUEUE_MAX = 256
SECONDS_PER_SIM_DAY = 86_400
MINUTES_PER_SIM_DAY = 1_440
# On a fresh world, start the clock mid-morning so even-paced campaigns deliver immediately
# (even pacing gates spend to the day's elapsed fraction — starting at 00:00 looks dead).
DEFAULT_START_SIM_TIME = 8 * 3600
BUCKET_METRICS = ("auctions", "impressions", "clicks", "conversions", "spend_micros", "revenue_micros")
TODAY_KEYS = ("auctions", "impressions", "clicks", "conversions")


@dataclass
class Control:
    running: bool = True
    speed: float = 60.0          # sim-seconds advanced per real second
    tick_hz: float = 2.0         # loop ticks per real second
    sim_time: float = 0.0        # elapsed sim seconds
    market_density: float = 1.0


@dataclass
class BucketAccum:
    ad_id: str
    ad_set_id: str
    campaign_id: str
    account_id: str
    bucket: int
    auctions: int = 0
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    spend_micros: int = 0
    revenue_micros: int = 0
    breakdowns: dict = field(
        default_factory=lambda: {"interest": {}, "geo": {}, "age_band": {}, "gender": {}}
    )

    def add(self, d) -> None:
        for m in BUCKET_METRICS:
            setattr(self, m, getattr(self, m) + getattr(d, m))
        for dim, val in (("interest", d.interest), ("geo", d.geo), ("age_band", d.age_band), ("gender", d.gender)):
            cell = self.breakdowns[dim].setdefault(
                val, {"impressions": 0, "clicks": 0, "conversions": 0, "spend_micros": 0, "revenue_micros": 0}
            )
            cell["impressions"] += d.impressions
            cell["clicks"] += d.clicks
            cell["conversions"] += d.conversions
            cell["spend_micros"] += d.spend_micros
            cell["revenue_micros"] += d.revenue_micros

    def to_row(self) -> dict:
        return {
            "ad_id": self.ad_id,
            "ad_set_id": self.ad_set_id,
            "campaign_id": self.campaign_id,
            "account_id": self.account_id,
            "bucket_start": self.bucket,
            "source": "synthetic",
            **{m: getattr(self, m) for m in BUCKET_METRICS},
            "breakdowns": json.dumps(self.breakdowns),
        }


def to_delivery_point(d: dict) -> dict:
    """Normalize a raw metric row (counts + micros) into the API/SSE delivery point.
    `span` is how many sim-minutes the bucket actually covers (>1 at fast sim speeds) —
    counts stay raw totals; clients divide by span for honest per-minute rates."""
    def i(k):
        return int(d.get(k) or 0)

    return {
        "t": i("t"),
        "span": round(max(i("covered_seconds"), 1) / 60.0, 2) if d.get("covered_seconds") else 1.0,
        "auctions": i("auctions"),
        "impressions": i("impressions"),
        "clicks": i("clicks"),
        "conversions": i("conversions"),
        "spend": round(micros_to_usd(i("spend_micros")), 2),
        "revenue": round(micros_to_usd(i("revenue_micros")), 2),
    }


class SimRuntime:
    def __init__(self, world, lines, *, session_maker=None):
        self.world = world
        self.lines = lines
        self.state = DeliveryState()
        self.control = Control()
        self.session_maker = session_maker or async_session_maker

        self.tick_index = 0
        self._accum: dict[tuple[str, int], BucketAccum] = {}
        # Sim-seconds of world time each pending bucket's ticks spanned (a tick attributes
        # its whole span to the bucket it lands in, mirroring how deltas are attributed).
        # Written to the bucket rows so clients can compute honest per-minute rates at any
        # sim speed — at 1 h/s a single bucket carries ~30 minutes of delivery.
        self._bucket_covered: dict[int, float] = {}
        # Per-line counters for the CURRENT sim-day (ad_id -> {auctions, impressions, ...}).
        # Feeds the cabinet's realized CTR / avg CPM / cost-per-result; reset on day roll and
        # rehydrated from delivery buckets on restart (like spend).
        self._today: dict[str, dict[str, int]] = {}
        self._today_day = 0
        self._pending_samples: list[dict] = []
        self._sample_seq = 0
        self._rng = random.Random()

        self._subscribers: set[asyncio.Queue] = set()
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._wake = asyncio.Event()

    @property
    def viewers(self) -> int:
        # Derived from the live subscriber set, so a leaked counter can never pin the loop.
        return len(self._subscribers)

    # --- clock helpers -------------------------------------------------------
    @property
    def sim_day(self) -> int:
        return int(self.control.sim_time // SECONDS_PER_SIM_DAY)

    @property
    def day_fraction(self) -> float:
        return (self.control.sim_time % SECONDS_PER_SIM_DAY) / SECONDS_PER_SIM_DAY

    def _current_bucket(self) -> int:
        return int(self.control.sim_time // 60)

    def sim_clock(self) -> str:
        rem = self.control.sim_time % SECONDS_PER_SIM_DAY
        return f"Day {self.sim_day + 1} {int(rem // 3600):02d}:{int((rem % 3600) // 60):02d}"

    def _sim_seconds_per_tick(self) -> float:
        return self.control.speed / max(0.2, self.control.tick_hz)

    # --- lifecycle -----------------------------------------------------------
    async def start(self) -> None:
        self._stop.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(asyncio.shield(self._task), timeout=5.0)
            except asyncio.TimeoutError:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            self._task = None

    async def _run(self) -> None:
        try:
            await self._load_or_init_control()
            loop = asyncio.get_running_loop()
            last_flush = loop.time()
            while not self._stop.is_set():
                # A per-iteration guard: a transient DB error or a bad tick must skip an
                # interval, never terminate the world loop (which would freeze the sim
                # until a restart). flush() is commit-then-mutate, so a failed flush leaves
                # the pending buckets in memory to retry next interval.
                try:
                    if not (self.control.running and self.viewers > 0):
                        await self.flush()
                        await self._idle_wait()
                        last_flush = loop.time()
                        continue
                    self.step_once()
                    now = loop.time()
                    if now - last_flush >= FLUSH_INTERVAL_S:
                        await self.flush()
                        last_flush = now
                    await asyncio.sleep(1.0 / max(0.2, self.control.tick_hz))
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log.exception("world tick failed; continuing")
                    await asyncio.sleep(0.5)  # back off so we don't hot-loop on a hard error
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("world loop crashed")
        finally:
            try:
                await self.flush(final=True)
            except Exception:
                log.exception("final flush failed")

    async def _idle_wait(self) -> None:
        while not self._stop.is_set():
            self._wake.clear()
            if self.control.running and self.viewers > 0:
                return
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

    async def _load_or_init_control(self) -> None:
        async with self.session_maker() as s:
            existing = await persistence.load_control(s)
            if existing is None:
                self.control = Control(
                    running=True, speed=60.0, tick_hz=2.0,
                    sim_time=float(DEFAULT_START_SIM_TIME), market_density=1.0,
                )
                await persistence.save_control(s, **self._control_kwargs())
                await s.commit()
                self.state.roll_to_day(self.sim_day)
                self._today_day = self.sim_day
            else:
                self.control = Control(**existing)
                # Resume at the NEXT whole sim-minute so no post-restart tick re-enters an
                # already-flushed bucket (upsert is REPLACE, not add — it would drop the
                # pre-restart delivery). Strictly advance: ceil() would no-op when the
                # persisted sim_time already sits exactly on a minute boundary (which the
                # default 30-sim-sec ticks hit every other tick), re-entering the bucket.
                self.control.sim_time = (int(self.control.sim_time // 60.0) + 1) * 60.0
                # Establish the sim-day, then rehydrate running state from the DB mirrors so
                # spend/learning don't reset (which would let a day's budget be re-spent).
                self.state.roll_to_day(self.sim_day)
                await self._rehydrate_state(s)
        self._rebuild_world_density()

    async def _rehydrate_state(self, session) -> None:
        """Restore DeliveryState from the persisted mirrors after a restart. Lifetime spend
        and learning signal always carry over; today's spend only for rows recorded on the
        current sim-day (older rows are correctly a fresh day = 0)."""
        day = self.sim_day
        for b in await persistence.load_budget_states(session):
            self.state.spent_lifetime_micros[b["ad_id"]] = b["spent_lifetime_micros"]
            if b["sim_day"] == day:
                self.state.spent_today_micros[b["ad_id"]] = b["spent_today_micros"]
        for lrow in await persistence.load_learning_states(session):
            self.state.learning_signal[lrow["ad_set_id"]] = lrow["accumulated_signal"]
        # Per-line 'today' counters come straight from the day's flushed buckets.
        day_start = day * MINUTES_PER_SIM_DAY
        for row in await persistence.today_totals_by_ad(
            session, day_start=day_start, day_end=day_start + MINUTES_PER_SIM_DAY
        ):
            self._today[row["ad_id"]] = {m: int(row[m] or 0) for m in TODAY_KEYS}
        self._today_day = day

    # --- the tick ------------------------------------------------------------
    def step_once(self) -> list:
        """Advance one tick: move the clock, run the pure engine, accumulate deltas, and
        occasionally capture a materialized auction. Pure of I/O (safe to call in tests)."""
        self.tick_index += 1
        spt = self._sim_seconds_per_tick()
        self.control.sim_time += spt
        self.state.roll_to_day(self.sim_day)
        if self._today_day != self.sim_day:
            self._today = {}
            self._today_day = self.sim_day

        deltas = run_tick(
            self.world, self.lines, self.state,
            sim_seconds_per_tick=spt, day_fraction=self.day_fraction,
            tick_index=self.tick_index, seed=WORLD_SEED, stochastic=True,
        )
        bucket = self._current_bucket()
        self._bucket_covered[bucket] = self._bucket_covered.get(bucket, 0.0) + spt
        for d in deltas:
            key = (d.ad_id, bucket)
            acc = self._accum.get(key)
            if acc is None:
                acc = BucketAccum(d.ad_id, d.ad_set_id, d.campaign_id, d.account_id, bucket)
                self._accum[key] = acc
            acc.add(d)
            today = self._today.setdefault(d.ad_id, dict.fromkeys(TODAY_KEYS, 0))
            for m in TODAY_KEYS:
                today[m] += getattr(d, m)

        if self.tick_index % SAMPLE_EVERY_N_TICKS == 0:
            sample = self._capture_sample()
            if sample is not None:
                self._pending_samples.append(sample)
        return deltas

    def _capture_sample(self) -> dict | None:
        active = [ln for ln in self.lines if ln.active]
        if not active:
            return None
        line = self._rng.choice(active)
        segs = matching_segments(line.targeting, self.world)
        if not segs:
            return None
        seg = self._rng.choice(segs)
        return self._build_sample(line, seg)

    def _build_sample(self, line, seg) -> dict:
        relevant = is_interest_relevant(line.targeting, seg)
        cum_imp = self.state.cum_impressions.get((line.ad_id, seg.id), 0)
        if line.objective in LEARNING_OBJECTIVES:
            lift = learning_lift(self.state.learning_signal.get(line.ad_set_id, 0.0), self.world.learning, None)
        else:
            lift = 1.0
        ctr = sm.effective_ctr(seg, relevant, cum_imp, self.world)
        cvr = sm.effective_cvr(seg, relevant, lift, self.world)
        self._sample_seq += 1
        req, res = sampled_auction(
            self.world, seg, line, ctr=ctr, cvr=cvr, rng=self._rng,
            n_phantoms=5, request_id=f"auc-{self._sample_seq}",
        )
        bids = {
            "eligible": [
                {
                    "seat": rb.seat,
                    "price": round(micros_to_usd(rb.bid.price_micros), 2),
                    "price_micros": rb.bid.price_micros,
                    "crid": rb.bid.crid,
                    "cid": rb.bid.cid,
                    "adomain": rb.bid.adomain,
                    "is_winner": res.winner is rb,
                }
                for rb in res.eligible
            ],
            "filtered": [
                {
                    "seat": fb.seat,
                    "price": round(micros_to_usd(fb.bid.price_micros), 2),
                    "price_micros": fb.bid.price_micros,
                    "reason": fb.reason.name,
                    "reason_code": int(fb.reason),
                }
                for fb in res.filtered
            ],
        }
        notices = [{"kind": e.kind, "seat": e.seat, "url": e.url, "billed": e.billed} for e in res.notices]
        return {
            "sim_time": self.control.sim_time,
            "segment_key": seg.id,
            "line_ad_id": line.ad_id,
            "won": res.won,
            "winner_seat": res.winner.seat if res.winner else "",
            "winner_ad_id": res.winner.bid.crid if res.winner else "",
            "clearing_micros": res.clearing_micros,
            "floor_micros": res.floor_micros,
            "min_to_win_micros": res.min_to_win_micros,
            "eligible_count": len(res.eligible),
            "filtered_count": len(res.filtered),
            "request_json": json.dumps(req.to_dict()),
            "bids_json": json.dumps(bids),
            "notices_json": json.dumps(notices),
        }

    # --- flush (the only writer) --------------------------------------------
    async def flush(self, final: bool = False) -> None:
        # Write EVERY accumulator — including the current in-progress minute — in the same
        # transaction as the budget/learning mirrors, so after any crash the buckets and the
        # mirrors cover the exact same tick range (spend without its impressions would skew
        # avg CPM / cost-per-result after rehydration). The in-progress bucket is REPLACE-
        # rewritten with larger totals each flush (idempotent; the SSE point for the same
        # sim-minute replaces client-side), so only completed buckets are dropped from memory.
        current = self._current_bucket()
        keys = list(self._accum)
        drop = keys if final else [k for k in keys if k[1] < current]
        # Read (do NOT pop) the accumulators + snapshot the pending samples, so an exception
        # anywhere in the write leaves in-memory state intact to retry on the next flush.
        points: dict[int, dict] = {}
        rows: list[dict] = []
        for k in keys:
            acc = self._accum[k]
            covered = int(round(self._bucket_covered.get(acc.bucket, 60.0))) or 60
            rows.append({**acc.to_row(), "covered_seconds": covered})
            p = points.setdefault(
                acc.bucket,
                {"t": acc.bucket, "covered_seconds": covered, **{m: 0 for m in BUCKET_METRICS}},
            )
            for m in BUCKET_METRICS:
                p[m] += getattr(acc, m)
        samples = list(self._pending_samples)

        async with self.session_maker() as s:
            await persistence.upsert_buckets(s, rows)
            await persistence.snapshot_budget(s, self._budget_entries())
            await persistence.snapshot_learning(s, self._learning_entries())
            if samples:
                await persistence.insert_samples(s, samples)
                await persistence.trim_samples(s, keep=SAMPLE_RING)
            await persistence.save_control(s, **self._control_kwargs())
            await s.commit()

        # Commit succeeded — now it is safe to drop the COMPLETED buckets (the in-progress
        # one keeps accumulating in memory and will be REPLACE-rewritten next flush).
        for k in drop:
            self._accum.pop(k, None)
        self._bucket_covered = (
            {} if final else {b: v for b, v in self._bucket_covered.items() if b >= current}
        )
        del self._pending_samples[: len(samples)]

        for b in sorted(points):
            self._publish("delivery", to_delivery_point(points[b]))
        self._publish_status()

    def _budget_entries(self) -> list[dict]:
        return [
            {
                "ad_id": ln.ad_id,
                "ad_set_id": ln.ad_set_id,
                "campaign_id": ln.campaign_id,
                "account_id": ln.account_id,
                "sim_day": self.state.sim_day,
                "spent_today_micros": self.state.spent_today_micros.get(ln.ad_id, 0),
                "spent_lifetime_micros": self.state.spent_lifetime_micros.get(ln.ad_id, 0),
                "daily_budget_micros": ln.daily_budget_micros,
            }
            for ln in self.lines
        ]

    def _learning_entries(self) -> list[dict]:
        out = []
        for ln in self.lines:
            if ln.objective not in LEARNING_OBJECTIVES:
                continue
            sig = self.state.learning_signal.get(ln.ad_set_id, 0.0)
            out.append({
                "ad_set_id": ln.ad_set_id,
                "campaign_id": ln.campaign_id,
                "objective": ln.objective.value,
                "accumulated_signal": sig,
                "threshold": self.world.learning.threshold,
                "in_learning": in_learning(sig, self.world.learning),
            })
        return out

    # --- controls ------------------------------------------------------------
    def _control_kwargs(self) -> dict:
        c = self.control
        return {
            "running": c.running, "speed": c.speed, "tick_hz": c.tick_hz,
            "sim_time": c.sim_time, "market_density": c.market_density,
        }

    def _rebuild_world_density(self) -> None:
        self.world = replace(
            self.world, economy=replace(self.world.economy, market_density=self.control.market_density)
        )

    async def apply_control(self, *, running=None, speed=None, tick_hz=None, market_density=None) -> dict:
        if running is not None:
            self.control.running = bool(running)
        if speed is not None:
            self.control.speed = clamp(float(speed), 1.0, 100_000.0)
        if tick_hz is not None:
            self.control.tick_hz = clamp(float(tick_hz), 0.2, 20.0)
        if market_density is not None:
            self.control.market_density = clamp(float(market_density), 0.0, 5.0)
            self._rebuild_world_density()
        async with self.session_maker() as s:
            await persistence.save_control(s, **self._control_kwargs())
            await s.commit()
        self._wake.set()
        self._publish_status()
        return self.status()

    # --- SSE fan-out ---------------------------------------------------------
    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAX)
        self._subscribers.add(q)
        self._wake.set()  # a new viewer un-pauses the idle loop
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def _publish(self, event_type: str, data) -> None:
        event = {"type": event_type, "data": data}
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # slow client — it will catch up on the next status snapshot

    def _publish_status(self) -> None:
        self._publish("status", self.status())

    # --- status snapshot -----------------------------------------------------
    def status(self) -> dict:
        return {
            "running": self.control.running,
            "active": self.control.running and self.viewers > 0,
            "viewers": self.viewers,
            "speed": self.control.speed,
            "tick_hz": self.control.tick_hz,
            "sim_time": self.control.sim_time,
            "sim_day": self.sim_day,
            "sim_clock": self.sim_clock(),
            "market_density": self.control.market_density,
            "market": self._market_status(),
            "lines": [self._line_status(ln) for ln in self.lines],
        }

    def _market_status(self) -> dict:
        """The market as a whole, right now: the opportunity-weighted average competitor bid
        across every niche (scaled by the live density), plus who is bidding against you."""
        segs = self.world.segment_list()
        total_w = sum(s.opportunity_rate for s in segs)
        avg_ref = (
            sum(s.reference_bid_micros * s.opportunity_rate for s in segs) / total_w
            if total_w > 0
            else 0.0
        )
        return {
            "density": self.world.economy.market_density,
            "avg_bid": round(micros_to_usd(avg_ref * self.world.economy.market_density), 2),
            "floor": round(micros_to_usd(self.world.economy.default_floor_micros), 2),
            "auction_type": self.world.economy.auction_type,
            "seats": [ps.name for ps in self.world.phantom_seats],
        }

    def _line_market(self, ln) -> dict:
        """The line's competitive position right now, computed with the SAME functions
        run_tick bids with (expectation-only, no draws) — the glass-box signal IS the
        mechanics: avg niche bid vs our eCPM, the est. share of auctions we'd win, and the
        CPM we'd expect to pay on wins."""
        eco = self.world.economy
        density = eco.market_density
        floor = eco.default_floor_micros
        at = AuctionType(eco.auction_type)
        if ln.objective in LEARNING_OBJECTIVES:
            lift = learning_lift(
                self.state.learning_signal.get(ln.ad_set_id, 0.0), self.world.learning, None
            )
        else:
            lift = 1.0

        segs = matching_segments(ln.targeting, self.world)
        total_w = ref_acc = bid_acc = wr_acc = cpm_acc = 0.0
        reach = 0
        for seg in segs:
            relevant = is_interest_relevant(ln.targeting, seg)
            cum_imp = self.state.cum_impressions.get((ln.ad_id, seg.id), 0)
            ctr = sm.effective_ctr(seg, relevant, cum_imp, self.world)
            cvr = sm.effective_cvr(seg, relevant, lift, self.world)
            ebid = effective_bid_micros(ln, ctr, cvr)
            ref = int(seg.reference_bid_micros * density)
            wr = win_rate(ebid, ref) if ebid >= floor else 0.0
            cpm = (
                cpm_paid_first_price(ebid)
                if at == AuctionType.FIRST_PRICE
                else cpm_paid_second_price(ebid, ref, wr)
            )
            w = seg.opportunity_rate
            total_w += w
            ref_acc += ref * w
            bid_acc += ebid * w
            wr_acc += wr * w
            cpm_acc += max(cpm, floor) * wr * w  # paid CPM only matters on wins
            reach += seg.size

        if total_w <= 0:
            return {
                "niche_bid": 0.0, "our_bid": 0.0, "win_rate": 0.0,
                "est_cpm": None, "segments": 0, "reach": 0,
            }
        return {
            "niche_bid": round(micros_to_usd(ref_acc / total_w), 2),
            "our_bid": round(micros_to_usd(bid_acc / total_w), 2),
            "win_rate": round(wr_acc / total_w, 4),
            "est_cpm": round(micros_to_usd(cpm_acc / wr_acc), 2) if wr_acc > 0 else None,
            "segments": len(segs),
            "reach": reach,
        }

    def _line_status(self, ln) -> dict:
        label = LINE_LABELS.get(ln.ad_id, {})
        budget = ln.daily_budget_micros
        spent = self.state.spent_today_micros.get(ln.ad_id, 0)
        spent_usd = micros_to_usd(spent)
        is_learning_obj = ln.objective in LEARNING_OBJECTIVES
        sig = self.state.learning_signal.get(ln.ad_set_id, 0.0)

        today = self._today.get(ln.ad_id) or {}
        imps = today.get("impressions", 0)
        clicks = today.get("clicks", 0)
        convs = today.get("conversions", 0)

        # The objective decides what a "result" is and how its cost reads.
        if ln.objective == Objective.AWARENESS:
            results, result_label, cost_label = imps, "impressions", "CPM"
            cost = round(spent_usd * 1000 / imps, 2) if imps else None
        elif ln.objective == Objective.TRAFFIC:
            results, result_label, cost_label = clicks, "clicks", "CPC"
            cost = round(spent_usd / clicks, 2) if clicks else None
        elif ln.objective == Objective.ENGAGEMENT:
            results, result_label, cost_label = clicks, "engagements", "cost/eng."
            cost = round(spent_usd / clicks, 2) if clicks else None
        else:
            results, result_label, cost_label = convs, "conversions", "CPA"
            cost = round(spent_usd / convs, 2) if convs else None

        return {
            "ad_id": ln.ad_id,
            "campaign_id": ln.campaign_id,
            "brand": label.get("brand", ln.creative.brand_name),
            "name": label.get("name", ln.campaign_id),
            "objective": ln.objective.value,
            "funnel_stage": FUNNEL_STAGE.get(ln.objective),
            "pacing": ln.pacing.value,
            "daily_budget": round(micros_to_usd(budget), 2),
            "spent_today": round(spent_usd, 2),
            "budget_util": round(spent / budget, 4) if budget else None,
            "in_learning": in_learning(sig, self.world.learning) if is_learning_obj else None,
            "signal": round(sig, 1) if is_learning_obj else None,
            "signal_to_exit": round(signal_to_exit(sig, self.world.learning), 1) if is_learning_obj else None,
            "auctions_today": today.get("auctions", 0),
            "impressions_today": imps,
            "clicks_today": clicks,
            "conversions_today": convs,
            "ctr": round(clicks / imps, 4) if imps else None,
            "avg_cpm": round(spent_usd * 1000 / imps, 2) if imps else None,
            "results": results,
            "result_label": result_label,
            "cost_per_result": cost,
            "cost_label": cost_label,
            "market": self._line_market(ln),
        }

    async def snapshot(self, *, window: int = 180) -> dict:
        """Initial payload for a newly-connected SSE client: current status + recent buckets."""
        async with self.session_maker() as s:
            rows = await persistence.read_delivery(s, window=window)
        return {"status": self.status(), "delivery": [to_delivery_point(r) for r in rows]}

    # --- reads for the API (go through the runtime's DB) ---------------------
    async def delivery_series(self, *, window: int = 180, campaign_id: str | None = None) -> list[dict]:
        async with self.session_maker() as s:
            rows = await persistence.read_delivery(s, window=window, campaign_id=campaign_id)
        return [to_delivery_point(r) for r in rows]

    async def list_samples(self, *, limit: int = 40) -> list[dict]:
        async with self.session_maker() as s:
            rows = await persistence.list_samples(s, limit=limit)
        for r in rows:
            r["clearing"] = round(micros_to_usd(r.pop("clearing_micros")), 2)
            r["floor"] = round(micros_to_usd(r.pop("floor_micros")), 2)
            r["min_to_win"] = round(micros_to_usd(r.pop("min_to_win_micros")), 2)
        return rows

    async def get_sample(self, sample_id: int) -> dict | None:
        async with self.session_maker() as s:
            row = await persistence.get_sample(s, sample_id)
            if row is None:
                return None
            return _sample_detail(row)

    async def replay(self, *, ad_id: str | None = None, segment_key: str | None = None) -> dict | None:
        """Run a fresh materialized auction on demand and persist it into the ring."""
        line = next((ln for ln in self.lines if ln.ad_id == ad_id), None) if ad_id else None
        if line is None:
            active = [ln for ln in self.lines if ln.active]
            if not active:
                return None
            line = self._rng.choice(active)
        segs = matching_segments(line.targeting, self.world)
        if not segs:
            return None
        seg = next((s for s in segs if s.id == segment_key), None) if segment_key else None
        if seg is None:
            seg = self._rng.choice(segs)
        sample = self._build_sample(line, seg)
        async with self.session_maker() as s:
            await persistence.insert_samples(s, [sample])
            await persistence.trim_samples(s, keep=SAMPLE_RING)
            await s.commit()
        return _sample_detail_from_dict(sample)


def _sample_detail(row) -> dict:
    return {
        "id": row.id,
        "sim_time": row.sim_time,
        "segment_key": row.segment_key,
        "line_ad_id": row.line_ad_id,
        "won": row.won,
        "winner_seat": row.winner_seat,
        "winner_ad_id": row.winner_ad_id,
        "clearing": round(micros_to_usd(row.clearing_micros), 2),
        "floor": round(micros_to_usd(row.floor_micros), 2),
        "min_to_win": round(micros_to_usd(row.min_to_win_micros), 2),
        "request": json.loads(row.request_json),
        "bids": json.loads(row.bids_json),
        "notices": json.loads(row.notices_json),
    }


def _sample_detail_from_dict(d: dict) -> dict:
    return {
        "id": None,
        "sim_time": d["sim_time"],
        "segment_key": d["segment_key"],
        "line_ad_id": d["line_ad_id"],
        "won": d["won"],
        "winner_seat": d["winner_seat"],
        "winner_ad_id": d["winner_ad_id"],
        "clearing": round(micros_to_usd(d["clearing_micros"]), 2),
        "floor": round(micros_to_usd(d["floor_micros"]), 2),
        "min_to_win": round(micros_to_usd(d["min_to_win_micros"]), 2),
        "request": json.loads(d["request_json"]),
        "bids": json.loads(d["bids_json"]),
        "notices": json.loads(d["notices_json"]),
    }
