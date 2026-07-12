"""Seed a small synthetic social network so the feed is alive from first boot.

Idempotent (a no-op once any synthetic user exists). Deliberately modest — Phase 5 scales
this to the full ~50-200 synthetics + hundreds of posts and the guest demo sandbox. Names are
invented, not real people. Interests are drawn from the world catalog so a synthetic profile
reads consistently and could be interest-targeted.
"""
import json
import time

from sqlalchemy import func, select

from app.models import Follow, Post, Profile, User

# (handle, display_name, interest, bio, [posts...])
_SYNTHETICS = [
    ("maya_codes", "Maya Ortiz", "tech", "Building small tools that do one thing well.",
     ["Shipped a tiny CLI this weekend. Nothing beats deleting code that finally works.",
      "Hot take: the best framework is the one your team already understands.",
      "Spent an hour debugging a typo. The typo won for a while."]),
    ("leo_plays", "Leo Novak", "gaming", "Backlog: 400 games. Time: none.",
     ["Finally beat that boss I've been stuck on for a week. Worth it.",
      "Co-op night > any single-player campaign, fight me."]),
    ("nora_funds", "Nora Bishop", "finance", "Boring money habits, exciting compounding.",
     ["Automate your savings and forget about it. Future you says thanks.",
      "The market did a thing today. It will do another thing tomorrow."]),
    ("theo_trails", "Theo Park", "travel", "Collecting train rides, not souvenirs.",
     ["Overnight train beats a 6am flight every single time.",
      "Best meals happen three streets away from the tourist map."]),
    ("ivy_lifts", "Ivy Chen", "fitness", "Progress over perfection. Rest is a rep.",
     ["Deload week is not a weakness. Your joints agree.",
      "Showed up tired, lifted anyway. Small wins stack."]),
    ("sam_eats", "Sam Reyes", "food", "Weeknight cooking, zero food waste.",
     ["Leftover roast veg → next-day grain bowl. Elite laziness.",
      "A good knife changes everything. That's the whole tip."]),
    ("remy_style", "Remy Dubois", "fashion", "Fewer, better things.",
     ["Capsule wardrobe update: sold two jackets, kept the one I actually wear.",
      "Tailoring a $20 thrift find beats buying new. Every time."]),
    ("kai_sound", "Kai Anders", "music", "Making beats in a tiny apartment.",
     ["New loop stuck in my head since 2am. Sending help (and coffee).",
      "Analog warmth is real and I will not be taking questions."]),
    ("zoe_paws", "Zoe Bright", "pets", "Two cats, zero regrets.",
     ["The cat knocked my plant over again. Chaos gremlin, but I love her.",
      "Adopt, foster, or just donate — shelters need all of it."]),
    ("dev_reads", "Dev Malhotra", "education", "Learning in public, one note at a time.",
     ["Re-explaining a concept to someone is the fastest way to learn it yourself.",
      "Finished a course I started 8 months ago. Momentum is a myth; discipline isn't."]),
]


async def ensure_seed_social(session) -> None:
    already = (
        await session.execute(
            select(func.count()).select_from(User).where(User.is_synthetic.is_(True))
        )
    ).scalar()
    if already:
        return

    base = time.time()
    users: list[User] = []
    for i, (handle, name, interest, bio, _posts) in enumerate(_SYNTHETICS):
        uid = f"usr-syn-{i:02d}"
        users.append(User(
            id=uid, email=None, handle=handle, password_hash=None,
            is_synthetic=True, is_guest=False, created_at=base - i,
        ))
        session.add(users[-1])
        session.add(Profile(
            user_id=uid, display_name=name, avatar_seed=uid, bio=bio,
            interests_json=json.dumps([interest]), geo="USA", age_band="25-34", gender="",
        ))

    # Posts, newest first, spaced ~11 sim... wall minutes apart for a natural feed order.
    seq = 0
    for i, (_h, _n, _int, _bio, posts) in enumerate(_SYNTHETICS):
        uid = f"usr-syn-{i:02d}"
        for j, bodytext in enumerate(posts):
            session.add(Post(
                id=f"post-syn-{seq:03d}", author_id=uid, body=bodytext,
                image_key=None, created_at=base - seq * 660,
            ))
            seq += 1

    # A light follow graph among the synthetics so profiles show non-zero counts.
    n = len(_SYNTHETICS)
    for i in range(n):
        for off in (1, 2):
            session.add(Follow(
                follower_id=f"usr-syn-{i:02d}", followee_id=f"usr-syn-{(i + off) % n:02d}",
                created_at=base,
            ))
