"""The DB line builder must reproduce the seed roster exactly (the seeded rows were built
from seed_lines()), and must only surface fully-active campaigns to the engine."""
from app.sim.line_builder import load_lines
from app.sim.seed import seed_lines


async def test_load_lines_reproduces_seed_roster(temp_session_maker):
    from app.sim.seed import ensure_seed_campaigns

    async with temp_session_maker() as s:
        await ensure_seed_campaigns(s)
        await s.commit()
        built, labels = await load_lines(s)

    seeds = {ln.ad_id: ln for ln in seed_lines()}
    assert {ln.ad_id for ln in built} == set(seeds)
    # Line is a frozen dataclass: equality compares every field (ids, objective, bid,
    # targeting, creative, pacing, budget, value). DB round-trip must be lossless.
    for ln in built:
        assert ln == seeds[ln.ad_id]
    # Labels carry the human campaign name + brand for the cabinet status.
    assert labels["seed-nimbus-ad"]["name"] == "Nimbus X launch"
    assert labels["seed-nimbus-ad"]["brand"] == "Nimbus"


async def test_load_lines_skips_paused_and_draft(temp_session_maker):
    from sqlalchemy import update

    from app.models import Campaign
    from app.sim.seed import ensure_seed_campaigns

    async with temp_session_maker() as s:
        await ensure_seed_campaigns(s)
        await s.execute(
            update(Campaign).where(Campaign.id == "seed-nimbus-cmp").values(status="paused")
        )
        await s.execute(
            update(Campaign).where(Campaign.id == "seed-lumen-cmp").values(status="draft")
        )
        await s.commit()
        built, _ = await load_lines(s)

    ids = {ln.campaign_id for ln in built}
    assert "seed-nimbus-cmp" not in ids  # paused -> out of the engine
    assert "seed-lumen-cmp" not in ids  # draft -> out of the engine
    assert "seed-voltmatic-cmp" in ids and "seed-meridian-cmp" in ids
