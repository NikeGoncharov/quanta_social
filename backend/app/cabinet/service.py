"""Cabinet service helpers: build DB rows from request bodies, apply partial edits, and
shape rows for the grid / detail / estimate. Money crosses here (USD floats <-> micros)."""
import json
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy import select

from ..adsim.dsp.campaign import FreqCap, Line, Targeting
from ..adsim.models.creative import NativeCreative
from ..adsim.models.enums import FUNNEL_STAGE, OBJECTIVE_BILLING, Objective
from ..adsim.money import micros_to_usd, usd_to_micros
from ..models import Ad, AdSet, AdvertiserAccount, Campaign
from ..sim.seed import DEFAULT_ACCOUNT_ID, DEFAULT_ACCOUNT_NAME
from .schemas import CampaignCreate, CampaignPatch

# String-keyed views of the engine's objective maps, for JSON payloads.
FUNNEL_STAGE_STR = {o.value: v for o, v in FUNNEL_STAGE.items()}
BID_LABEL_STR = {
    "awareness": "CPM",
    "traffic": "CPC",
    "engagement": "Cost / eng.",
    "conversions": "Target CPA",
}
RESULT_LABEL_STR = {
    "awareness": "impressions",
    "traffic": "clicks",
    "engagement": "engagements",
    "conversions": "conversions",
}


def _domain_from(url: str) -> str:
    """Best-effort advertiser domain (adomain) from a creative link — used in the OpenRTB
    bid's `adomain`, which the exchange's badv filtering reads."""
    if not url:
        return ""
    try:
        host = urlparse(url).netloc or urlparse("//" + url.strip()).netloc
    except ValueError:
        return ""
    host = host.lower()
    return host[4:] if host.startswith("www.") else host


def provisional_line(
    *,
    objective: str,
    targeting: dict,
    bid_micros: int,
    daily_budget_micros: int,
    value_micros: int,
    freq_cap: FreqCap | None = None,
) -> Line:
    """A throwaway Line for the wizard estimate — only the fields the estimate reads matter
    (objective, targeting, bid, budget, conversion value, freq cap); the creative is a
    placeholder. The freq cap must be carried so the estimate honors it, matching delivery."""
    obj = Objective(objective)
    return Line(
        ad_id="_estimate",
        ad_set_id="_estimate",
        campaign_id="_estimate",
        account_id="_estimate",
        seat="_estimate",
        objective=obj,
        bid_micros=bid_micros,
        billing_event=OBJECTIVE_BILLING[obj],
        targeting=Targeting.from_dict(targeting),
        daily_budget_micros=daily_budget_micros,
        baseline_conv_value_micros=value_micros,
        creative=NativeCreative(
            title="", body="", cta_text="", brand_name="", main_image_key="", link_url=""
        ),
        freq_cap=freq_cap,
    )


async def create_campaign(session, body: CampaignCreate, *, now: float) -> Campaign:
    """Insert account (if missing) + campaign + ad set + ad in one unit of work (v1's
    1 campaign -> 1 ad set -> 1 ad shape). Ad-set / ad status track the campaign so a draft
    stays out of the engine. Caller commits."""
    account_id = body.account_id or DEFAULT_ACCOUNT_ID
    if await session.get(AdvertiserAccount, account_id) is None:
        session.add(
            AdvertiserAccount(
                id=account_id,
                name=DEFAULT_ACCOUNT_NAME if account_id == DEFAULT_ACCOUNT_ID else account_id,
                is_demo=False,
                created_at=now,
            )
        )
    cid = f"cmp-{uuid4().hex[:8]}"
    sid = f"set-{uuid4().hex[:8]}"
    aid = f"ad-{uuid4().hex[:8]}"
    campaign = Campaign(
        id=cid,
        account_id=account_id,
        name=body.name,
        objective=body.objective,
        status=body.status,
        daily_budget_micros=usd_to_micros(body.daily_budget_usd),
        pacing=body.pacing,
        baseline_conv_value_micros=usd_to_micros(body.value_usd),
        created_at=now,
    )
    ad_set = AdSet(
        id=sid,
        campaign_id=cid,
        name=f"{body.name} — main",
        status=body.status,
        bid_micros=usd_to_micros(body.bid_usd),
        bid_strategy="manual",
        targeting_json=json.dumps(body.targeting.model_dump()),
        freq_cap_impressions=body.freq_cap_impressions,
        freq_cap_per_days=body.freq_cap_per_days,
    )
    ad = Ad(
        id=aid,
        ad_set_id=sid,
        name=body.creative.title,
        status=body.status,
        creative_json=json.dumps(body.creative.model_dump()),
        adomain=_domain_from(body.creative.link_url),
    )
    session.add_all([campaign, ad_set, ad])
    return campaign


def apply_patch(campaign: Campaign, ad_set: AdSet, ad: Ad, patch: CampaignPatch) -> None:
    """Apply only the fields present in the request. Objective is immutable in v1 (it changes
    billing / learning semantics), so it is not patchable. An explicit JSON null for a
    non-nullable field is treated as 'no change' (never written), so it can't crash the
    request; only `freq_cap_impressions` may be nulled — to clear the cap."""
    fields = patch.model_dump(exclude_unset=True)

    def given(key):
        return key in fields and fields[key] is not None

    if given("name"):
        campaign.name = fields["name"]
        ad_set.name = f"{fields['name']} — main"
    if given("status"):
        campaign.status = ad_set.status = ad.status = fields["status"]
    if given("daily_budget_usd"):
        campaign.daily_budget_micros = usd_to_micros(fields["daily_budget_usd"])
    if given("pacing"):
        campaign.pacing = fields["pacing"]
    if given("value_usd"):
        campaign.baseline_conv_value_micros = usd_to_micros(fields["value_usd"])
    if given("bid_usd"):
        ad_set.bid_micros = usd_to_micros(fields["bid_usd"])
    if patch.targeting is not None:
        ad_set.targeting_json = json.dumps(patch.targeting.model_dump())
    if patch.creative is not None:
        ad.creative_json = json.dumps(patch.creative.model_dump())
        ad.name = patch.creative.title
        ad.adomain = _domain_from(patch.creative.link_url)
    if "freq_cap_impressions" in fields:  # None here intentionally clears the cap
        ad_set.freq_cap_impressions = fields["freq_cap_impressions"]
    if given("freq_cap_per_days"):
        ad_set.freq_cap_per_days = fields["freq_cap_per_days"]


async def load_campaign_rows(session, *, account_id: str | None = None):
    """All campaigns (any status) with their ad set + ad, newest first."""
    q = (
        select(Campaign, AdSet, Ad)
        .join(AdSet, AdSet.campaign_id == Campaign.id)
        .join(Ad, Ad.ad_set_id == AdSet.id)
        .order_by(Campaign.created_at.desc(), Campaign.id.desc())
    )
    if account_id:
        q = q.where(Campaign.account_id == account_id)
    return (await session.execute(q)).all()


async def load_one(session, campaign_id: str):
    q = (
        select(Campaign, AdSet, Ad)
        .join(AdSet, AdSet.campaign_id == Campaign.id)
        .join(Ad, Ad.ad_set_id == AdSet.id)
        .where(Campaign.id == campaign_id)
    )
    return (await session.execute(q)).first()


def grid_row(cmp: Campaign, aset: AdSet, ad: Ad, live: dict | None) -> dict:
    """A grid row: the DB source-of-truth fields plus the live delivery block (from the
    runtime status) when the campaign is on air — None for paused / draft."""
    creative = json.loads(ad.creative_json or "{}")
    return {
        "campaign_id": cmp.id,
        "ad_id": ad.id,
        "ad_set_id": aset.id,
        "account_id": cmp.account_id,
        "name": cmp.name,
        "brand": creative.get("brand_name", ""),
        "objective": cmp.objective,
        "funnel_stage": FUNNEL_STAGE_STR.get(cmp.objective),
        "status": cmp.status,
        "pacing": cmp.pacing,
        "daily_budget": round(micros_to_usd(cmp.daily_budget_micros), 2),
        "bid": round(micros_to_usd(aset.bid_micros), 2),
        "bid_label": BID_LABEL_STR.get(cmp.objective, "Bid"),
        "created_at": cmp.created_at,
        "live": live,
    }


def campaign_detail(cmp: Campaign, aset: AdSet, ad: Ad) -> dict:
    """Full campaign for the detail / edit view (USD-normalized, targeting + creative)."""
    return {
        "campaign_id": cmp.id,
        "ad_id": ad.id,
        "ad_set_id": aset.id,
        "account_id": cmp.account_id,
        "name": cmp.name,
        "objective": cmp.objective,
        "funnel_stage": FUNNEL_STAGE_STR.get(cmp.objective),
        "status": cmp.status,
        "pacing": cmp.pacing,
        "daily_budget_usd": round(micros_to_usd(cmp.daily_budget_micros), 2),
        "bid_usd": round(micros_to_usd(aset.bid_micros), 2),
        "bid_label": BID_LABEL_STR.get(cmp.objective, "Bid"),
        "result_label": RESULT_LABEL_STR.get(cmp.objective, "results"),
        "value_usd": round(micros_to_usd(cmp.baseline_conv_value_micros), 2),
        "targeting": json.loads(aset.targeting_json or "{}"),
        "creative": json.loads(ad.creative_json or "{}"),
        "freq_cap_impressions": aset.freq_cap_impressions,
        "freq_cap_per_days": aset.freq_cap_per_days,
        "created_at": cmp.created_at,
    }
