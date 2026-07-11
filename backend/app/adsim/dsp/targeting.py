"""Targeting match + audience sizing (drives the cabinet's live audience gauge).

The relevance rule is the core precision-vs-reach lesson: the CTR/CVR uplift applies only
when a campaign EXPLICITLY interest-targets a segment. Target narrowly -> uplift but small
reach; target broadly -> big reach at base rates.
"""
from ..world.schema import Segment, World
from .campaign import Targeting


def targeting_matches(t: Targeting, seg: Segment) -> bool:
    if t.interests and seg.interest not in t.interests:
        return False
    if t.geos and seg.geo not in t.geos:
        return False
    if t.age_bands and seg.age_band not in t.age_bands:
        return False
    if t.genders and seg.gender not in t.genders:
        return False
    return True


def matching_segments(t: Targeting, world: World) -> list[Segment]:
    return [s for s in world.segment_list() if targeting_matches(t, s)]


def audience_size(t: Targeting, world: World) -> int:
    return sum(s.size for s in world.segment_list() if targeting_matches(t, s))


def is_interest_relevant(t: Targeting, seg: Segment) -> bool:
    """True when the campaign explicitly interest-targets this segment (relevance uplift)."""
    return bool(t.interests) and seg.interest in t.interests
