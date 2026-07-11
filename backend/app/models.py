"""SQLAlchemy models for Quanta.

Tables are added per phase; import this module wherever Base.metadata must be fully
populated (Alembic env, init_db).

  Phase 1: (engine is pure — no DB models)
  Phase 2: delivery_bucket, budget_state, freq_cap_counter, reach_state,
           auction_sample, sim_control, learning_state
  Phase 3: advertiser_accounts, campaigns, ad_sets, ads
  Phase 4: users, profiles, follows, posts, likes, comments, messages,
           ad_impression, ad_click, ad_conversion
"""
from app.database import Base  # noqa: F401

# Models are declared here (or imported here) as each phase lands.
