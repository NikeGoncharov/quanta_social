"""Cabinet reporting — reads straight from the delivery buckets (the aggregate is the
source of truth), so totals reconcile exactly with the live dashboard. KPIs come with a
window-over-window delta; the breakdown explores interest / geo / age / gender."""
from fastapi import APIRouter, Depends, HTTPException

from ..adsim.metrics.kpis import Kpis
from ..adsim.money import micros_to_usd
from ..database import get_db
from ..sim import persistence
from ..sim.runtime import to_delivery_point

router = APIRouter(prefix="/cabinet/reporting", tags=["cabinet"])

DIMENSIONS = ("interest", "geo", "age_band", "gender")
_DELTA_METRICS = ("impressions", "clicks", "conversions", "spend", "revenue", "ctr", "cpa", "roas")
MAX_WINDOW = 20_160  # ~14 sim-days of minutes


def _pct_delta(cur, prev):
    if cur is None or prev is None:
        return None
    if prev == 0:
        return None if cur == 0 else 1.0  # grew from nothing — undefined ratio, flag as "new"
    return round((cur - prev) / prev, 4)


@router.get("/kpis")
async def kpis(campaign_id: str | None = None, window: int = 1440, db=Depends(get_db)):
    """Totals for the newest `window` sim-minutes vs the window before it (all campaigns or
    one). Anchored to the last recorded bucket, not the live clock."""
    window = max(1, min(window, MAX_WINDOW))
    latest = await persistence.latest_bucket(db, campaign_id=campaign_id)
    if latest is None:
        empty = Kpis().to_dict()
        return {"current": empty, "previous": empty, "deltas": {}, "window": window, "anchor": None}
    end = latest + 1
    cur = await persistence.kpi_totals(db, start=end - window, end=end, campaign_id=campaign_id)
    prev = await persistence.kpi_totals(db, start=end - 2 * window, end=end - window, campaign_id=campaign_id)
    cur_k, prev_k = Kpis(**cur).to_dict(), Kpis(**prev).to_dict()
    deltas = {m: _pct_delta(cur_k.get(m), prev_k.get(m)) for m in _DELTA_METRICS}
    return {"current": cur_k, "previous": prev_k, "deltas": deltas, "window": window, "anchor": latest}


@router.get("/timeseries")
async def timeseries(campaign_id: str | None = None, bin: int = 30, window: int = 48, db=Depends(get_db)):
    """Delivery rolled into uniform bins (same rollup the dashboard history uses)."""
    bin_minutes = max(1, min(bin, 240))
    bins = max(1, min(window, 400))
    rows = await persistence.read_history(db, bin_minutes=bin_minutes, bins=bins, campaign_id=campaign_id)
    for r in rows:
        r["covered_seconds"] = bin_minutes * 60
    return {"bin": bin_minutes, "points": [to_delivery_point(r) for r in rows]}


@router.get("/breakdown")
async def breakdown(dimension: str, campaign_id: str | None = None, window: int = 1440, db=Depends(get_db)):
    """Delivery split along one audience dimension over the newest `window` sim-minutes,
    ranked by impressions."""
    if dimension not in DIMENSIONS:
        raise HTTPException(status_code=400, detail=f"dimension must be one of {DIMENSIONS}")
    window = max(1, min(window, MAX_WINDOW))
    rows = await persistence.read_breakdowns(db, dimension=dimension, campaign_id=campaign_id, window=window)
    out = []
    for r in rows:
        imps, clicks = r["impressions"], r["clicks"]
        out.append(
            {
                "value": r["value"],
                "impressions": imps,
                "clicks": clicks,
                "conversions": r["conversions"],
                "spend": round(micros_to_usd(r["spend_micros"]), 2),
                "revenue": round(micros_to_usd(r["revenue_micros"]), 2),
                "ctr": round(clicks / imps, 4) if imps else None,
            }
        )
    out.sort(key=lambda d: d["impressions"], reverse=True)
    return {"dimension": dimension, "rows": out}
