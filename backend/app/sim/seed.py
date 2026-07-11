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
from ..adsim.dsp.campaign import Line, Targeting
from ..adsim.models.creative import NativeCreative
from ..adsim.models.enums import OBJECTIVE_BILLING, Objective, Pacing
from ..adsim.money import usd_to_micros


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
