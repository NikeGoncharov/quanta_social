"""Forward delivery estimate — what a line would deliver over a sim-day.

It integrates the day in float using the EXACT SAME economic helpers `run_tick` bids and
settles with (effective_ctr/cvr, effective_bid_micros, win_rate, cpm_paid_*, pacing,
freq_remaining_impressions, learning_lift) — only the binomial DRAW is replaced by its float
expectation. That distinction matters: `run_tick`'s expectation mode rounds every tiny
per-(tick, segment) funnel value to zero, which would report 0 clicks for a modest campaign;
carrying floats and rolling fatigue (cumulative impressions) and the learning signal forward
step by step gives the honest daily expectation while still tracking the mechanics the old
flat-snapshot closed form ignored (frequency cap, CTR fatigue, the learning ramp).

Powers the wizard estimate and the bid-landscape projection, so the numbers the cabinet
promises match what the world then delivers (the glass-box contract).
"""
from ..dsp.pacing import freq_remaining_impressions, pace_allowed_spend_micros
from ..dsp.strategy import effective_bid_micros
from ..dsp.targeting import is_interest_relevant, matching_segments
from ..mathx import cpm_paid_first_price, cpm_paid_second_price, win_rate
from ..models.enums import LEARNING_OBJECTIVES, AuctionType, Objective
from ..money import micros_to_usd
from ..simulation import segment_model as sm
from ..simulation.learning import learning_lift

SECONDS_PER_SIM_DAY = 86_400
DEFAULT_STEPS = 48  # 30-sim-minute steps: fine enough to integrate fatigue / learning / pacing


def estimate_delivery(world, line, *, steps: int = DEFAULT_STEPS) -> dict:
    """Project `line`'s delivery over one fresh sim-day. Returns USD-normalized totals, the
    opportunity-weighted realized win rate, and whether the daily budget was the binding cap.
    """
    eco = world.economy
    density = eco.market_density
    floor = eco.default_floor_micros
    at = AuctionType(eco.auction_type)
    is_learning = line.objective in LEARNING_OBJECTIVES

    segs = matching_segments(line.targeting, world)
    audience = sum(s.size for s in segs)

    cum_imp: dict = {}         # per-segment cumulative impressions (fatigue), float
    freq_shown: dict = {}      # per-segment impressions today (frequency cap), float
    signal = 0.0               # learning signal (conversions / engagements), float
    spent_micros = 0.0
    tot = {k: 0.0 for k in ("auctions", "impressions", "clicks", "conversions", "spend_micros", "revenue_micros")}
    spt = SECONDS_PER_SIM_DAY / steps

    for i in range(steps):
        day_fraction = min(1.0, (i + 1) / steps)
        allowed = pace_allowed_spend_micros(line, int(spent_micros), day_fraction)
        if allowed <= 0:
            continue
        lift = learning_lift(signal, world.learning, None) if is_learning else 1.0

        # Pass 1: per-segment economics + desired spend (mirrors run_tick, in float).
        plans = []
        total_desired = 0.0
        for seg in segs:
            relevant = is_interest_relevant(line.targeting, seg)
            ctr = sm.effective_ctr(seg, relevant, int(cum_imp.get(seg.id, 0.0)), world)
            cvr = sm.effective_cvr(seg, relevant, lift, world)
            opps = seg.opportunity_rate * spt
            freq_left = freq_remaining_impressions(line, seg, int(freq_shown.get(seg.id, 0.0)))
            available = min(opps, freq_left)
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
            total_desired += available * wr * cpm / 1000.0
            plans.append((seg, ctr, cvr, available, wr, cpm))

        if not plans:
            continue
        budget_scale = 1.0 if total_desired <= allowed else (allowed / total_desired if total_desired > 0 else 0.0)

        for seg, ctr, cvr, available, wr, cpm in plans:
            imps = available * min(1.0, wr * budget_scale)
            if imps <= 0:
                continue
            spend = imps * cpm / 1000.0
            clicks = imps * ctr
            conv = clicks * cvr
            tot["auctions"] += available
            tot["impressions"] += imps
            tot["clicks"] += clicks
            tot["conversions"] += conv
            tot["spend_micros"] += spend
            tot["revenue_micros"] += conv * sm.conversion_value_micros(line, seg)
            cum_imp[seg.id] = cum_imp.get(seg.id, 0.0) + imps
            freq_shown[seg.id] = freq_shown.get(seg.id, 0.0) + imps
            spent_micros += spend
            if line.objective == Objective.CONVERSIONS:
                signal += conv
            elif line.objective == Objective.ENGAGEMENT:
                signal += clicks

    budget = line.daily_budget_micros
    win_rate_out = round(tot["impressions"] / tot["auctions"], 4) if tot["auctions"] else 0.0
    return {
        "audience": int(audience),
        "segments": len(segs),
        "auctions": int(round(tot["auctions"])),
        "impressions": int(round(tot["impressions"])),
        "clicks": int(round(tot["clicks"])),
        "conversions": int(round(tot["conversions"])),
        "spend": round(micros_to_usd(tot["spend_micros"]), 2),
        "revenue": round(micros_to_usd(tot["revenue_micros"]), 2),
        "win_rate": win_rate_out,
        # Float pacing spends exactly up to the budget when demand allows (no truncation), so
        # near-full spend is an honest 'budget is the limiter' signal.
        "budget_capped": bool(budget) and tot["spend_micros"] >= budget * 0.99,
    }
