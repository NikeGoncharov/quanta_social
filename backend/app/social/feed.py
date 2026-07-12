"""The home feed — organic posts from the people you follow (plus discovery), with a real,
billed sponsored post injected roughly every sixth slot.

The sponsored slot is the heart of Phase 4: each one runs a genuine single-opportunity
auction (SimRuntime.serve_sponsored) among all eligible live campaigns and phantom
competitors. A win records a real impression into the same delivery state and buckets the
synthetic world uses — so what a friend actually sees is billed exactly like the simulation.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.models import Follow, Post, Profile, User

from . import service

router = APIRouter()

SPONSOR_EVERY = 6  # one sponsored slot per ~6 feed items


def _runtime(request: Request):
    return getattr(request.app.state, "runtime", None)


@router.get("/feed")
async def home_feed(
    request: Request, limit: int = 24,
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    limit = max(1, min(limit, 50))
    profile = await db.get(Profile, current.id)
    interests = service.parse_interests(profile)

    followees = (await db.execute(
        select(Follow.followee_id).where(Follow.follower_id == current.id)
    )).scalars().all()
    author_ids = set(followees) | {current.id}

    followed = (await db.execute(
        select(Post).where(Post.author_id.in_(author_ids)).order_by(Post.created_at.desc()).limit(limit)
    )).scalars().all()

    posts = list(followed)
    # Backfill from discovery (synthetic accounts) so a fresh account still sees a full feed.
    if len(posts) < limit:
        have = {p.id for p in posts}
        syn = select(User.id).where(User.is_synthetic.is_(True))
        discover = (await db.execute(
            select(Post).where(Post.author_id.in_(syn), Post.author_id != current.id)
            .order_by(Post.created_at.desc()).limit(limit * 2)
        )).scalars().all()
        for p in discover:
            if p.id not in have:
                posts.append(p)
                have.add(p.id)
            if len(posts) >= limit:
                break
    posts.sort(key=lambda p: p.created_at, reverse=True)
    posts = posts[:limit]

    hydrated = await service.hydrate_posts(db, current.id, posts)

    rt = _runtime(request)
    items: list[dict] = []
    shown_ads: set[str] = set()
    since_ad = 0
    for p in hydrated:
        items.append({"kind": "post", "post": p})
        since_ad += 1
        if rt is not None and since_ad >= SPONSOR_EVERY - 1:
            since_ad = 0
            ad = await rt.serve_sponsored(
                db, viewer_id=current.id, interests=interests,
                geo=(profile.geo if profile else ""), age_band=(profile.age_band if profile else ""),
                gender=(profile.gender if profile else ""), exclude_ad_ids=shown_ads,
            )
            if ad is not None:
                shown_ads.add(ad["ad_id"])
                items.append({"kind": "ad", **ad})
    # serve_sponsored commits each recorded impression itself (under the runtime's real-serve
    # lock), so there is nothing left to commit here.
    return {"items": items}


@router.post("/sponsored/{impression_id}/click")
async def sponsored_click(
    impression_id: str, request: Request,
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Record a real click on a sponsored post (and a possible click-through conversion)."""
    rt = _runtime(request)
    if rt is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Ad engine offline")
    result = await rt.record_sponsored_click(db, impression_id=impression_id, viewer_id=current.id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Impression not found")
    return result  # record_sponsored_click commits under the runtime's real-serve lock
