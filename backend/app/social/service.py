"""Shared social helpers: serialization + batched count queries (no per-row N+1).

Timestamps are wall epoch seconds. Avatars have no uploads in v1 — the frontend renders a
deterministic gradient from `avatar_seed`, mirroring how creatives render from an image key.
"""
import json
import time

from fastapi import HTTPException, status
from sqlalchemy import func, select

from app.models import Comment, Follow, Like, Post, Profile, User


def now() -> float:
    return time.time()


async def user_by_handle(db, handle: str) -> User:
    """Resolve a @handle to a User or raise 404. Shared by the profile and message routers."""
    user = (await db.execute(select(User).where(User.handle == handle))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def unknown_author(author_id: str) -> dict:
    """Fallback author card for a row whose author no longer exists — one shape, so it can't
    drift from user_brief's keys."""
    return {
        "id": author_id, "handle": "unknown", "display_name": "Unknown",
        "avatar_seed": author_id, "is_synthetic": False,
    }


def parse_interests(profile: Profile | None) -> list[str]:
    if profile is None:
        return []
    try:
        val = json.loads(profile.interests_json or "[]")
        return [str(x) for x in val] if isinstance(val, list) else []
    except (ValueError, TypeError):
        return []


def user_brief(user: User, profile: Profile | None) -> dict:
    """The compact author/peer card used in posts, comments, lists."""
    display = (profile.display_name if profile else "") or user.handle
    seed = (profile.avatar_seed if profile else "") or user.id
    return {
        "id": user.id,
        "handle": user.handle,
        "display_name": display,
        "avatar_seed": seed,
        "is_synthetic": user.is_synthetic,
    }


def profile_public(
    user: User, profile: Profile | None, *,
    followers: int, following: int, posts: int, is_following: bool, is_me: bool,
) -> dict:
    # geo / age_band / gender are the private ad-targeting signals — surfaced only to the owner
    # (they're blanked, not omitted, so the response shape stays stable for the client).
    return {
        **user_brief(user, profile),
        "bio": profile.bio if profile else "",
        "interests": parse_interests(profile),
        "geo": (profile.geo if profile else "") if is_me else "",
        "age_band": (profile.age_band if profile else "") if is_me else "",
        "gender": (profile.gender if profile else "") if is_me else "",
        "followers": followers,
        "following": following,
        "posts": posts,
        "is_following": is_following,
        "is_me": is_me,
    }


def post_public(
    post: Post, author: dict, *, like_count: int, comment_count: int, liked: bool,
) -> dict:
    return {
        "id": post.id,
        "author": author,
        "body": post.body,
        "image_key": post.image_key,
        "created_at": post.created_at,
        "like_count": like_count,
        "comment_count": comment_count,
        "liked": liked,
    }


async def load_authors(db, author_ids: set[str]) -> dict[str, dict]:
    """Batch-load the user + profile for a set of author ids -> {id: user_brief}."""
    if not author_ids:
        return {}
    users = (await db.execute(select(User).where(User.id.in_(author_ids)))).scalars().all()
    profiles = (await db.execute(select(Profile).where(Profile.user_id.in_(author_ids)))).scalars().all()
    pmap = {p.user_id: p for p in profiles}
    return {u.id: user_brief(u, pmap.get(u.id)) for u in users}


async def like_counts(db, post_ids: list[str]) -> dict[str, int]:
    if not post_ids:
        return {}
    rows = (await db.execute(
        select(Like.post_id, func.count()).where(Like.post_id.in_(post_ids)).group_by(Like.post_id)
    )).all()
    return {pid: int(n) for pid, n in rows}


async def comment_counts(db, post_ids: list[str]) -> dict[str, int]:
    if not post_ids:
        return {}
    rows = (await db.execute(
        select(Comment.post_id, func.count()).where(Comment.post_id.in_(post_ids)).group_by(Comment.post_id)
    )).all()
    return {pid: int(n) for pid, n in rows}


async def liked_by(db, user_id: str, post_ids: list[str]) -> set[str]:
    if not post_ids:
        return set()
    rows = (await db.execute(
        select(Like.post_id).where(Like.user_id == user_id, Like.post_id.in_(post_ids))
    )).scalars().all()
    return set(rows)


async def hydrate_posts(db, viewer_id: str, posts: list[Post]) -> list[dict]:
    """Turn a list of Post rows into public dicts, batch-loading authors, counts and my likes."""
    if not posts:
        return []
    ids = [p.id for p in posts]
    authors = await load_authors(db, {p.author_id for p in posts})
    lc = await like_counts(db, ids)
    cc = await comment_counts(db, ids)
    mine = await liked_by(db, viewer_id, ids)
    out = []
    for p in posts:
        author = authors.get(p.author_id) or unknown_author(p.author_id)
        out.append(post_public(
            p, author, like_count=lc.get(p.id, 0), comment_count=cc.get(p.id, 0), liked=p.id in mine,
        ))
    return out
