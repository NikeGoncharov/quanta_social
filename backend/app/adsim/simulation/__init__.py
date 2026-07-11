"""The real-time simulation: delivery state, the learning phase, the segment behavior
model, and run_tick — the pure statistical aggregation that produces per-segment deltas.

The async world loop, batched writer, and SimControl live in Phase 2 (they touch the DB
and the event loop); everything here is pure and unit-tested.
"""
