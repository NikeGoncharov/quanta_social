"""The social network: profiles, the follow graph, posts, the sponsored feed, and DMs.

Aggregated into one router mounted at /social. The sponsored slot in the feed is where the
social app meets the ad engine — a real, billed auction (see feed.py)."""
from fastapi import APIRouter

from . import feed, messages, posts, profiles

router = APIRouter(prefix="/social", tags=["social"])
router.include_router(profiles.router)
router.include_router(posts.router)
router.include_router(feed.router)
router.include_router(messages.router)
