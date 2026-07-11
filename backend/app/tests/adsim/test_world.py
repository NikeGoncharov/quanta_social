from app.adsim.dsp.campaign import Targeting
from app.adsim.dsp.targeting import audience_size, is_interest_relevant, matching_segments
from app.adsim.world import load_world


def test_world_loads_full_segment_grid():
    w = load_world()
    assert len(w.segments) == 15 * 5 * 4 * 2  # interests x geos x ages x genders = 600
    assert {"tech", "finance", "gaming"} <= set(w.interests)
    assert len(w.phantom_seats) == 6


def test_broad_targeting_reaches_whole_population():
    w = load_world()
    total = audience_size(Targeting(), w)
    assert abs(total - w.population) <= 2000  # rounding across 600 cells


def test_interest_targeting_is_a_subset():
    w = load_world()
    tech = audience_size(Targeting(interests=frozenset({"tech"})), w)
    assert 0 < tech < w.population


def test_intersection_targeting():
    w = load_world()
    t = Targeting(interests=frozenset({"finance"}), geos=frozenset({"USA"}))
    segs = matching_segments(t, w)
    assert segs
    assert all(s.interest == "finance" and s.geo == "USA" for s in segs)


def test_relevance_only_with_explicit_interest_targeting():
    w = load_world()
    seg = next(s for s in w.segment_list() if s.interest == "tech")
    assert is_interest_relevant(Targeting(interests=frozenset({"tech"})), seg)
    assert not is_interest_relevant(Targeting(), seg)  # broad = no uplift
