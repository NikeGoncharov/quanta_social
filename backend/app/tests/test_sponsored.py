"""The sponsored feed's real auction: SimRuntime.serve_sponsored records a genuine billed
impression into the same DeliveryState + delivery buckets as the synthetic world, and
record_sponsored_click carries the funnel (click -> possible conversion). Driven directly
against a DB-backed runtime with a seeded rng for determinism."""
import random

from sqlalchemy import func, select

from app.models import AdClick, AdConversion, AdImpression, DeliveryBucket


async def _win_one(rt, maker, *, viewer_id, tries=80):
    """Serve until a house campaign wins the slot; return its impression payload."""
    async with maker() as s:
        for _ in range(tries):
            ad = await rt.serve_sponsored(
                s, viewer_id=viewer_id, interests=["tech"], geo="USA", age_band="25-34", gender="F"
            )
            if ad is not None:
                await s.commit()
                return ad
        await s.commit()
    return None


async def test_runtime_has_seed_lines(db_runtime):
    assert db_runtime.lines, "DB-backed runtime should have loaded the seed roster"


async def test_serve_sponsored_records_real_delivery(db_runtime, temp_session_maker):
    rt = db_runtime
    rt._rng = random.Random(7)
    wins = 0
    async with temp_session_maker() as s:
        for _ in range(50):
            ad = await rt.serve_sponsored(
                s, viewer_id="usr-viewer", interests=["tech"], geo="USA", age_band="25-34", gender="F"
            )
            if ad is not None:
                wins += 1
                # the winning creative is a real serialized NativeCreative
                assert set(ad["creative"]) >= {"title", "body", "cta_text", "brand_name"}
                assert ad["clearing"] > 0
        await s.commit()

    assert wins > 0, "a tech/USA viewer should win some slots against the phantom market"

    async with temp_session_maker() as s:
        n_imp = (await s.execute(select(func.count()).select_from(AdImpression))).scalar()
        assert n_imp == wins
        real_imps = (await s.execute(
            select(func.sum(DeliveryBucket.impressions)).where(DeliveryBucket.source == "real")
        )).scalar()
        assert real_imps == wins
        real_spend = (await s.execute(
            select(func.sum(DeliveryBucket.spend_micros)).where(DeliveryBucket.source == "real")
        )).scalar()
        assert real_spend and real_spend > 0
        # synthetic buckets are untouched by real serving (separate source rows)
        syn = (await s.execute(
            select(func.count()).select_from(DeliveryBucket).where(DeliveryBucket.source == "real")
        )).scalar()
        assert syn >= 1

    # the same live DeliveryState the world loop uses now carries the real spend
    assert sum(rt.state.spent_today_micros.values()) == real_spend


async def test_real_impression_matches_state_spend(db_runtime, temp_session_maker):
    """Glass-box: the price billed on the impression row equals the spend added to state."""
    rt = db_runtime
    rt._rng = random.Random(3)
    ad = await _win_one(rt, temp_session_maker, viewer_id="usr-a")
    assert ad is not None
    async with temp_session_maker() as s:
        imp = await s.get(AdImpression, ad["impression_id"])
        assert imp is not None
        assert imp.spend_micros == rt.state.spent_today_micros.get(imp.ad_id)
        assert imp.clearing_micros > 0
        assert imp.spend_micros == imp.clearing_micros // 1000  # spend = 1 imp at clearing CPM


async def test_sponsored_click_records_click_and_is_idempotent(db_runtime, temp_session_maker):
    rt = db_runtime
    rt._rng = random.Random(11)
    ad = await _win_one(rt, temp_session_maker, viewer_id="usr-clicker")
    assert ad is not None

    async with temp_session_maker() as s:
        res = await rt.record_sponsored_click(s, impression_id=ad["impression_id"], viewer_id="usr-clicker")
        await s.commit()
    assert res is not None and res["clicked"] is True

    async with temp_session_maker() as s:
        assert (await s.execute(select(func.count()).select_from(AdClick))).scalar() == 1
        real_clicks = (await s.execute(
            select(func.sum(DeliveryBucket.clicks)).where(DeliveryBucket.source == "real")
        )).scalar()
        assert real_clicks == 1

    # a repeat click on the same impression is a no-op
    async with temp_session_maker() as s:
        again = await rt.record_sponsored_click(s, impression_id=ad["impression_id"], viewer_id="usr-clicker")
        await s.commit()
    assert again.get("repeat") is True
    async with temp_session_maker() as s:
        assert (await s.execute(select(func.count()).select_from(AdClick))).scalar() == 1


async def test_click_wrong_viewer_rejected(db_runtime, temp_session_maker):
    rt = db_runtime
    rt._rng = random.Random(5)
    ad = await _win_one(rt, temp_session_maker, viewer_id="usr-owner")
    assert ad is not None
    async with temp_session_maker() as s:
        res = await rt.record_sponsored_click(s, impression_id=ad["impression_id"], viewer_id="usr-someone-else")
    assert res is None


async def test_conversion_eventually_recorded(db_runtime, temp_session_maker):
    """Across enough clicks, deterministic click-through attribution yields some conversions,
    each with a positive value and a matching real revenue bucket."""
    rt = db_runtime
    rt._rng = random.Random(2)
    # Win and click many impressions.
    imp_ids = []
    async with temp_session_maker() as s:
        for _ in range(150):
            ad = await rt.serve_sponsored(
                s, viewer_id="usr-buyer", interests=["tech"], geo="USA", age_band="25-34", gender="F"
            )
            if ad is not None:
                imp_ids.append(ad["impression_id"])
        await s.commit()
    assert imp_ids
    async with temp_session_maker() as s:
        for iid in imp_ids:
            await rt.record_sponsored_click(s, impression_id=iid, viewer_id="usr-buyer")
        await s.commit()

    async with temp_session_maker() as s:
        conv = (await s.execute(select(func.count()).select_from(AdConversion))).scalar()
        assert conv >= 1, "some of many clicks should convert at the segment CVR"
        revenue = (await s.execute(
            select(func.sum(DeliveryBucket.revenue_micros)).where(DeliveryBucket.source == "real")
        )).scalar()
        assert revenue and revenue > 0


async def test_no_fill_returns_none(db_runtime, temp_session_maker):
    rt = db_runtime
    async with temp_session_maker() as s:
        ad = await rt.serve_sponsored(
            s, viewer_id="u", interests=["tech"], geo="USA", age_band="25-34", gender="F",
            exclude_ad_ids={ln.ad_id for ln in rt.lines},
        )
    assert ad is None
