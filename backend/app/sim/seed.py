"""The seed roster of live campaigns the world loop delivers (Phase 3 builds `Line`s from real
DB rows; this roster is what `ensure_seed_campaigns` materializes on first boot).

The first four lines each surface a different lesson in the cabinet:

  Nimbus   — Conversions, roomy budget, tech/USA -> the visible *learning phase* ramping up
  Lumen    — Awareness (CPM), broad               -> steady reach at base rates
  Voltmatic— Traffic (CPC), ASAP pacing           -> front-loaded delivery
  Meridian — Conversions, tiny budget             -> the *budget* limiter biting early

Phase 5 adds five more so a visitor of ANY interest, in any geo, sees a relevant sponsored
auction in their feed (Verdano / Wander / Tempo / Marlowe cover the remaining interests;
Kinbara is an untargeted broad-reach house line that clears when nothing else does). Only
Nimbus keeps a single-geo target, so the geo-exclusion lesson still shows in the cabinet.

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
            # Broad geo so a gaming fan anywhere sees it (Nimbus keeps the single-geo lesson).
            targeting=Targeting(interests=frozenset({"gaming"})),
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
            targeting=Targeting(interests=frozenset({"finance"})),  # broad geo (see Voltmatic)
            creative=NativeCreative(
                title="Meridian — banking that keeps up",
                body="Open an account in minutes.",
                cta_text="Get started",
                brand_name="Meridian",
                main_image_key="stock/finance-1.jpg",
                link_url="https://meridian.example/open",
            ),
        ),
        # --- broader demo coverage (Phase 5) --------------------------------------
        # The four lines above each teach one lesson but target narrow niches. These five widen
        # the roster so a visitor of ANY interest, in any geo, sees a relevant sponsored auction
        # in their feed — the whole point of the demo. Together they cover every world interest;
        # Kinbara is an untargeted broad-reach line, so there is always at least one eligible bid.
        _line(
            slug="verdano",
            brand="Verdano",
            objective=Objective.TRAFFIC,
            bid_usd=0.9,
            daily_budget_usd=220.0,
            value_usd=40.0,
            targeting=Targeting(interests=frozenset({"food", "home", "parenting"})),
            creative=NativeCreative(
                title="Verdano — dinner, sorted",
                body="Fresh boxes, five-ingredient recipes.",
                cta_text="Try a box",
                brand_name="Verdano",
                main_image_key="stock/food-1.jpg",
                link_url="https://verdano.example",
            ),
        ),
        _line(
            slug="wander",
            brand="Wander",
            objective=Objective.AWARENESS,
            bid_usd=7.0,
            daily_budget_usd=260.0,
            value_usd=55.0,
            targeting=Targeting(interests=frozenset({"travel", "autos", "sports"})),
            creative=NativeCreative(
                title="Wander — go further",
                body="Gear and guides for the open road.",
                cta_text="Explore",
                brand_name="Wander",
                main_image_key="stock/travel-1.jpg",
                link_url="https://wander.example",
            ),
        ),
        _line(
            slug="tempo",
            brand="Tempo",
            objective=Objective.ENGAGEMENT,
            bid_usd=0.6,
            daily_budget_usd=180.0,
            value_usd=25.0,
            targeting=Targeting(interests=frozenset({"fitness", "music", "education"})),
            creative=NativeCreative(
                title="Tempo — find your rhythm",
                body="Classes, tracks and lessons in one app.",
                cta_text="Start free",
                brand_name="Tempo",
                main_image_key="stock/music-1.jpg",
                link_url="https://tempo.example",
            ),
        ),
        _line(
            slug="marlowe",
            brand="Marlowe",
            objective=Objective.CONVERSIONS,
            bid_usd=38.0,
            daily_budget_usd=300.0,
            value_usd=90.0,
            targeting=Targeting(interests=frozenset({"fashion", "beauty", "pets"})),
            creative=NativeCreative(
                title="Marlowe — everyday, elevated",
                body="Considered pieces for you and yours.",
                cta_text="Shop the edit",
                brand_name="Marlowe",
                main_image_key="stock/fashion-1.jpg",
                link_url="https://marlowe.example",
            ),
        ),
        _line(
            slug="kinbara",
            brand="Kinbara",
            objective=Objective.AWARENESS,
            # A strong house CPM: as the only line eligible for EVERY impression, it needs to clear
            # typical niche competition so a visitor in a geo/interest no targeted line covers still
            # sees a sponsored slot (the demo's whole point). Cheap niches see it overpay a little —
            # that's the honest first-price cost of guaranteed reach, visible in the cabinet.
            bid_usd=12.0,
            daily_budget_usd=400.0,
            value_usd=50.0,
            targeting=Targeting(),  # no interest / no geo filter -> broad reach, matches everyone
            creative=NativeCreative(
                title="Kinbara — quietly everywhere",
                body="The brand behind the everyday.",
                cta_text="Discover",
                brand_name="Kinbara",
                main_image_key="stock/beauty-1.jpg",
                link_url="https://kinbara.example",
            ),
        ),
    ]


# Display metadata for the cabinet (brand + a human label), keyed by the line's ad_id.
LINE_LABELS: dict[str, dict] = {
    "seed-nimbus-ad": {"brand": "Nimbus", "name": "Nimbus X launch"},
    "seed-lumen-ad": {"brand": "Lumen", "name": "Lumen awareness"},
    "seed-voltmatic-ad": {"brand": "Voltmatic", "name": "Voltmatic traffic"},
    "seed-meridian-ad": {"brand": "Meridian", "name": "Meridian signups"},
    "seed-verdano-ad": {"brand": "Verdano", "name": "Verdano meal boxes"},
    "seed-wander-ad": {"brand": "Wander", "name": "Wander travel"},
    "seed-tempo-ad": {"brand": "Tempo", "name": "Tempo memberships"},
    "seed-marlowe-ad": {"brand": "Marlowe", "name": "Marlowe lifestyle"},
    "seed-kinbara-ad": {"brand": "Kinbara", "name": "Kinbara brand"},
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

    async def _ensure_account(account_id, name, *, is_demo):
        # Accounts outlive campaigns (deleting a campaign leaves its account), so re-seeding
        # an emptied DB must not blindly re-insert an existing account PK -> IntegrityError.
        if await session.get(AdvertiserAccount, account_id) is None:
            session.add(
                AdvertiserAccount(id=account_id, name=name, is_demo=is_demo, created_at=0.0)
            )

    await _ensure_account(DEFAULT_ACCOUNT_ID, DEFAULT_ACCOUNT_NAME, is_demo=False)
    for ln in seed_lines():
        label = LINE_LABELS.get(ln.ad_id, {})
        brand = label.get("brand", ln.creative.brand_name)
        await _ensure_account(ln.account_id, brand, is_demo=True)
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
