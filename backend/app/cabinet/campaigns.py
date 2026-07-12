"""Campaign CRUD + the grid. Every mutation commits, then asks the world loop to reload its
roster so the change is live within a tick (new campaign starts bidding; paused one drops
out; an edit re-targets / re-bids). The grid merges DB source-of-truth with live delivery."""
import time

from fastapi import APIRouter, Depends, HTTPException, Request

from ..database import get_db
from . import service
from .schemas import CampaignCreate, CampaignPatch

router = APIRouter(prefix="/cabinet", tags=["cabinet"])


def _request_reload(request: Request) -> None:
    rt = getattr(request.app.state, "runtime", None)
    if rt is not None:
        rt.request_reload()


@router.get("/grid")
async def grid(request: Request, account_id: str | None = None, db=Depends(get_db)):
    rows = await service.load_campaign_rows(db, account_id=account_id)
    rt = getattr(request.app.state, "runtime", None)
    live_by_ad: dict[str, dict] = {}
    if rt is not None:
        live_by_ad = {ln["ad_id"]: ln for ln in rt.status()["lines"]}
    return {"rows": [service.grid_row(c, s, a, live_by_ad.get(a.id)) for (c, s, a) in rows]}


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str, db=Depends(get_db)):
    row = await service.load_one(db, campaign_id)
    if row is None:
        raise HTTPException(status_code=404, detail="campaign not found")
    return service.campaign_detail(*row)


@router.post("/campaigns", status_code=201)
async def create_campaign(body: CampaignCreate, request: Request, db=Depends(get_db)):
    campaign = await service.create_campaign(db, body, now=time.time())
    await db.commit()
    _request_reload(request)
    return service.campaign_detail(*await service.load_one(db, campaign.id))


@router.patch("/campaigns/{campaign_id}")
async def patch_campaign(campaign_id: str, patch: CampaignPatch, request: Request, db=Depends(get_db)):
    row = await service.load_one(db, campaign_id)
    if row is None:
        raise HTTPException(status_code=404, detail="campaign not found")
    service.apply_patch(*row, patch)
    await db.commit()
    _request_reload(request)
    return service.campaign_detail(*await service.load_one(db, campaign_id))


@router.delete("/campaigns/{campaign_id}", status_code=204)
async def delete_campaign(campaign_id: str, request: Request, db=Depends(get_db)):
    row = await service.load_one(db, campaign_id)
    if row is None:
        raise HTTPException(status_code=404, detail="campaign not found")
    cmp, aset, ad = row
    # Hard delete the triple. Historical delivery buckets stay (join-by-convention), so past
    # reporting is preserved even after the campaign is gone.
    await db.delete(ad)
    await db.delete(aset)
    await db.delete(cmp)
    await db.commit()
    _request_reload(request)
