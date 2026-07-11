"""DeliveryState — the mutable running state the world carries between ticks.

Per-day counters (spend, frequency) reset each sim-day; lifetime counters (cumulative
impressions for fatigue, learning signal) persist. In Phase 2 this is materialized in the
DB (budget_state / freq_cap_counter / reach_state / learning_state); here it is an
in-memory container so the engine stays pure and testable.
"""
from dataclasses import dataclass, field


@dataclass
class DeliveryState:
    sim_day: int = 0
    spent_today_micros: dict = field(default_factory=dict)      # ad_id -> micros
    spent_lifetime_micros: dict = field(default_factory=dict)   # ad_id -> micros
    freq_shown_today: dict = field(default_factory=dict)        # (campaign_id, seg_id) -> imps today
    cum_impressions: dict = field(default_factory=dict)         # (ad_id, seg_id) -> lifetime imps (fatigue)
    learning_signal: dict = field(default_factory=dict)         # ad_set_id -> accumulated signal

    def roll_to_day(self, day: int) -> None:
        """Reset per-day counters when the sim-day advances."""
        if day != self.sim_day:
            self.sim_day = day
            self.spent_today_micros = {}
            self.freq_shown_today = {}
