"""run_tick — the statistical heart of the world.

For each active line x matching segment it computes the expected auction outcome and draws
impressions/clicks/conversions with binomial/multinomial (reused from rng), producing
compact per-segment deltas. It NEVER materializes one row per impression: synthetic volume
lives as aggregates. Pure and deterministic given its inputs (the async loop and DB writer
that call it live in Phase 2).

Per (line, segment) each tick:
  1. effective CTR/CVR   (relevance uplift, fatigue, learning lift)
  2. opportunities       = segment.opportunity_rate * sim_seconds_per_tick
  3. gates               frequency cap; budget pacing throttles participation
  4. bid -> win rate     eCPM vs the segment's density-scaled reference bid
  5. settle              clearing CPM (first- or second-price aggregate)
  6. draw                impressions <= auctions, clicks <= impressions, conversions <= clicks
  7. accrue              spend, revenue; update budget / frequency / fatigue / learning state
"""
from dataclasses import dataclass

from ..dsp.pacing import freq_remaining_impressions, pace_allowed_spend_micros
from ..dsp.strategy import effective_bid_micros
from ..dsp.targeting import is_interest_relevant, matching_segments
from ..mathx import cpm_paid_first_price, cpm_paid_second_price, win_rate
from ..models.enums import LEARNING_OBJECTIVES, AuctionType, Objective
from ..money import spend_micros
from ..rng import binomial, substream
from . import segment_model as sm
from .learning import learning_lift


@dataclass
class SegmentDelta:
    ad_id: str
    ad_set_id: str
    campaign_id: str
    account_id: str
    interest: str
    geo: str
    age_band: str
    gender: str
    auctions: int
    impressions: int
    clicks: int
    conversions: int
    spend_micros: int
    revenue_micros: int


def run_tick(
    world,
    lines,
    state,
    *,
    sim_seconds_per_tick: float,
    day_fraction: float,
    tick_index: int,
    seed: int = 0,
    stochastic: bool = True,
) -> list[SegmentDelta]:
    deltas: list[SegmentDelta] = []
    density = world.economy.market_density
    at = AuctionType(world.economy.auction_type)
    floor = world.economy.default_floor_micros

    for line in lines:
        if not line.active:
            continue
        spent_today = state.spent_today_micros.get(line.ad_id, 0)
        allowed = pace_allowed_spend_micros(line, spent_today, day_fraction)
        if allowed <= 0:
            continue

        if line.objective in LEARNING_OBJECTIVES:
            rng_learn = substream(seed, tick_index, "learn", line.ad_set_id) if stochastic else None
            lift = learning_lift(
                state.learning_signal.get(line.ad_set_id, 0.0), world.learning, rng_learn
            )
        else:
            lift = 1.0

        # --- Pass 1: per-segment economics ---
        plans = []
        total_desired = 0
        for seg in matching_segments(line.targeting, world):
            relevant = is_interest_relevant(line.targeting, seg)
            cum_imp = state.cum_impressions.get((line.ad_id, seg.id), 0)
            ctr = sm.effective_ctr(seg, relevant, cum_imp, world)
            cvr = sm.effective_cvr(seg, relevant, lift, world)
            opps = seg.opportunity_rate * sim_seconds_per_tick
            freq_left = freq_remaining_impressions(
                line, seg, state.freq_shown_today.get((line.campaign_id, seg.id), 0)
            )
            available = int(round(min(opps, freq_left)))
            if available <= 0:
                continue
            ebid = effective_bid_micros(line, ctr, cvr)
            ref = int(seg.reference_bid_micros * density)
            wr = win_rate(ebid, ref) if ebid >= floor else 0.0
            if wr <= 0.0:
                continue
            cpm = (
                cpm_paid_first_price(ebid)
                if at == AuctionType.FIRST_PRICE
                else cpm_paid_second_price(ebid, ref, wr)
            )
            cpm = max(cpm, floor)
            total_desired += spend_micros(int(round(available * wr)), cpm)
            plans.append((seg, ctr, cvr, available, wr, cpm))

        if not plans:
            continue

        # Budget pacing throttles participation so expected spend fits `allowed`.
        budget_scale = 1.0 if total_desired <= allowed else (
            allowed / total_desired if total_desired > 0 else 0.0
        )

        spent_this_tick = 0
        for (seg, ctr, cvr, available, wr, cpm) in plans:
            if spent_this_tick >= allowed:
                break
            p_win = min(1.0, wr * budget_scale)
            rng_imp = substream(seed, tick_index, "imp", f"{line.ad_id}:{seg.id}") if stochastic else None
            impressions = binomial(available, p_win, rng_imp, stochastic)
            # Hard budget clamp — guarantees the daily budget is never exceeded.
            if cpm > 0:
                max_imps = (allowed - spent_this_tick) * 1000 // cpm
                impressions = min(impressions, int(max_imps))
            if impressions <= 0:
                continue
            spend = spend_micros(impressions, cpm)
            spent_this_tick += spend

            rng_click = substream(seed, tick_index, "clk", f"{line.ad_id}:{seg.id}") if stochastic else None
            clicks = binomial(impressions, ctr, rng_click, stochastic)
            rng_conv = substream(seed, tick_index, "cnv", f"{line.ad_id}:{seg.id}") if stochastic else None
            conversions = binomial(clicks, cvr, rng_conv, stochastic)
            revenue = conversions * sm.conversion_value_micros(line, seg)

            # --- accrue state ---
            state.spent_today_micros[line.ad_id] = spent_today + spent_this_tick
            state.spent_lifetime_micros[line.ad_id] = (
                state.spent_lifetime_micros.get(line.ad_id, 0) + spend
            )
            fk = (line.campaign_id, seg.id)
            state.freq_shown_today[fk] = state.freq_shown_today.get(fk, 0) + impressions
            ck = (line.ad_id, seg.id)
            state.cum_impressions[ck] = state.cum_impressions.get(ck, 0) + impressions
            if line.objective == Objective.CONVERSIONS:
                state.learning_signal[line.ad_set_id] = (
                    state.learning_signal.get(line.ad_set_id, 0.0) + conversions
                )
            elif line.objective == Objective.ENGAGEMENT:
                state.learning_signal[line.ad_set_id] = (
                    state.learning_signal.get(line.ad_set_id, 0.0) + clicks
                )

            deltas.append(
                SegmentDelta(
                    ad_id=line.ad_id,
                    ad_set_id=line.ad_set_id,
                    campaign_id=line.campaign_id,
                    account_id=line.account_id,
                    interest=seg.interest,
                    geo=seg.geo,
                    age_band=seg.age_band,
                    gender=seg.gender,
                    auctions=available,
                    impressions=impressions,
                    clicks=clicks,
                    conversions=conversions,
                    spend_micros=spend,
                    revenue_micros=revenue,
                )
            )

    return deltas
