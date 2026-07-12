"""Build engine `Line`s from the DB advertiser hierarchy (account -> campaign -> ad_set
-> ad). This is the Phase 3 replacement for the hardcoded `seed_lines()` roster: the world
loop calls `load_lines` at startup and after every cabinet edit, so user-created campaigns
join the live auction and edits take effect within a tick.

Only fully-active rows (campaign AND ad_set AND ad status == 'active') become live lines —
paused / draft campaigns simply drop out of the engine (the cabinet grid reads the DB
directly to show them). Because delivery state (spend, learning, fatigue) is keyed by the
stable `ad_id` / `ad_set_id`, rebuilding the line list never resets a running campaign.
"""
import json

from sqlalchemy import select

from ..adsim.dsp.campaign import FreqCap, Line, Targeting
from ..adsim.models.creative import NativeCreative
from ..adsim.models.enums import OBJECTIVE_BILLING, Objective, Pacing
from ..models import Ad, AdSet, Campaign

ACTIVE = "active"


def _line_from_rows(cmp: Campaign, aset: AdSet, ad: Ad) -> Line:
    objective = Objective(cmp.objective)
    targeting = Targeting.from_dict(json.loads(aset.targeting_json or "{}"))
    creative = NativeCreative.from_dict(json.loads(ad.creative_json or "{}"))
    freq = (
        FreqCap(impressions=aset.freq_cap_impressions, per_days=aset.freq_cap_per_days)
        if aset.freq_cap_impressions
        else None
    )
    return Line(
        ad_id=ad.id,
        ad_set_id=aset.id,
        campaign_id=cmp.id,
        account_id=cmp.account_id,
        seat=cmp.account_id,
        objective=objective,
        bid_micros=aset.bid_micros,
        billing_event=OBJECTIVE_BILLING[objective],
        targeting=targeting,
        daily_budget_micros=cmp.daily_budget_micros,
        baseline_conv_value_micros=cmp.baseline_conv_value_micros,
        creative=creative,
        adomain=ad.adomain,
        freq_cap=freq,
        pacing=Pacing(cmp.pacing),
        active=True,
    )


async def load_lines(session) -> tuple[list[Line], dict[str, dict]]:
    """Return (lines, labels). `lines` are the fully-active campaigns flattened for the
    engine; `labels` maps ad_id -> display metadata (brand / campaign name / account) the
    runtime status blends in, replacing the static seed LINE_LABELS."""
    q = (
        select(Campaign, AdSet, Ad)
        .join(AdSet, AdSet.campaign_id == Campaign.id)
        .join(Ad, Ad.ad_set_id == AdSet.id)
        .where(
            Campaign.status == ACTIVE,
            AdSet.status == ACTIVE,
            Ad.status == ACTIVE,
        )
        .order_by(Campaign.created_at, Campaign.id)
    )
    rows = (await session.execute(q)).all()
    lines: list[Line] = []
    labels: dict[str, dict] = {}
    for cmp, aset, ad in rows:
        line = _line_from_rows(cmp, aset, ad)
        lines.append(line)
        labels[ad.id] = {
            "brand": line.creative.brand_name,
            "name": cmp.name,
            "account_id": cmp.account_id,
            "objective": cmp.objective,
        }
    return lines, labels
