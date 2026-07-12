"""Engine-native campaign types.

A `Line` is a flattened campaign x ad_set x ad that the engine bids with. In Phase 3 these
are built from DB rows; here they are plain dataclasses so the engine stays pure and the
tests can construct them directly.
"""
from dataclasses import dataclass, field

from ..models.creative import NativeCreative
from ..models.enums import BillingEvent, Objective, Pacing


@dataclass(frozen=True)
class Targeting:
    interests: frozenset = frozenset()
    geos: frozenset = frozenset()
    age_bands: frozenset = frozenset()
    genders: frozenset = frozenset()

    @classmethod
    def from_dict(cls, d: dict) -> "Targeting":
        return cls(
            interests=frozenset(d.get("interests", []) or []),
            geos=frozenset(d.get("geos", []) or []),
            age_bands=frozenset(d.get("age_bands", []) or []),
            genders=frozenset(d.get("genders", []) or []),
        )

    def to_dict(self) -> dict:
        """Sorted plain-list form for JSON columns / API payloads (round-trips from_dict)."""
        return {
            "interests": sorted(self.interests),
            "geos": sorted(self.geos),
            "age_bands": sorted(self.age_bands),
            "genders": sorted(self.genders),
        }


@dataclass(frozen=True)
class FreqCap:
    impressions: int   # per person per window
    per_days: int = 1


@dataclass(frozen=True)
class Line:
    ad_id: str
    ad_set_id: str
    campaign_id: str
    account_id: str
    seat: str                      # the advertiser account acts as a buyer seat
    objective: Objective
    bid_micros: int                # meaning depends on billing_event (CPM / CPC / target CPA)
    billing_event: BillingEvent
    targeting: Targeting
    daily_budget_micros: int
    baseline_conv_value_micros: int
    creative: NativeCreative
    adomain: str = ""
    cats: frozenset = field(default_factory=frozenset)
    freq_cap: FreqCap | None = None
    pacing: Pacing = Pacing.EVEN
    active: bool = True
