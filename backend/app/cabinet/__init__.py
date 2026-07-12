"""The Quanta Ads cabinet API (Phase 3). Mounted at /cabinet (the SPA calls /api/cabinet/...).

Sub-routers by concern: accounts, campaigns (CRUD + grid), wizard (estimate), reporting
(kpis / timeseries / breakdown), targeting (options + audience), diagnostics (why /
bid-landscape). Aggregated into one `router` the app includes.
"""
from fastapi import APIRouter

from . import accounts, campaigns, diagnostics, reporting, targeting, wizard

router = APIRouter()
for _module in (accounts, campaigns, wizard, reporting, targeting, diagnostics):
    router.include_router(_module.router)
