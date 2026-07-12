"""Advertiser accounts. Until Phase 4 auth lands, the cabinet operates on a single default
local account (auto-created); the seeded demo accounts are also listed for the showcase."""
from fastapi import APIRouter, Depends
from sqlalchemy import select

from ..database import get_db
from ..models import AdvertiserAccount
from ..sim.seed import DEFAULT_ACCOUNT_ID, DEFAULT_ACCOUNT_NAME

router = APIRouter(prefix="/cabinet", tags=["cabinet"])


def _acct(a: AdvertiserAccount) -> dict:
    return {"id": a.id, "name": a.name, "currency": a.currency, "is_demo": a.is_demo}


@router.get("/account")
async def get_default_account(db=Depends(get_db)):
    """The current advertiser (the local account), creating it on first use."""
    acct = await db.get(AdvertiserAccount, DEFAULT_ACCOUNT_ID)
    if acct is None:
        acct = AdvertiserAccount(
            id=DEFAULT_ACCOUNT_ID, name=DEFAULT_ACCOUNT_NAME, is_demo=False, created_at=0.0
        )
        db.add(acct)
        await db.commit()
    return _acct(acct)


@router.get("/accounts")
async def list_accounts(db=Depends(get_db)):
    rows = (await db.execute(select(AdvertiserAccount).order_by(AdvertiserAccount.created_at))).scalars().all()
    return {"accounts": [_acct(a) for a in rows]}
