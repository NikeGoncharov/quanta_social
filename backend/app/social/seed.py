"""Seed a synthetic social network so the feed is alive from the first visit.

Phase 5 scales the modest first-boot roster up to the full showcase: ~70 synthetic accounts
spanning every world interest, a few hundred themed posts (a deterministic slice carrying a
stock image), a dense shared-interest follow graph, plus likes and comments so counts read as
a living network. Everything is generated from one seeded RNG, so the network is identical on
every fresh boot — a stable public demo, not a different world each restart.

Idempotent: a no-op once any synthetic user exists (a dev DB carried across restarts keeps its
ids and history). All names are invented, never real people; interests, geos and demographics
are drawn from the world catalog so a profile reads consistently and can be interest-targeted
by a live campaign.
"""
import json
import random
import time

from sqlalchemy import func, select

from app.models import Comment, Follow, Like, Post, Profile, User

# Mirrors the world catalog (adsim/world/world.yaml). Kept as a local constant because the seed
# is authored content anyway — the roster, bios and posts are hand-written against these keys.
INTERESTS = [
    "tech", "gaming", "finance", "fashion", "travel", "fitness", "food", "autos",
    "beauty", "sports", "music", "parenting", "home", "pets", "education",
]
GEOS = ["USA", "GBR", "DEU", "BRA", "IND"]
AGE_BANDS = ["18-24", "25-34", "35-44", "45+"]
GENDERS = ["F", "M"]

SEED = 1_704  # any fixed value — pins the whole synthetic network deterministically

# The curated highlights: hand-written voices with a distinct personality. Kept first (and with
# stable handles) because tests and the demo narrative reference them by name.
# (handle, display_name, interest, bio, [posts...])
_FEATURED = [
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

# Invented name pools (internationally varied to match the geo spread; clearly fictional).
_FIRST = [
    "Aria", "Bassam", "Camila", "Dmitri", "Elena", "Farah", "Gabriel", "Hana", "Ibrahim",
    "Julia", "Kenji", "Lena", "Marco", "Nadia", "Omar", "Priya", "Quinn", "Rosa", "Sven",
    "Tara", "Umar", "Vera", "Wei", "Ximena", "Yara", "Zane", "Amara", "Bruno", "Clara",
    "Diego", "Esther", "Felix", "Greta", "Hugo", "Ines", "Jonas", "Keira", "Luca", "Mira",
    "Noah", "Olga", "Pablo", "Rania", "Soren", "Talia", "Uma", "Viktor", "Wren", "Yusuf", "Zara",
]
_LAST = [
    "Adeyemi", "Bauer", "Castro", "Dubois", "Eriksson", "Ferrari", "Gupta", "Haas", "Ivanov",
    "Jensen", "Kowalski", "Lindqvist", "Moreau", "Nakamura", "Okafor", "Petrov", "Quintero",
    "Rossi", "Silva", "Tan", "Ueda", "Varga", "Wang", "Yilmaz", "Zhang", "Almeida", "Bianchi",
    "Costa", "Delgado", "Nazarian",
]

# Per-interest post pools. Users of an interest sample a few of these (no repeats within a user),
# so the feed reads varied without hand-authoring a post for every account.
_POSTS = {
    "tech": [
        "Refactored a gnarly module today. Same behavior, half the code. Deeply satisfying.",
        "The simplest solution you're slightly embarrassed by usually wins.",
        "Wrote the tests I should've written last week. Past me owes present me.",
        "A good error message is a love letter to your future self.",
        "Turned off notifications for two hours and shipped more than all of yesterday.",
        "The bug was in the code I was 'sure' was fine. It always is.",
        "Naming things is still the hardest problem. No, I won't elaborate.",
    ],
    "gaming": [
        "Beat the level I rage-quit last month. Persistence, or stubbornness — same thing.",
        "Indie games keep out-designing the big studios. Small teams, big ideas.",
        "Co-op across three time zones tonight. Worth the sleep debt.",
        "Backlog grew by two, shrank by one. Net negative, as always.",
        "That soundtrack has been living in my head rent-free for a week.",
        "Speedrun attempt #47. We don't talk about attempts 1 through 46.",
    ],
    "finance": [
        "Boring portfolios win. Set it, automate it, ignore it.",
        "Listed every subscription I pay for. Cancelled three on the spot.",
        "Compounding is quiet for years, then suddenly loud. Stay in your seat.",
        "An emergency fund is the cheapest peace of mind you can buy.",
        "The best budget is the one you'll actually keep. Simple beats perfect.",
        "Markets did a dramatic thing today. My plan did not change.",
    ],
    "fashion": [
        "Fewer, better pieces. My closet finally makes sense.",
        "Tailored a thrifted blazer for the price of a coffee. Elite value.",
        "Neutral base, one bold accent. Never fails.",
        "Sold what I don't wear. The wardrobe breathes again.",
        "Good shoes and a good bag outlast every trend.",
        "Fit over logo, every single time.",
    ],
    "travel": [
        "Overnight trains beat 6am flights. I won't be taking questions.",
        "The best meals are three streets past the tourist map.",
        "Packed two weeks into a carry-on. Freedom is light.",
        "Learned ten words of the local language. Doors opened everywhere.",
        "The detour was the trip. It usually is.",
        "Slow travel: one city, one week, zero rushing.",
    ],
    "fitness": [
        "Showed up tired, trained anyway. Small wins stack.",
        "Deload week isn't weakness — it's how you keep going.",
        "Sleep is the most underrated supplement. Full stop.",
        "Progress photos over the scale. The mirror tells a longer story.",
        "Consistency beats intensity you can't repeat.",
        "Rest days are training days for your joints.",
    ],
    "food": [
        "Leftover roast veg became tomorrow's grain bowl. Elite laziness.",
        "A sharp knife changes everything. That's the whole tip.",
        "Weeknight rule: five ingredients, one pan, zero stress.",
        "Made stock from scraps. Free flavor hiding in the freezer.",
        "Salt your pasta water like the sea. Trust me.",
        "The best recipe is the one you can cook from memory.",
    ],
    "autos": [
        "Detailed the car by hand today. Meditative and free.",
        "Manual gearbox, empty road, good playlist. That's the whole hobby.",
        "Tire pressure checked, fluids topped. Boring maintenance saves fortunes.",
        "Planned an EV road trip around chargers and good coffee stops.",
        "Old cars have soul. Also, occasionally, a check-engine light.",
        "A clean engine bay is a happy engine bay.",
    ],
    "beauty": [
        "Skincare is just sunscreen and consistency. Everything else is bonus.",
        "Decluttered the shelf down to five things I actually use.",
        "A good night's sleep beats any serum. Rude, but true.",
        "Bold lip, nothing else. Instant effort with zero effort.",
        "Patch test first. Learned that one the hard way.",
        "Less product, more water. My skin said thank you.",
    ],
    "sports": [
        "Sunday-league knees, top-flight dreams. Balance.",
        "Watched the comeback of the season with total strangers. Magic.",
        "Ran the local 10k. Slow, but I finished smiling.",
        "Underdogs make the whole sport worth watching.",
        "New best on the bike commute. Legs are furious.",
        "Stats are fun, but the eye test still matters.",
    ],
    "music": [
        "New loop stuck in my head since 2am. Sending help and coffee.",
        "Analog warmth is real. I won't be taking questions.",
        "Learned three chords, wrote a whole song. Music is generous.",
        "Made a playlist for the exact mood of a rainy commute.",
        "Live shows in tiny venues beat stadiums every time.",
        "Practiced the scales I hated. Solos got easier. Annoying but true.",
    ],
    "parenting": [
        "Toddler negotiated bedtime like a seasoned lawyer. I lost.",
        "Lowered my standards, raised my sanity. Everyone's happier.",
        "The mess is temporary, the memory isn't. Mostly believe that at 7am.",
        "Read the same book four times tonight. They requested a fifth.",
        "Snacks packed, shoes lost, snacks found in the shoes.",
        "Small humans, big feelings. We're figuring it out together.",
    ],
    "home": [
        "Rearranged one corner and the whole room feels new.",
        "A plant, a lamp, and a clear surface fix almost any room.",
        "Fixed the wobbly shelf myself. Absurdly proud.",
        "Decluttered a drawer. Found things I'd bought twice.",
        "Warm light after sunset changes the whole mood of a home.",
        "Cleaning while a podcast plays: the only way it gets done.",
    ],
    "pets": [
        "The cat knocked the plant over again. Chaos gremlin, fully loved.",
        "Adopt, foster, or just donate — shelters need all of it.",
        "The dog learned a new trick for exactly one treat's worth of effort.",
        "Morning walk with the pup beats any alarm clock.",
        "Vet checkup done. Good boy, expensive boy.",
        "Their favorite toy is, of course, the box it came in.",
    ],
    "education": [
        "Re-explaining a concept is the fastest way to actually learn it.",
        "Finished a course I started eight months ago. Discipline over momentum.",
        "Twenty minutes a day beats a cram session every time.",
        "Took messy notes, rewrote them clean. The rewrite is where it sticks.",
        "Learning in public is scary and worth it. Wrong in the open, right sooner.",
        "Curiosity is a muscle. Used it today; it's a little stronger.",
    ],
}

_COMMENTS = [
    "This is so real.", "Needed this today, thanks.", "Okay this is a great point.",
    "Saving this one.", "Couldn't agree more.", "Ha, called out.", "Well said.",
    "Facts.", "This unlocked something for me.", "Exactly how I feel about it.",
]

_DAY = 86_400
_SPREAD_DAYS = 14  # posts fan out over the last two weeks for a natural timeline


def _image_for(interest: str, rng: random.Random) -> str:
    """A category-matched gallery key. The frontend renders deterministic art from the string,
    so any `stock/<interest>-<n>.jpg` is a valid image — no binary assets in v1."""
    return f"stock/{interest}-{rng.randint(1, 3)}.jpg"


async def ensure_seed_social(session) -> None:
    already = (
        await session.execute(
            select(func.count()).select_from(User).where(User.is_synthetic.is_(True))
        )
    ).scalar()
    if already:
        return

    rng = random.Random(SEED)
    now = time.time()
    # Every synthetic account is anchored comfortably in the past so a later real registration
    # (created at wall-now) always sorts newest in "who to follow" and never collides in time.
    base = now - _DAY

    users: list[tuple[str, str]] = []       # (user_id, interest)
    posts: list[tuple[str, str]] = []        # (post_id, author_id)

    def add_user(uid: str, handle: str, name: str, interest: str, bio: str, created: float) -> None:
        session.add(User(
            id=uid, email=None, handle=handle, password_hash=None,
            is_synthetic=True, is_guest=False, created_at=created,
        ))
        session.add(Profile(
            user_id=uid, display_name=name, avatar_seed=uid, bio=bio,
            interests_json=json.dumps([interest]),
            geo=rng.choice(GEOS), age_band=rng.choice(AGE_BANDS), gender=rng.choice(GENDERS),
        ))
        users.append((uid, interest))

    def add_posts(uid: str, interest: str, bodies: list[str], prefix: str) -> None:
        for body in bodies:
            pid = f"{prefix}-{len(posts):04d}"
            image = _image_for(interest, rng) if rng.random() < 0.35 else None
            created = base - rng.random() * _SPREAD_DAYS * _DAY
            session.add(Post(id=pid, author_id=uid, body=body, image_key=image, created_at=created))
            posts.append((pid, uid))

    # 1) The curated highlights (stable ids/handles).
    for i, (handle, name, interest, bio, body_list) in enumerate(_FEATURED):
        uid = f"usr-syn-{i:02d}"
        add_user(uid, handle, name, interest, bio, base - i)
        add_posts(uid, interest, body_list, "post-syn")

    # 2) The generated crowd: a handful of voices per interest, each posting a themed sample.
    taken_handles = {h for h, *_ in _FEATURED}
    gi = 0
    for interest in INTERESTS:
        for _ in range(4):  # ~4 accounts per interest -> ~60 generated + 10 featured
            first, last = rng.choice(_FIRST), rng.choice(_LAST)
            name = f"{first} {last}"
            handle = f"{first}_{last}".lower()
            while handle in taken_handles:
                handle = f"{first}_{last}{rng.randint(2, 99)}".lower()
            taken_handles.add(handle)
            uid = f"usr-syn-g{gi:03d}"
            bio = rng.choice([
                f"Into {interest}, mostly. Here for the good stuff.",
                f"Sharing what I learn about {interest}.",
                f"{interest.capitalize()} and everything around it.",
                "Small thoughts, posted often.",
            ])
            add_user(uid, handle, name, interest, bio, base - 100 - gi)
            k = rng.randint(4, 6)
            bodies = rng.sample(_POSTS[interest], min(k, len(_POSTS[interest])))
            add_posts(uid, interest, bodies, "post-gen")
            gi += 1

    # 3) A dense follow graph, biased toward shared interest so feeds feel coherent. Each account
    #    follows a few peers in its own niche plus a couple of the featured highlights.
    by_interest: dict[str, list[str]] = {}
    for uid, interest in users:
        by_interest.setdefault(interest, []).append(uid)
    featured_ids = [f"usr-syn-{i:02d}" for i in range(len(_FEATURED))]
    edges: set[tuple[str, str]] = set()
    for uid, interest in users:
        peers = [p for p in by_interest.get(interest, []) if p != uid]
        picks = set(rng.sample(peers, min(len(peers), rng.randint(2, 4))))
        picks.update(rng.sample(featured_ids, min(len(featured_ids), 2)))
        picks.discard(uid)
        for target in picks:
            edges.add((uid, target))
    for follower, followee in edges:
        session.add(Follow(follower_id=follower, followee_id=followee, created_at=base))

    # 4) Likes + a few comments so posts carry non-zero social proof.
    user_ids = [uid for uid, _ in users]
    post_ids = [pid for pid, _ in posts]
    author_of = dict(posts)  # post_id -> author_id
    liked: set[tuple[str, str]] = set()  # (user_id, post_id) — Like's composite PK, deduped here
    for uid in user_ids:
        for pid in rng.sample(post_ids, min(len(post_ids), rng.randint(3, 8))):
            if author_of[pid] == uid or (uid, pid) in liked:
                continue  # no self-likes; the composite PK must stay unique
            liked.add((uid, pid))
            session.add(Like(user_id=uid, post_id=pid, created_at=base))
    ci = 0
    for pid, author in posts:
        if rng.random() < 0.18:
            commenter = rng.choice(user_ids)
            if commenter == author:
                continue
            session.add(Comment(
                id=f"cmt-seed-{ci:04d}", post_id=pid, author_id=commenter,
                body=rng.choice(_COMMENTS), created_at=base,
            ))
            ci += 1
