"""The create-wizard's live estimate: what a not-yet-published campaign would deliver, using
the exact bid math the world then runs. Publishing is a plain POST /cabinet/campaigns."""
from fastapi import APIRouter, Request

from ..adsim.dsp.campaign import FreqCap
from ..adsim.money import usd_to_micros
from ..sim.routes import get_runtime
from .schemas import EstimateBody
from .service import RESULT_LABEL_STR, provisional_line

router = APIRouter(prefix="/cabinet/wizard", tags=["cabinet"])


@router.post("/estimate")
async def estimate(body: EstimateBody, request: Request):
    """Project one sim-day of delivery for the proposed campaign (fresh: learning start, no
    fatigue), so the wizard shows reach / impressions / results / spend before publishing."""
    rt = get_runtime(request)
    freq = (
        FreqCap(impressions=body.freq_cap_impressions, per_days=body.freq_cap_per_days)
        if body.freq_cap_impressions
        else None
    )
    line = provisional_line(
        objective=body.objective,
        targeting=body.targeting.model_dump(),
        bid_micros=usd_to_micros(body.bid_usd),
        daily_budget_micros=usd_to_micros(body.daily_budget_usd),
        value_micros=usd_to_micros(body.value_usd),
        freq_cap=freq,
    )
    est = rt.estimate_line(line)  # one-sim-day projection via run_tick replay
    result_key = {
        "awareness": "impressions",
        "traffic": "clicks",
        "engagement": "clicks",
        "conversions": "conversions",
    }[body.objective]
    est["results"] = est[result_key]
    est["result_label"] = RESULT_LABEL_STR[body.objective]
    return est
