"""Forward delivery estimate — what a line would deliver over a window, computed with the
exact same expectation math `run_tick` bids and settles with (no random draws). Powers the
wizard's live estimate and the bid-landscape's per-bid projection, so the numbers the
cabinet promises match what the world then delivers (the glass-box contract).

For a brand-new campaign the state is fresh: no cumulative impressions (no fatigue) and,
for optimized objectives, the learning phase's `start_lift`. Callers with a live campaign
pass its current lift and a cumulative-impression lookup to project from where it is now.
"""
from ..dsp.strategy import effective_bid_micros
from ..dsp.targeting import is_interest_relevant, matching_segments
from ..mathx import cpm_paid_first_price, cpm_paid_second_price, win_rate
from ..models.enums import LEARNING_OBJECTIVES, AuctionType
from ..money import micros_to_usd, spend_micros
from ..simulation import segment_model as sm

SECONDS_PER_SIM_DAY = 86_400


def estimate_delivery(
    world,
    line,
    *,
    seconds: int = SECONDS_PER_SIM_DAY,
    lift: float | None = None,
    cum_imp_fn=None,
) -> dict:
    """Project `line`'s delivery over `seconds` of sim time. `cum_imp_fn(seg_id) -> int`
    supplies per-segment cumulative impressions (fatigue); default 0. Returns USD-normalized
    counts, spend/revenue capped to the pro-rated daily budget, and the opportunity-weighted
    win rate."""
    eco = world.economy
    density = eco.market_density
    floor = eco.default_floor_micros
    at = AuctionType(eco.auction_type)
    if lift is None:
        lift = world.learning.start_lift if line.objective in LEARNING_OBJECTIVES else 1.0

    segs = matching_segments(line.targeting, world)
    audience = sum(s.size for s in segs)

    exp_auctions = exp_impr = exp_clicks = exp_conv = 0.0
    exp_spend_micros = exp_rev_micros = 0.0
    wr_weighted = weight = 0.0

    for seg in segs:
        relevant = is_interest_relevant(line.targeting, seg)
        cum = cum_imp_fn(seg.id) if cum_imp_fn else 0
        ctr = sm.effective_ctr(seg, relevant, cum, world)
        cvr = sm.effective_cvr(seg, relevant, lift, world)
        opps = seg.opportunity_rate * seconds
        ebid = effective_bid_micros(line, ctr, cvr)
        ref = int(seg.reference_bid_micros * density)
        wr = win_rate(ebid, ref) if ebid >= floor else 0.0
        weight += seg.opportunity_rate
        wr_weighted += wr * seg.opportunity_rate
        if wr <= 0.0:
            continue
        cpm = (
            cpm_paid_first_price(ebid)
            if at == AuctionType.FIRST_PRICE
            else cpm_paid_second_price(ebid, ref, wr)
        )
        cpm = max(cpm, floor)
        imps = opps * wr
        exp_auctions += opps
        exp_impr += imps
        exp_clicks += imps * ctr
        exp_conv += imps * ctr * cvr
        exp_spend_micros += spend_micros(int(imps), cpm)
        exp_rev_micros += imps * ctr * cvr * sm.conversion_value_micros(line, seg)

    # Budget pacing: an even-paced line can't spend more than the (pro-rated) daily budget
    # over the window; scale the volumes down proportionally, matching run_tick's throttle.
    budget_window = (
        line.daily_budget_micros * (seconds / SECONDS_PER_SIM_DAY)
        if line.daily_budget_micros
        else exp_spend_micros
    )
    capped = bool(line.daily_budget_micros) and exp_spend_micros > budget_window
    scale = (budget_window / exp_spend_micros) if capped and exp_spend_micros > 0 else 1.0
    final_spend_micros = min(exp_spend_micros, budget_window) if line.daily_budget_micros else exp_spend_micros

    return {
        "audience": int(audience),
        "segments": len(segs),
        "auctions": int(exp_auctions * scale),
        "impressions": int(exp_impr * scale),
        "clicks": int(exp_clicks * scale),
        "conversions": int(exp_conv * scale),
        "spend": round(micros_to_usd(final_spend_micros), 2),
        "revenue": round(micros_to_usd(exp_rev_micros * scale), 2),
        "win_rate": round(wr_weighted / weight, 4) if weight > 0 else 0.0,
        "budget_capped": capped,
    }
