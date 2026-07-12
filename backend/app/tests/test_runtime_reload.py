"""The world loop must pick up cabinet edits by rebuilding its line roster from the DB —
WITHOUT resetting the running spend / learning state (which is keyed by the stable ids)."""
from sqlalchemy import update

from app.models import AdSet, Campaign


async def test_reload_preserves_running_state(db_runtime):
    rt = db_runtime
    for _ in range(30):
        rt.step_once()
    before = {ln.ad_id: rt.state.spent_today_micros.get(ln.ad_id, 0) for ln in rt.lines}
    assert any(v > 0 for v in before.values())
    learn_before = dict(rt.state.learning_signal)

    # A cabinet edit: bump Nimbus's daily budget, then reload the roster.
    async with rt.session_maker() as s:
        await s.execute(
            update(Campaign).where(Campaign.id == "seed-nimbus-cmp").values(daily_budget_micros=999_000_000)
        )
        await s.commit()
    await rt.reload_lines()

    nimbus = next(ln for ln in rt.lines if ln.ad_id == "seed-nimbus-ad")
    assert nimbus.daily_budget_micros == 999_000_000  # edit took effect
    # ...but spend and learning carried over untouched (no re-spend, no learning reset).
    for ad_id, spent in before.items():
        assert rt.state.spent_today_micros.get(ad_id, 0) == spent
    assert rt.state.learning_signal == learn_before


async def test_reload_drops_paused_and_adds_new(db_runtime):
    rt = db_runtime
    for _ in range(10):
        rt.step_once()
    voltmatic_spent = rt.state.spent_today_micros.get("seed-voltmatic-ad", 0)

    # Pause Voltmatic + add a brand-new campaign, then reload.
    from app.cabinet.schemas import CampaignCreate, CreativeIn, TargetingIn
    from app.cabinet.service import create_campaign

    async with rt.session_maker() as s:
        await s.execute(
            update(Campaign).where(Campaign.id == "seed-voltmatic-cmp").values(status="paused")
        )
        await s.execute(update(AdSet).where(AdSet.campaign_id == "seed-voltmatic-cmp").values(status="paused"))
        body = CampaignCreate(
            name="Newco launch", objective="awareness", daily_budget_usd=250, bid_usd=7,
            targeting=TargetingIn(interests=["tech"]),
            creative=CreativeIn(title="Newco", brand_name="Newco", link_url="https://newco.example"),
        )
        new_cmp = await create_campaign(s, body, now=1.0)
        await s.commit()
    await rt.reload_lines()

    ids = {ln.campaign_id for ln in rt.lines}
    assert "seed-voltmatic-cmp" not in ids  # paused dropped out
    assert new_cmp.id in ids  # new campaign joined the live roster
    # Voltmatic's spend is still in state (it just isn't being delivered now).
    assert rt.state.spent_today_micros.get("seed-voltmatic-ad", 0) == voltmatic_spent
