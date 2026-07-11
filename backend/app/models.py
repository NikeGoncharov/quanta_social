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
