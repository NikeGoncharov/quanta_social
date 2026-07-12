"""The glass-box diagnostics for a live campaign: the plain-language 'why' (the one binding
limiter) and the bid landscape (win rate / CPM / results across a sweep of bids). Both read
the running world + delivery state through the runtime."""
from fastapi import APIRouter, HTTPException, Request

from ..sim.routes import get_runtime

router = APIRouter(prefix="/cabinet/campaigns", tags=["cabinet"])


@router.get("/{campaign_id}/why")
async def why(campaign_id: str, request: Request):
    return get_runtime(request).diagnose_campaign(campaign_id)


@router.get("/{campaign_id}/bid-landscape")
async def bid_landscape(campaign_id: str, request: Request):
    res = get_runtime(request).bid_landscape(campaign_id)
    if res is None:
        raise HTTPException(
            status_code=404, detail="campaign is not on air (paused/draft) — no live bid landscape"
        )
    return res
