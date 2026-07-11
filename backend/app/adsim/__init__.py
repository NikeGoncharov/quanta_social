"""adsim — Quanta's in-process programmatic advertising engine.

Modeled on OpenRTB 2.6 (object shapes, auction settlement, notice lifecycle) but the
transport is stubbed and traffic is synthetic. Pure Python: no FastAPI or SQLAlchemy
imports live under this package, so the whole engine is unit-testable in isolation.

Layout:
  models/       OpenRTB objects, enums, macros, the shared NativeCreative
  world/        the synthetic world definition (segments, interests, market, economy)
  ssp/          publisher inventory + BidRequest generation
  exchange/     eligibility, auction, settlement, notices
  dsp/          bidder, targeting, pacing, bid strategy, campaign types
  simulation/   clock, segment model, learning phase, run_tick (statistical aggregate)
  metrics/      ledger, KPIs, reports, diagnostics
"""
