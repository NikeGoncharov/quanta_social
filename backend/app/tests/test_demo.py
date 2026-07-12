"""Phase 5 — the scaled synthetic seed, the image-gallery contract, and guest demo mode.

Seed/reaper tests drive the service functions against a temp DB directly (deterministic, no
HTTP); the guest-endpoint tests build on `cabinet_client` (runtime + request DB share one temp
database) plus the seeded social network, exactly like the social API tests.
"""
import time

import pytest_asyncio
from sqlalchemy import func, select

from app.models import Comment, Like, Post, User


async def _count(session, model, *where) -> int:
    q = select(func.count()).select_from(model)
    for w in where:
        q = q.where(w)
    return int((await session.execute(q)).scalar() or 0)


async def _seed(temp_session_maker) -> None:
    from app.social.seed import ensure_seed_social

    async with temp_session_maker() as s:
        await ensure_seed_social(s)
        await s.commit()


# --- scaled seed -------------------------------------------------------------
async def test_seed_scales_to_a_full_network(temp_session_maker):
    await _seed(temp_session_maker)
    async with temp_session_maker() as s:
        synthetics = await _count(s, User, User.is_synthetic.is_(True))
        posts = await _count(s, Post)
        assert synthetics >= 50, "the seed should stand up a full network, not a handful"
        assert posts >= 200, "hundreds of posts so the feed reads as alive"
        handles = set((await s.execute(select(User.handle))).scalars().all())
        # The curated highlights keep stable handles (tests + the demo narrative name them).
        assert {"maya_codes", "leo_plays", "nora_funds"} <= handles


async def test_seed_is_idempotent(temp_session_maker):
    await _seed(temp_session_maker)
    async with temp_session_maker() as s:
        before = await _count(s, User)
    await _seed(temp_session_maker)  # second call is a no-op (synthetics already exist)
    async with temp_session_maker() as s:
        assert await _count(s, User) == before


async def test_seed_posts_carry_images_across_categories(temp_session_maker):
    await _seed(temp_session_maker)
    async with temp_session_maker() as s:
        keys = (await s.execute(select(Post.image_key).where(Post.image_key.isnot(None)))).scalars().all()
    assert len(keys) >= 20, "a meaningful slice of posts should carry a stock image"
    assert all(k.startswith("stock/") for k in keys)
    categories = {k.split("/")[1].split("-")[0] for k in keys}
    assert len(categories) >= 5, "images should span multiple interest categories"


async def test_seed_has_social_proof(temp_session_maker):
    await _seed(temp_session_maker)
    async with temp_session_maker() as s:
        assert await _count(s, Like) > 0
        assert await _count(s, Comment) > 0


# --- guest demo mode ---------------------------------------------------------
@pytest_asyncio.fixture
async def demo_client(cabinet_client, temp_session_maker):
    """cabinet_client (runtime + shared request DB) with the synthetic network seeded — the
    setup a guest actually lands in."""
    ac, rt = cabinet_client
    from app.social.seed import ensure_seed_social

    async with temp_session_maker() as s:
        await ensure_seed_social(s)
        await s.commit()
    return ac, rt


async def test_guest_starts_a_real_session(demo_client):
    ac, _ = demo_client
    r = await ac.post("/demo/guest")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["is_guest"] is True
    assert body["handle"].startswith("guest")
    # The cookie now authenticates — /auth/me resolves the same guest.
    me = await ac.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["is_guest"] is True


async def test_guest_has_full_access(demo_client):
    ac, _ = demo_client
    await ac.post("/demo/guest")

    feed = await ac.get("/social/feed?limit=24")
    assert feed.status_code == 200
    assert len(feed.json()["items"]) > 0  # a full feed from the synthetic network

    posted = await ac.post("/social/posts", json={"body": "hello from a guest"})
    assert posted.status_code == 201

    grid = await ac.get("/cabinet/grid")  # the live glass-box cabinet is reachable
    assert grid.status_code == 200


# --- the reaper (strictly guest-scoped) --------------------------------------
async def _make_real_and_guest(temp_session_maker):
    """Seed the network, add one real user, and mint a guest that has authored a post and liked
    a synthetic post. Returns the guest id."""
    from app.auth import get_password_hash
    from app.demo import create_guest

    await _seed(temp_session_maker)
    async with temp_session_maker() as s:
        s.add(User(
            id="usr-real", email="real@quanta-social.com", handle="real_person",
            password_hash=get_password_hash("password123"),
            is_synthetic=False, is_guest=False, created_at=time.time(),
        ))
        await s.commit()
        guest, _ = await create_guest(s)
        gid = guest.id
        a_synth_post = (await s.execute(select(Post.id))).scalars().first()
        s.add(Post(id="post-guest-x", author_id=gid, body="a guest thought", created_at=time.time()))
        s.add(Like(user_id=gid, post_id=a_synth_post, created_at=time.time()))
        await s.commit()
    return gid


async def test_reap_removes_expired_guests_and_their_data(temp_session_maker):
    from app.demo import reap_expired_guests

    gid = await _make_real_and_guest(temp_session_maker)
    async with temp_session_maker() as s:
        synth_before = await _count(s, User, User.is_synthetic.is_(True))

    # now in the future so the just-made guest is definitively past the TTL.
    async with temp_session_maker() as s:
        res = await reap_expired_guests(s, older_than_seconds=0, now=time.time() + 60)
    assert res["guests"] == 1
    assert res["posts"] == 1

    async with temp_session_maker() as s:
        assert await _count(s, User, User.is_guest.is_(True)) == 0
        assert await _count(s, User, User.is_synthetic.is_(True)) == synth_before  # seed untouched
        assert (await s.execute(select(User).where(User.id == "usr-real"))).scalar_one_or_none() is not None
        assert (await s.execute(select(Post).where(Post.id == "post-guest-x"))).scalar_one_or_none() is None
        # the guest's like is gone, but the synthetic post it targeted survives
        assert await _count(s, Like, Like.user_id == gid) == 0


async def test_reap_respects_ttl_for_fresh_guests(temp_session_maker):
    from app.demo import create_guest, reap_expired_guests

    await _seed(temp_session_maker)
    async with temp_session_maker() as s:
        await create_guest(s)
    # A guest younger than the TTL is left alone.
    async with temp_session_maker() as s:
        res = await reap_expired_guests(s, older_than_seconds=3600)
    assert res["guests"] == 0
    async with temp_session_maker() as s:
        assert await _count(s, User, User.is_guest.is_(True)) == 1


async def test_reset_all_guests_clears_the_sandbox(temp_session_maker):
    from app.demo import create_guest, reset_all_guests

    await _seed(temp_session_maker)
    async with temp_session_maker() as s:
        await create_guest(s)
    async with temp_session_maker() as s:
        await create_guest(s)
    async with temp_session_maker() as s:
        assert await _count(s, User, User.is_guest.is_(True)) == 2

    async with temp_session_maker() as s:
        res = await reset_all_guests(s)
    assert res["guests"] == 2
    async with temp_session_maker() as s:
        assert await _count(s, User, User.is_guest.is_(True)) == 0
        assert await _count(s, User, User.is_synthetic.is_(True)) >= 50  # real network intact
