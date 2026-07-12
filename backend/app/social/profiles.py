"""Profiles + the follow graph."""
import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.models import Follow, Post, Profile, User

from . import service
from .schemas import ProfilePatch

router = APIRouter()


async def _counts(db: AsyncSession, user_id: str) -> tuple[int, int, int]:
    followers = (await db.execute(
        select(func.count()).select_from(Follow).where(Follow.followee_id == user_id)
    )).scalar() or 0
    following = (await db.execute(
        select(func.count()).select_from(Follow).where(Follow.follower_id == user_id)
    )).scalar() or 0
    posts = (await db.execute(
        select(func.count()).select_from(Post).where(Post.author_id == user_id)
    )).scalar() or 0
    return int(followers), int(following), int(posts)


@router.get("/users/{handle}")
async def get_profile(handle: str, current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user = await service.user_by_handle(db, handle)
    profile = await db.get(Profile, user.id)
    followers, following, posts = await _counts(db, user.id)
    is_following = (await db.execute(
        select(Follow).where(Follow.follower_id == current.id, Follow.followee_id == user.id)
    )).first() is not None
    return service.profile_public(
        user, profile, followers=followers, following=following, posts=posts,
        is_following=is_following, is_me=(user.id == current.id),
    )


@router.get("/users/{handle}/posts")
async def user_posts(
    handle: str, limit: int = 30, current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = await service.user_by_handle(db, handle)
    rows = (await db.execute(
        select(Post).where(Post.author_id == user.id).order_by(Post.created_at.desc()).limit(min(limit, 100))
    )).scalars().all()
    return {"posts": await service.hydrate_posts(db, current.id, list(rows))}


@router.patch("/profile")
async def update_profile(
    body: ProfilePatch, current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    profile = await db.get(Profile, current.id)
    if profile is None:
        profile = Profile(user_id=current.id, avatar_seed=current.id)
        db.add(profile)
    if body.display_name is not None:
        profile.display_name = body.display_name.strip()[:60]
    if body.bio is not None:
        profile.bio = body.bio.strip()[:280]
    if body.interests is not None:
        profile.interests_json = json.dumps([str(i) for i in body.interests][:12])
    if body.geo is not None:
        profile.geo = body.geo.strip()
    if body.age_band is not None:
        profile.age_band = body.age_band.strip()
    if body.gender is not None:
        profile.gender = body.gender.strip()
    if body.avatar_seed is not None and body.avatar_seed.strip():
        profile.avatar_seed = body.avatar_seed.strip()[:60]
    await db.commit()
    followers, following, posts = await _counts(db, current.id)
    return service.profile_public(
        current, profile, followers=followers, following=following, posts=posts,
        is_following=False, is_me=True,
    )


@router.post("/users/{handle}/follow", status_code=status.HTTP_201_CREATED)
async def follow(handle: str, current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user = await service.user_by_handle(db, handle)
    if user.id == current.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot follow yourself")
    existing = (await db.execute(
        select(Follow).where(Follow.follower_id == current.id, Follow.followee_id == user.id)
    )).first()
    if existing is None:
        db.add(Follow(follower_id=current.id, followee_id=user.id, created_at=service.now()))
        await db.commit()
    return {"following": True}


@router.delete("/users/{handle}/follow")
async def unfollow(handle: str, current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user = await service.user_by_handle(db, handle)
    await db.execute(
        delete(Follow).where(Follow.follower_id == current.id, Follow.followee_id == user.id)
    )
    await db.commit()
    return {"following": False}


@router.get("/suggestions")
async def suggestions(limit: int = 6, current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """People to follow: users the viewer doesn't already follow (and isn't), newest first —
    a lightweight discovery rail for the sidebar."""
    followed = (await db.execute(
        select(Follow.followee_id).where(Follow.follower_id == current.id)
    )).scalars().all()
    exclude = set(followed) | {current.id}
    rows = (await db.execute(
        select(User).where(User.handle.isnot(None)).order_by(User.created_at.desc()).limit(200)
    )).scalars().all()
    picks = [u for u in rows if u.id not in exclude][:min(limit, 20)]
    profiles = {
        p.user_id: p for p in (await db.execute(
            select(Profile).where(Profile.user_id.in_([u.id for u in picks] or [""]))
        )).scalars().all()
    }
    return {"users": [service.user_brief(u, profiles.get(u.id)) for u in picks]}
