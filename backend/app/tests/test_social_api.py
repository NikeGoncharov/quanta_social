"""Social API: auth (register/login/me), profiles + follow graph, posts/likes/comments,
messages, and the feed shape. Builds on cabinet_client (runtime + request DB share one temp
database) and additionally seeds the synthetic network + registers a real 'me' user whose
auth cookie the AsyncClient carries across requests."""
import pytest_asyncio


@pytest_asyncio.fixture
async def social_client(cabinet_client, temp_session_maker):
    ac, rt = cabinet_client
    from app.social.seed import ensure_seed_social

    async with temp_session_maker() as s:
        await ensure_seed_social(s)
        await s.commit()
    r = await ac.post("/auth/register", json={"email": "me@quanta-social.com", "password": "password123", "handle": "me"})
    assert r.status_code == 201, r.text
    return ac, rt


async def test_register_sets_cookie_and_me(social_client):
    ac, _ = social_client
    r = await ac.get("/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert body["handle"] == "me"
    assert body["email"] == "me@quanta-social.com"


async def test_feed_requires_auth(cabinet_client):
    ac, _ = cabinet_client  # no registration -> no auth cookie
    r = await ac.get("/social/feed")
    assert r.status_code == 401


async def test_login_roundtrip(social_client):
    ac, _ = social_client
    # register a second user, log out, log back in
    await ac.post("/auth/register", json={"email": "second@quanta-social.com", "password": "password123"})
    await ac.post("/auth/logout")
    r = await ac.post("/auth/login", json={"email": "second@quanta-social.com", "password": "password123"})
    assert r.status_code == 200
    me = await ac.get("/auth/me")
    assert me.json()["email"] == "second@quanta-social.com"


async def test_bad_login_rejected(social_client):
    ac, _ = social_client
    await ac.post("/auth/logout")
    r = await ac.post("/auth/login", json={"email": "me@quanta-social.com", "password": "wrongpass1"})
    assert r.status_code == 401


async def test_duplicate_email_rejected(social_client):
    ac, _ = social_client
    r = await ac.post("/auth/register", json={"email": "me@quanta-social.com", "password": "password123"})
    assert r.status_code == 400


async def test_short_password_rejected(cabinet_client):
    ac, _ = cabinet_client
    r = await ac.post("/auth/register", json={"email": "x@quanta-social.com", "password": "short"})
    assert r.status_code == 422


async def test_profile_follow_and_suggestions(social_client):
    ac, _ = social_client
    r = await ac.get("/social/users/maya_codes")
    assert r.status_code == 200
    assert r.json()["is_following"] is False

    r = await ac.post("/social/users/maya_codes/follow")
    assert r.status_code == 201
    r = await ac.get("/social/users/maya_codes")
    assert r.json()["is_following"] is True
    assert r.json()["followers"] >= 1

    r = await ac.get("/social/suggestions")
    assert "maya_codes" not in [u["handle"] for u in r.json()["users"]]

    r = await ac.delete("/social/users/maya_codes/follow")
    assert r.status_code == 200
    r = await ac.get("/social/users/maya_codes")
    assert r.json()["is_following"] is False


async def test_cannot_follow_self(social_client):
    ac, _ = social_client
    r = await ac.post("/social/users/me/follow")
    assert r.status_code == 400


async def test_profile_hides_demographics_from_others(social_client):
    """geo / age_band / gender are private ad-targeting signals: visible on your own profile,
    blanked on everyone else's (interests stay intentionally public)."""
    ac, _ = social_client
    await ac.patch("/social/profile", json={"geo": "USA", "age_band": "25-34", "gender": "F"})

    mine = (await ac.get("/social/users/me")).json()
    assert (mine["geo"], mine["age_band"], mine["gender"]) == ("USA", "25-34", "F")

    other = (await ac.get("/social/users/maya_codes")).json()
    assert other["geo"] == "" and other["age_band"] == "" and other["gender"] == ""
    assert other["display_name"] and other["interests"]  # public fields still present


async def test_post_like_comment(social_client):
    ac, _ = social_client
    r = await ac.post("/social/posts", json={"body": "hello quanta"})
    assert r.status_code == 201
    pid = r.json()["id"]
    assert r.json()["author"]["handle"] == "me"

    r = await ac.post(f"/social/posts/{pid}/like")
    assert r.json()["like_count"] == 1
    # idempotent like
    r = await ac.post(f"/social/posts/{pid}/like")
    assert r.json()["like_count"] == 1

    r = await ac.post(f"/social/posts/{pid}/comments", json={"body": "nice one"})
    assert r.status_code == 201

    r = await ac.get(f"/social/posts/{pid}")
    assert r.json()["like_count"] == 1
    assert r.json()["liked"] is True
    assert len(r.json()["comments"]) == 1

    r = await ac.delete(f"/social/posts/{pid}/like")
    assert r.json()["like_count"] == 0


async def test_delete_own_post_only(social_client):
    ac, _ = social_client
    r = await ac.post("/social/posts", json={"body": "to be deleted"})
    pid = r.json()["id"]
    r = await ac.delete(f"/social/posts/{pid}")
    assert r.status_code == 200
    r = await ac.get(f"/social/posts/{pid}")
    assert r.status_code == 404


async def test_feed_returns_items(social_client):
    ac, _ = social_client
    r = await ac.get("/social/feed?limit=24")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) > 0
    assert "post" in {it["kind"] for it in items}
    for it in items:
        if it["kind"] == "post":
            assert "author" in it["post"] and "body" in it["post"]
        else:
            assert it["kind"] == "ad"
            assert "impression_id" in it and "creative" in it


async def test_messages_flow(social_client):
    ac, _ = social_client
    r = await ac.post("/social/messages/leo_plays", json={"body": "hey leo"})
    assert r.status_code == 201

    r = await ac.get("/social/messages/leo_plays")
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert len(msgs) == 1 and msgs[0]["from_me"] is True

    r = await ac.get("/social/messages")
    assert any(c["peer"]["handle"] == "leo_plays" for c in r.json()["conversations"])
