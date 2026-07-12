"""SQLAlchemy models for Quanta.

Tables are added per phase; import this module wherever Base.metadata must be fully
populated (Alembic env, init_db).

  Phase 1: (engine is pure — no DB models)
  Phase 2: delivery_bucket, budget_state, freq_cap_counter, reach_state,
           auction_sample, sim_control, learning_state
  Phase 3: advertiser_accounts, campaigns, ad_sets, ads
  Phase 4: users, profiles, follows, posts, likes, comments, messages,
           ad_impression, ad_click, ad_conversion

Money is stored as integer micros everywhere (1 USD = 1_000_000), matching the engine;
the API converts to USD floats at the edge. All timestamps are *sim* time, not wall time:
`bucket_start` is a sim-minute index (sim_seconds // 60) and `sim_time` is elapsed sim
seconds — the one global clock the world loop advances.
"""
from sqlalchemy import Boolean, Column, Float, Index, Integer, String, Text, UniqueConstraint

from app.database import Base


# ---------------------------------------------------------------------------
# Phase 3 — the advertiser hierarchy the cabinet edits and the world loop
# delivers. account -> campaign -> ad_set -> ad. IDs are plain strings joined
# by convention (like the delivery tables — no ForeignKeys), so a flattened
# `Line` can be rebuilt from these rows and fed to the same pure engine that
# Phase 2 ran on a hardcoded seed roster.
#
# v1 keeps the shape 1 campaign -> 1 ad_set -> 1 ad (the wizard creates the
# triple atomically): the daily budget then maps cleanly onto the single line,
# whose spend the engine keys by ad_id. Multi-ad-set budget sharing is v2.
# ---------------------------------------------------------------------------


class AdvertiserAccount(Base):
    """A buyer: acts as the OpenRTB seat its campaigns bid under. `owner_user_id` is
    nullable until Phase 4 wires auth; `is_demo` marks the seeded showcase accounts."""
    __tablename__ = "advertiser_accounts"

    id = Column(String, primary_key=True)               # e.g. "acct-local" / "acct-<uuid8>"
    owner_user_id = Column(String, nullable=True)       # Phase 4 auth
    name = Column(String, nullable=False)
    currency = Column(String, nullable=False, default="USD")
    is_demo = Column(Boolean, nullable=False, default=False)
    created_at = Column(Float, nullable=False, default=0.0)  # wall epoch; seeds sort first at 0


class Campaign(Base):
    """The objective + budget + pacing envelope. The objective decides the funnel stage,
    the billing event, and whether delivery goes through a learning phase."""
    __tablename__ = "campaigns"

    id = Column(String, primary_key=True)               # "cmp-<uuid8>" / "seed-<slug>-cmp"
    account_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    objective = Column(String, nullable=False)          # awareness | traffic | engagement | conversions
    status = Column(String, nullable=False, default="active")  # active | paused | draft
    daily_budget_micros = Column(Integer, nullable=False, default=0)
    pacing = Column(String, nullable=False, default="even")    # even | asap
    baseline_conv_value_micros = Column(Integer, nullable=False, default=0)
    created_at = Column(Float, nullable=False, default=0.0)

    __table_args__ = (Index("ix_campaign_account", "account_id"),)


class AdSet(Base):
    """The bid + targeting + frequency envelope. `bid_micros` means a CPM (Awareness), a
    CPC (Traffic/Engagement) or a target CPA (Conversions) — the strategy reads it by
    the campaign's objective, exactly as the seed roster did."""
    __tablename__ = "ad_sets"

    id = Column(String, primary_key=True)               # "set-<uuid8>" / "seed-<slug>-set"
    campaign_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="active")
    bid_micros = Column(Integer, nullable=False, default=0)
    bid_strategy = Column(String, nullable=False, default="manual")  # BidStrategy value
    targeting_json = Column(Text, nullable=False, default="{}")      # {interests,geos,age_bands,genders}
    freq_cap_impressions = Column(Integer, nullable=True)            # None -> no cap
    freq_cap_per_days = Column(Integer, nullable=False, default=1)

    __table_args__ = (Index("ix_adset_campaign", "campaign_id"),)


class Ad(Base):
    """The creative. `creative_json` is a serialized NativeCreative — the one creative
    schema shared by the editor, the OpenRTB `adm`, and the sponsored-post renderer."""
    __tablename__ = "ads"

    id = Column(String, primary_key=True)               # "ad-<uuid8>" / "seed-<slug>-ad"
    ad_set_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="active")
    creative_json = Column(Text, nullable=False, default="{}")
    adomain = Column(String, nullable=False, default="")

    __table_args__ = (Index("ix_ad_adset", "ad_set_id"),)


class DeliveryBucket(Base):
    """The statistical heart of persistence: one row per (ad, sim-minute, source).

    Synthetic delivery is aggregated into these compact buckets — never one row per
    impression. `breakdowns` holds a JSON split of the metrics by interest / geo / age /
    gender so the cabinet can explore dimensions without a row explosion. Real (friend)
    impressions land under source='real' in Phase 4; Phase 2 is all 'synthetic'.
    """
    __tablename__ = "delivery_bucket"

    id = Column(Integer, primary_key=True)
    ad_id = Column(String, nullable=False)
    ad_set_id = Column(String, nullable=False)
    campaign_id = Column(String, nullable=False)
    account_id = Column(String, nullable=False)
    bucket_start = Column(Integer, nullable=False)          # sim-minute index
    source = Column(String, nullable=False, default="synthetic")

    auctions = Column(Integer, nullable=False, default=0)
    impressions = Column(Integer, nullable=False, default=0)
    clicks = Column(Integer, nullable=False, default=0)
    conversions = Column(Integer, nullable=False, default=0)
    spend_micros = Column(Integer, nullable=False, default=0)
    revenue_micros = Column(Integer, nullable=False, default=0)
    # Sim-seconds of world time the bucket's ticks actually spanned. At fast sim speeds one
    # tick covers many minutes and dumps them all into a single bucket, so honest
    # "per sim-minute" rates must divide by this — NOT assume 60.
    covered_seconds = Column(Integer, nullable=False, default=60, server_default="60")
    breakdowns = Column(Text, nullable=False, default="{}")  # JSON: {dimension: {value: {...}}}

    __table_args__ = (
        UniqueConstraint("ad_id", "bucket_start", "source", name="uq_delivery_bucket"),
        Index("ix_delivery_campaign_time", "campaign_id", "bucket_start"),
        Index("ix_delivery_time", "bucket_start"),
    )


class SimControl(Base):
    """Singleton (id=1) mirror of the world loop's controls, so speed / density / the sim
    clock survive a restart. The running loop keeps an in-memory copy and writes here."""
    __tablename__ = "sim_control"

    id = Column(Integer, primary_key=True)                  # always 1
    running = Column(Boolean, nullable=False, default=True)
    speed = Column(Float, nullable=False, default=60.0)     # sim-seconds advanced per real second
    tick_hz = Column(Float, nullable=False, default=2.0)    # loop ticks per real second
    sim_time = Column(Float, nullable=False, default=0.0)   # elapsed sim seconds
    market_density = Column(Float, nullable=False, default=1.0)


class AuctionSample(Base):
    """A ring buffer (~200 rows, oldest evicted) of fully materialized auctions — the raw
    material for the RTB Inspector. `id` is monotonic, so 'newest N' and eviction are trivial."""
    __tablename__ = "auction_sample"

    id = Column(Integer, primary_key=True)
    sim_time = Column(Float, nullable=False)
    segment_key = Column(String, nullable=False)
    line_ad_id = Column(String, nullable=False)
    won = Column(Boolean, nullable=False, default=False)
    winner_seat = Column(String, nullable=False, default="")
    winner_ad_id = Column(String, nullable=False, default="")
    clearing_micros = Column(Integer, nullable=False, default=0)
    floor_micros = Column(Integer, nullable=False, default=0)
    min_to_win_micros = Column(Integer, nullable=False, default=0)
    eligible_count = Column(Integer, nullable=False, default=0)
    filtered_count = Column(Integer, nullable=False, default=0)
    request_json = Column(Text, nullable=False)             # full OpenRTB BidRequest
    bids_json = Column(Text, nullable=False)                # eligible + filtered (with reasons)
    notices_json = Column(Text, nullable=False)             # nurl/burl/lurl log, macros expanded


class BudgetState(Base):
    """Display mirror of the loop's per-line spend (in-memory DeliveryState is authoritative).
    Lets the cabinet show spent-today / budget without reaching into engine memory."""
    __tablename__ = "budget_state"

    ad_id = Column(String, primary_key=True)
    ad_set_id = Column(String, nullable=False)
    campaign_id = Column(String, nullable=False)
    account_id = Column(String, nullable=False)
    sim_day = Column(Integer, nullable=False, default=0)
    spent_today_micros = Column(Integer, nullable=False, default=0)
    spent_lifetime_micros = Column(Integer, nullable=False, default=0)
    daily_budget_micros = Column(Integer, nullable=False, default=0)


class LearningState(Base):
    """Display mirror of the visible learning phase for Conversions / Engagement ad sets."""
    __tablename__ = "learning_state"

    ad_set_id = Column(String, primary_key=True)
    campaign_id = Column(String, nullable=False)
    objective = Column(String, nullable=False)
    accumulated_signal = Column(Float, nullable=False, default=0.0)
    threshold = Column(Float, nullable=False, default=0.0)
    in_learning = Column(Boolean, nullable=False, default=True)


class FreqCapCounter(Base):
    """Per (campaign, sim-day, segment) impressions, for frequency-cap accounting. Schema
    lands in Phase 2; populated by the diagnostics path in Phase 3."""
    __tablename__ = "freq_cap_counter"

    id = Column(Integer, primary_key=True)
    campaign_id = Column(String, nullable=False)
    sim_day = Column(Integer, nullable=False)
    segment_key = Column(String, nullable=False)
    impressions = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("campaign_id", "sim_day", "segment_key", name="uq_freq_cap"),
    )


class ReachState(Base):
    """Per (ad, segment) lifetime impressions + estimated unique reach (drives the reach/
    frequency curve and creative fatigue). Schema lands in Phase 2; populated in Phase 3."""
    __tablename__ = "reach_state"

    id = Column(Integer, primary_key=True)
    ad_id = Column(String, nullable=False)
    segment_key = Column(String, nullable=False)
    cum_impressions = Column(Integer, nullable=False, default=0)
    reached_est = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("ad_id", "segment_key", name="uq_reach_state"),
    )


# ---------------------------------------------------------------------------
# Phase 4 — the social network. One identity (`users`) spans the social app and
# the ad cabinet (advertiser_accounts.owner_user_id points here). String PKs and
# join-by-convention, matching the rest of the schema (no ForeignKeys). Social
# timestamps are WALL epoch seconds (not sim time) — the network runs in real
# time even while the ad world is paused. Real ad events (ad_impression /
# ad_click / ad_conversion) are added alongside the sponsored-feed wiring.
# ---------------------------------------------------------------------------


class User(Base):
    """A social account. Real users register with email + password; the seeded network is
    `is_synthetic` (no password, no login). `handle` is the public @username. The same user id
    can own advertiser accounts, so one person is both a network member and an advertiser."""
    __tablename__ = "users"

    id = Column(String, primary_key=True)               # "usr-<uuid8>" / "usr-<handle>" (synthetics)
    email = Column(String, unique=True, index=True, nullable=True)   # null for synthetic / guest
    handle = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=True)       # null for synthetic / guest (cannot log in)
    is_synthetic = Column(Boolean, nullable=False, default=False)
    is_guest = Column(Boolean, nullable=False, default=False)
    created_at = Column(Float, nullable=False, default=0.0)  # wall epoch


class Profile(Base):
    """1:1 with a user: the display identity plus the interest / geo / demo signals that map a
    real viewer to a world segment when the feed runs a live sponsored auction. `avatar_seed`
    drives a deterministic gradient avatar (no uploads in v1); `interests_json` is a JSON array
    of interest keys drawn from the world's catalog."""
    __tablename__ = "profiles"

    user_id = Column(String, primary_key=True)
    display_name = Column(String, nullable=False, default="")
    avatar_seed = Column(String, nullable=False, default="")
    bio = Column(String, nullable=False, default="")
    interests_json = Column(Text, nullable=False, default="[]")   # ["tech","gaming",...]
    geo = Column(String, nullable=False, default="")              # e.g. "USA" (segment targeting)
    age_band = Column(String, nullable=False, default="")         # e.g. "25-34"
    gender = Column(String, nullable=False, default="")           # e.g. "f" / "m" / ""


class Follow(Base):
    """A directed follow edge (follower -> followee). The composite PK makes an edge idempotent;
    the followee index powers 'followers of X' without a scan."""
    __tablename__ = "follows"

    follower_id = Column(String, primary_key=True)
    followee_id = Column(String, primary_key=True)
    created_at = Column(Float, nullable=False, default=0.0)

    __table_args__ = (Index("ix_follow_followee", "followee_id"),)


class Post(Base):
    """A text post with an optional stock image key. `body` is plain text (no uploads / markdown
    in v1). The (author, time) index serves both a profile's posts and the home feed fan-out."""
    __tablename__ = "posts"

    id = Column(String, primary_key=True)               # "post-<uuid8>"
    author_id = Column(String, nullable=False)
    body = Column(Text, nullable=False, default="")
    image_key = Column(String, nullable=True)           # bundled stock gallery key, optional
    created_at = Column(Float, nullable=False, default=0.0)

    __table_args__ = (Index("ix_post_author_time", "author_id", "created_at"),)


class Like(Base):
    """A user's like on a post. Composite PK keeps it idempotent (one like per user per post)."""
    __tablename__ = "likes"

    user_id = Column(String, primary_key=True)
    post_id = Column(String, primary_key=True)
    created_at = Column(Float, nullable=False, default=0.0)

    __table_args__ = (Index("ix_like_post", "post_id"),)


class Comment(Base):
    """A comment on a post. The (post, time) index returns a post's thread in order."""
    __tablename__ = "comments"

    id = Column(String, primary_key=True)               # "cmt-<uuid8>"
    post_id = Column(String, nullable=False)
    author_id = Column(String, nullable=False)
    body = Column(Text, nullable=False, default="")
    created_at = Column(Float, nullable=False, default=0.0)

    __table_args__ = (Index("ix_comment_post_time", "post_id", "created_at"),)


class Message(Base):
    """A direct message between two users. A conversation is the union of both directions between
    a pair, ordered by time; `read_at` (null until read) drives unread badges."""
    __tablename__ = "messages"

    id = Column(String, primary_key=True)               # "msg-<uuid8>"
    sender_id = Column(String, nullable=False)
    recipient_id = Column(String, nullable=False)
    body = Column(Text, nullable=False, default="")
    created_at = Column(Float, nullable=False, default=0.0)
    read_at = Column(Float, nullable=True)

    __table_args__ = (
        Index("ix_msg_sender", "sender_id", "created_at"),
        Index("ix_msg_recipient", "recipient_id", "created_at"),
    )


# ---------------------------------------------------------------------------
# Phase 4 — REAL ad events. When a logged-in user loads their feed, a genuine
# single-opportunity auction runs (adsim.run_auction) and, if one of our live
# campaigns wins the slot, a fully materialized impression is recorded here (as
# opposed to the synthetic delivery the world loop aggregates into buckets).
# These low-volume rows carry the exact clearing price and the funnel: an
# impression may gain a click, a click may gain a conversion. The same event
# ALSO increments a delivery_bucket row under source='real', so the cabinet's
# dashboards fold real delivery into their totals automatically.
# ---------------------------------------------------------------------------


class AdImpression(Base):
    """One real, billed impression served into a friend's feed. `clearing_micros` is the price
    the auction settled at; `spend_micros` is its per-impression cost (clearing / 1000).
    `bucket_start` pins the sim-minute so a later click/conversion attributes to the same bucket.
    `clicked` / `converted` make the click and conversion idempotent (one each per impression)."""
    __tablename__ = "ad_impression"

    id = Column(String, primary_key=True)               # "imp-<uuid8>"
    ad_id = Column(String, nullable=False)
    ad_set_id = Column(String, nullable=False)
    campaign_id = Column(String, nullable=False)
    account_id = Column(String, nullable=False)
    viewer_user_id = Column(String, nullable=False)
    segment_key = Column(String, nullable=False)
    interest = Column(String, nullable=False, default="")
    geo = Column(String, nullable=False, default="")
    age_band = Column(String, nullable=False, default="")
    gender = Column(String, nullable=False, default="")
    clearing_micros = Column(Integer, nullable=False, default=0)
    spend_micros = Column(Integer, nullable=False, default=0)
    auction_id = Column(String, nullable=False, default="")
    bucket_start = Column(Integer, nullable=False, default=0)  # sim-minute of the impression
    sim_time = Column(Float, nullable=False, default=0.0)
    created_at = Column(Float, nullable=False, default=0.0)    # wall epoch
    clicked = Column(Boolean, nullable=False, default=False)
    converted = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ix_imp_viewer_time", "viewer_user_id", "created_at"),
        Index("ix_imp_campaign_time", "campaign_id", "created_at"),
    )


class AdClick(Base):
    """A real click on a sponsored post (the viewer tapped the CTA)."""
    __tablename__ = "ad_click"

    id = Column(String, primary_key=True)               # "clk-<uuid8>"
    impression_id = Column(String, nullable=False)
    ad_id = Column(String, nullable=False)
    campaign_id = Column(String, nullable=False)
    viewer_user_id = Column(String, nullable=False)
    created_at = Column(Float, nullable=False, default=0.0)

    __table_args__ = (Index("ix_click_impression", "impression_id"),)


class AdConversion(Base):
    """A real conversion attributed (deterministic click-through) to a prior click."""
    __tablename__ = "ad_conversion"

    id = Column(String, primary_key=True)               # "cnv-<uuid8>"
    click_id = Column(String, nullable=False)
    impression_id = Column(String, nullable=False)
    ad_id = Column(String, nullable=False)
    campaign_id = Column(String, nullable=False)
    viewer_user_id = Column(String, nullable=False)
    value_micros = Column(Integer, nullable=False, default=0)
    created_at = Column(Float, nullable=False, default=0.0)

    __table_args__ = (Index("ix_conv_impression", "impression_id"),)
