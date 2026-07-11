"""Typed world objects (frozen dataclasses). Built by loader.load_world from world.yaml."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PhantomSeat:
    """A synthetic competitor DSP — gives a lone campaign real price pressure and
    populates the RTB Inspector with named seat bids."""
    name: str
    aggressiveness: float  # multiplier on the segment's reference bid


@dataclass(frozen=True)
class Segment:
    """One targetable cell: interest x geo x age_band x gender. Latent CTR/CVR/value and
    the competitive reference bid are hidden from the advertiser."""
    id: str
    interest: str
    geo: str
    age_band: str
    gender: str
    size: int                    # people in this cell
    opportunity_rate: float      # ad opportunities per sim-second
    base_ctr: float
    base_cvr: float              # conversions per click
    value_multiplier: float      # scales the advertiser's baseline conversion value
    reference_bid_micros: int    # competitive CPM (before live market_density)


@dataclass(frozen=True)
class Economy:
    currency: str
    auction_type: int            # 1 first-price | 2 second-price-plus
    default_floor_micros: int
    market_density: float        # global multiplier on reference bids (live UI knob)
    daily_opportunities: int


@dataclass(frozen=True)
class Learning:
    """Conversions/Engagement objectives ramp from start_lift to target_lift as signal
    accumulates toward `threshold`; below threshold the campaign is 'in learning'."""
    start_lift: float
    target_lift: float
    threshold: float
    noise: float


@dataclass(frozen=True)
class Fatigue:
    free_frequency: float        # impressions/person before CTR starts decaying
    k: float


@dataclass(frozen=True)
class World:
    interests: tuple
    geos: tuple
    age_bands: tuple
    genders: tuple
    segments: dict               # id -> Segment
    phantom_seats: tuple
    economy: Economy
    learning: Learning
    fatigue: Fatigue
    relevance_uplift: float
    baseline_conv_value_micros: int
    population: int

    def segment_list(self) -> list:
        return list(self.segments.values())
