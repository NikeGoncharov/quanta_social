"""The seed roster of live campaigns the world loop delivers in Phase 2.

Phase 3 builds `Line`s from real DB rows (advertiser_accounts / campaigns / ad_sets / ads);
until then this fixed roster gives the glass-box something real to show. The four lines are
chosen to each surface a different lesson in the cabinet:

  Nimbus   — Conversions, roomy budget   -> the visible *learning phase* ramping up
  Lumen    — Awareness (CPM), broad       -> steady reach at base rates
  Voltmatic— Traffic (CPC), ASAP pacing   -> front-loaded delivery
  Meridian — Conversions, tiny budget     -> the *budget* limiter biting early

Brands are deliberately fictional (Acme-style), never real advertisers.
"""
import dataclasses
import json

from sqlalchemy import func, select

from ..adsim.dsp.campaign import Line, Targeting
from ..adsim.models.creative import NativeCreative
from ..adsim.models.enums import OBJECTIVE_BILLING, Objective, Pacing
from ..adsim.money import usd_to_micros
from ..models import Ad, AdSet, AdvertiserAccount, Campaign

# The account every user-created campaign lands under until Phase 4 gives each person their
# own. The seeded showcase campaigns keep their own per-brand demo accounts.
DEFAULT_ACCOUNT_ID = "acct-local"
DEFAULT_ACCOUNT_NAME = "My advertiser"


def _line(
    *,
    slug: str,
    brand: str,
    objective: Objective,
    bid_usd: float,
    daily_budget_usd: float,
    value_usd: float,
    targeting: Targeting,
    creative: NativeCreative,
    pacing: Pacing = Pacing.EVEN,
) -> Line:
    # `bid_micros` means: a CPM for Awareness, a CPC for Traffic, a target CPA for
    # Conversions — the strategy interprets it by objective. Billing follows the objective.
    return Line(
        ad_id=f"seed-{slug}-ad",
        ad_set_id=f"seed-{slug}-set",
        campaign_id=f"seed-{slug}-cmp",
        account_id=f"acct-{slug}",
        seat=f"acct-{slug}",
        objective=objective,
        bid_micros=usd_to_micros(bid_usd),
        billing_event=OBJECTIVE_BILLING[objective],
        targeting=targeting,
        daily_budget_micros=usd_to_micros(daily_budget_usd),
        baseline_conv_value_micros=usd_to_micros(value_usd),
        creative=creative,
        adomain=f"{slug}.example",
        pacing=pacing,
    )


def seed_lines() -> list[Line]:
    return [
        _line(
            slug="nimbus",
            brand="Nimbus",
            objective=Objective.CONVERSIONS,
            bid_usd=40.0,
            daily_budget_usd=500.0,
            value_usd=80.0,
            targeting=Targeting(interests=frozenset({"tech"}), geos=frozenset({"USA"})),
            creative=NativeCreative(
                title="Meet the new Nimbus X",
                body="Fast, quiet, unreasonably good.",
                cta_text="Shop now",
                brand_name="Nimbus",
                main_image_key="stock/tech-1.jpg",
                link_url="https://nimbus.example/x",
            ),
        ),
        _line(
            slug="lumen",
            brand="Lumen",
            objective=Objective.AWARENESS,
            bid_usd=6.0,
            daily_budget_usd=300.0,
            value_usd=60.0,
            targeting=Targeting(interests=frozenset({"home", "beauty"})),
            creative=NativeCreative(
                title="Lumen — light, reimagined",
                body="Warm, tunable, effortless.",
                cta_text="Discover",
                brand_name="Lumen",
                main_image_key="stock/home-1.jpg",
                link_url="https://lumen.example",
            ),
        ),
        _line(
            slug="voltmatic",
            brand="Voltmatic",
            objective=Objective.TRAFFIC,
            bid_usd=0.85,
            daily_budget_usd=200.0,
            value_usd=30.0,
            targeting=Targeting(interests=frozenset({"gaming"}), geos=frozenset({"USA", "GBR"})),
            creative=NativeCreative(
                title="Voltmatic: play louder",
                body="Zero-lag gear for competitive play.",
                cta_text="Play now",
                brand_name="Voltmatic",
                main_image_key="stock/gaming-1.jpg",
                link_url="https://voltmatic.example/play",
            ),
            pacing=Pacing.ASAP,
        ),
        _line(
            slug="meridian",
            brand="Meridian",
            objective=Objective.CONVERSIONS,
            bid_usd=55.0,
            daily_budget_usd=120.0,
            value_usd=220.0,
            targeting=Targeting(interests=frozenset({"finance"}), geos=frozenset({"USA"})),
            creative=NativeCreative(
                title="Meridian — banking that keeps up",
                body="Open an account in minutes.",
                cta_text="Get started",
                brand_name="Meridian",
                main_image_key="stock/finance-1.jpg",
                link_url="https://meridian.example/open",
            ),
        ),
    ]


# Display metadata for the cabinet (brand + a human label), keyed by the line's ad_id.
LINE_LABELS: dict[str, dict] = {
    "seed-nimbus-ad": {"brand": "Nimbus", "name": "Nimbus X launch"},
    "seed-lumen-ad": {"brand": "Lumen", "name": "Lumen awareness"},
    "seed-voltmatic-ad": {"brand": "Voltmatic", "name": "Voltmatic traffic"},
    "seed-meridian-ad": {"brand": "Meridian", "name": "Meridian signups"},
}


def creative_to_dict(creative: NativeCreative) -> dict:
    return dataclasses.asdict(creative)


async def ensure_seed_campaigns(session) -> None:
    """Materialize the canonical seed roster into the DB (once), plus the default user
    account. Idempotent: if any campaign already exists this is a no-op, so a dev DB carried
    over from Phase 2 keeps its history and its `seed-*` delivery buckets stay attached (the
    seeded rows reuse the exact ids `seed_lines()` produced).
    """
    already = (await session.execute(select(func.count()).select_from(Campaign))).scalar()
    if already:
        return

    session.add(
        AdvertiserAccount(
            id=DEFAULT_ACCOUNT_ID, name=DEFAULT_ACCOUNT_NAME, is_demo=False, created_at=0.0
        )
    )
    for ln in seed_lines():
        label = LINE_LABELS.get(ln.ad_id, {})
        brand = label.get("brand", ln.creative.brand_name)
        session.add(
            AdvertiserAccount(id=ln.account_id, name=brand, is_demo=True, created_at=0.0)
        )
        session.add(
            Campaign(
                id=ln.campaign_id,
                account_id=ln.account_id,
                name=label.get("name", ln.campaign_id),
                objective=ln.objective.value,
                status="active",
                daily_budget_micros=ln.daily_budget_micros,
                pacing=ln.pacing.value,
                baseline_conv_value_micros=ln.baseline_conv_value_micros,
                created_at=0.0,
            )
        )
        session.add(
            AdSet(
                id=ln.ad_set_id,
                campaign_id=ln.campaign_id,
                name=f"{brand} — main",
                status="active",
                bid_micros=ln.bid_micros,
                bid_strategy="manual",
                targeting_json=json.dumps(ln.targeting.to_dict()),
                freq_cap_impressions=(ln.freq_cap.impressions if ln.freq_cap else None),
                freq_cap_per_days=(ln.freq_cap.per_days if ln.freq_cap else 1),
            )
        )
        session.add(
            Ad(
                id=ln.ad_id,
                ad_set_id=ln.ad_set_id,
                name=ln.creative.title,
                status="active",
                creative_json=json.dumps(creative_to_dict(ln.creative)),
                adomain=ln.adomain,
            )
        )
