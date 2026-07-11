"""Shared test factory for building engine Lines without repeating boilerplate."""
from app.adsim.dsp.campaign import Line, Targeting
from app.adsim.models.creative import NativeCreative
from app.adsim.models.enums import BillingEvent, Objective, Pacing
from app.adsim.money import usd_to_micros

CREATIVE = NativeCreative(
    title="Great product",
    body="You will love it",
    cta_text="Shop now",
    brand_name="Acme",
    main_image_key="stock/acme.jpg",
    link_url="https://acme.example/lp",
)


def make_line(
    *,
    ad_id="a1",
    ad_set_id="s1",
    campaign_id="c1",
    objective=Objective.AWARENESS,
    bid_usd=5.0,
    billing=BillingEvent.CPM,
    budget_usd=1000.0,
    targeting=None,
    pacing=Pacing.EVEN,
    freq_cap=None,
    aov_usd=60.0,
) -> Line:
    return Line(
        ad_id=ad_id,
        ad_set_id=ad_set_id,
        campaign_id=campaign_id,
        account_id="acc1",
        seat="acc1",
        objective=objective,
        bid_micros=usd_to_micros(bid_usd),
        billing_event=billing,
        targeting=targeting if targeting is not None else Targeting(interests=frozenset({"tech"})),
        daily_budget_micros=usd_to_micros(budget_usd),
        baseline_conv_value_micros=usd_to_micros(aov_usd),
        creative=CREATIVE,
        freq_cap=freq_cap,
        pacing=pacing,
    )
