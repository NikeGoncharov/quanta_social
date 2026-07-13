"""Guest demo mode (Phase 5).

A one-click throwaway identity so the public case study can be explored with full access — the
social network *and* the live glass-box cabinet — without an invite. A guest is an ordinary
authenticated user with `is_guest=True`, no email and no password (they can't log back in; the
cookie is the whole session).

Guests are disposable. A background reaper (started in the app lifespan) deletes each guest and
everything they authored once it is older than the TTL, so the shared demo never accumulates
junk. The purge is scoped *strictly* to `is_guest=True` users and their attributable rows — it
can never touch a real account or the synthetic seed.
"""
import json
import logging
import random
import time
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    create_access_token,
    create_refresh_token,
    public_me,
    set_auth_cookies,
    _unique_handle,
)
from app.config import (
    GUEST_DEMO_ENABLED,
    GUEST_MAX_CONCURRENT,
    GUEST_RATE_LIMIT,
    GUEST_RATE_WINDOW_SECONDS,
    GUEST_TTL_SECONDS,
)
from app.database import get_db
from app.ratelimit import SlidingWindowLimiter, client_ip
from app.models import (
    Ad,
    AdClick,
    AdConversion,
    AdImpression,
    AdSet,
    AdvertiserAccount,
    BudgetState,
    Campaign,
    Comment,
    DeliveryBucket,
    Follow,
    LearningState,
    Like,
    Message,
    Post,
    Profile,
    User,
)
from app.social.seed import AGE_BANDS, GENDERS, GEOS, INTERESTS

log = logging.getLogger("quanta.demo")

router = APIRouter(prefix="/demo", tags=["demo"])

# Per-IP rate limiter for guest minting. Module-level: one instance per worker, which is
# authoritative under the single-worker deployment the world loop requires.
guest_rate_limiter = SlidingWindowLimiter(limit=GUEST_RATE_LIMIT, window=GUEST_RATE_WINDOW_SECONDS)


async def _live_guest_count(db: AsyncSession) -> int:
    return (
        await db.execute(select(func.count()).select_from(User).where(User.is_guest.is_(True)))
    ).scalar() or 0


# --- guest creation ----------------------------------------------------------
async def create_guest(db: AsyncSession) -> tuple[User, Profile]:
    """Create a fresh guest user + profile. The profile carries real interest/geo/demo signals
    (each guest is randomly placed) so their feed runs genuine, relevant sponsored auctions."""
    rng = random.Random()  # intentionally non-deterministic: every guest is a distinct sample
    # Seed the handle base with randomness so the very first candidate is already unique — two
    # simultaneous first-guests can't both resolve the bare "guest" and collide on the UNIQUE
    # handle (a check-then-insert race that would 500 one of them).
    handle = await _unique_handle(db, "guest" + uuid4().hex[:6])
    uid = "usr-guest-" + uuid4().hex[:8]
    user = User(
        id=uid, email=None, handle=handle, password_hash=None,
        is_synthetic=False, is_guest=True, created_at=time.time(),
    )
    profile = Profile(
        user_id=uid, display_name="Guest explorer", avatar_seed=uid,
        bio="Exploring Quanta in demo mode.",
        interests_json=json.dumps(rng.sample(INTERESTS, 2)),
        geo=rng.choice(GEOS), age_band=rng.choice(AGE_BANDS), gender=rng.choice(GENDERS),
    )
    db.add(user)
    db.add(profile)
    await db.commit()
    return user, profile


@router.post("/guest", status_code=status.HTTP_201_CREATED)
async def start_guest(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Mint a guest session and set its auth cookies. Full access, sandboxed, auto-expiring."""
    if not GUEST_DEMO_ENABLED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Guest demo mode is disabled")
    # Abuse guards for this public, unauthenticated endpoint: a per-IP rate limit, then a global
    # ceiling on live guests so even a distributed spray can't bloat the shared-host disk.
    if not guest_rate_limiter.allow(client_ip(request)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many demo sessions from your network. Please wait a minute and try again.",
        )
    if await _live_guest_count(db) >= GUEST_MAX_CONCURRENT:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The live demo is at capacity right now. Please try again shortly.",
        )
    user, profile = await create_guest(db)
    set_auth_cookies(response, create_access_token(user.id), create_refresh_token(user.id))
    return public_me(user, profile)


# --- the reaper (strictly guest-scoped) --------------------------------------
async def _expired_guest_ids(db: AsyncSession, *, older_than_seconds, now: float | None) -> list[str]:
    q = select(User.id).where(User.is_guest.is_(True))
    if older_than_seconds is not None:
        cutoff = (time.time() if now is None else now) - older_than_seconds
        q = q.where(User.created_at < cutoff)
    return list((await db.execute(q)).scalars().all())


async def _purge_guests(db: AsyncSession, guest_ids: list[str]) -> dict:
    """Delete the given guest users and every row attributable to them. Join-by-convention (no
    FKs), so order doesn't matter for integrity — we simply remove each dependent set."""
    if not guest_ids:
        return {"guests": 0, "posts": 0, "advertiser_removed": False}

    guest_post_ids = list(
        (await db.execute(select(Post.id).where(Post.author_id.in_(guest_ids)))).scalars().all()
    )
    acct_ids = list(
        (await db.execute(
            select(AdvertiserAccount.id).where(AdvertiserAccount.owner_user_id.in_(guest_ids))
        )).scalars().all()
    )

    # Social footprint: messages either way, follow edges either way, the guest's likes/comments
    # AND everyone else's likes/comments on the guest's now-deleted posts, then the posts.
    await db.execute(delete(Message).where(
        or_(Message.sender_id.in_(guest_ids), Message.recipient_id.in_(guest_ids))
    ))
    await db.execute(delete(Follow).where(
        or_(Follow.follower_id.in_(guest_ids), Follow.followee_id.in_(guest_ids))
    ))
    like_cond = Like.user_id.in_(guest_ids)
    comment_cond = Comment.author_id.in_(guest_ids)
    if guest_post_ids:
        like_cond = or_(like_cond, Like.post_id.in_(guest_post_ids))
        comment_cond = or_(comment_cond, Comment.post_id.in_(guest_post_ids))
    await db.execute(delete(Like).where(like_cond))
    await db.execute(delete(Comment).where(comment_cond))
    await db.execute(delete(Post).where(Post.author_id.in_(guest_ids)))

    # Real ad events served TO the guest (their impressions/clicks/conversions on live campaigns).
    await db.execute(delete(AdConversion).where(AdConversion.viewer_user_id.in_(guest_ids)))
    await db.execute(delete(AdClick).where(AdClick.viewer_user_id.in_(guest_ids)))
    await db.execute(delete(AdImpression).where(AdImpression.viewer_user_id.in_(guest_ids)))

    # Any advertiser hierarchy a guest owned. In v1 the cabinet is single-tenant (acct-local), so
    # guests own no accounts and this is a no-op — but scoped correctly for when ownership lands.
    if acct_ids:
        camp_ids = list((await db.execute(
            select(Campaign.id).where(Campaign.account_id.in_(acct_ids))
        )).scalars().all())
        await db.execute(delete(DeliveryBucket).where(DeliveryBucket.account_id.in_(acct_ids)))
        await db.execute(delete(BudgetState).where(BudgetState.account_id.in_(acct_ids)))
        if camp_ids:
            await db.execute(delete(LearningState).where(LearningState.campaign_id.in_(camp_ids)))
            set_ids = list((await db.execute(
                select(AdSet.id).where(AdSet.campaign_id.in_(camp_ids))
            )).scalars().all())
            if set_ids:
                await db.execute(delete(Ad).where(Ad.ad_set_id.in_(set_ids)))
            await db.execute(delete(AdSet).where(AdSet.campaign_id.in_(camp_ids)))
            await db.execute(delete(Campaign).where(Campaign.account_id.in_(acct_ids)))
        await db.execute(delete(AdvertiserAccount).where(AdvertiserAccount.id.in_(acct_ids)))

    await db.execute(delete(Profile).where(Profile.user_id.in_(guest_ids)))
    await db.execute(delete(User).where(User.id.in_(guest_ids)))
    await db.commit()
    return {"guests": len(guest_ids), "posts": len(guest_post_ids), "advertiser_removed": bool(acct_ids)}


async def reap_expired_guests(db: AsyncSession, *, older_than_seconds=GUEST_TTL_SECONDS, now=None) -> dict:
    """Delete guests older than the TTL (and their data). The scheduled sweep."""
    return await _purge_guests(db, await _expired_guest_ids(db, older_than_seconds=older_than_seconds, now=now))


async def reset_all_guests(db: AsyncSession) -> dict:
    """Delete every guest regardless of age — a full sandbox reset."""
    return await _purge_guests(db, await _expired_guest_ids(db, older_than_seconds=None, now=None))
