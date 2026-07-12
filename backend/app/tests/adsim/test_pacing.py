from app.adsim.dsp.pacing import freq_remaining_impressions, pace_allowed_spend_micros
from app.adsim.dsp.campaign import FreqCap
from app.adsim.models.enums import Pacing
from app.adsim.money import usd_to_micros
from app.adsim.world.schema import Segment

from ._factories import make_line


def _seg(size=1000):
    return Segment("s", "tech", "USA", "25-34", "F", size, 1.0, 0.01, 0.03, 1.0, usd_to_micros(5))


def test_even_pacing_tracks_day_fraction():
    line = make_line(budget_usd=100, pacing=Pacing.EVEN)
    assert pace_allowed_spend_micros(line, 0, 0.5) == usd_to_micros(50)


def test_even_pacing_blocks_when_ahead_of_schedule():
    line = make_line(budget_usd=100, pacing=Pacing.EVEN)
    # already spent $60 at 50% of the day: the even target is $50 -> nothing allowed now.
    assert pace_allowed_spend_micros(line, usd_to_micros(60), 0.5) == 0


def test_asap_headstart_caps_the_first_tick():
    line = make_line(budget_usd=100, pacing=Pacing.ASAP)
    # Right at the midnight reset (day_fraction 0, nothing spent) ASAP delivers only the
    # 5% headstart, not the whole budget — this is what tames the once-a-day chart spike.
    assert pace_allowed_spend_micros(line, 0, 0.0) == usd_to_micros(5)


def test_asap_front_loads_but_is_bounded():
    line = make_line(budget_usd=100, pacing=Pacing.ASAP)
    even = make_line(budget_usd=100, pacing=Pacing.EVEN)
    # Early in the day ASAP runs well ahead of even pace but does NOT dump everything:
    # frac = 0.05 + 0.1*4 = 0.45 -> target $45, minus $30 already spent = $15 allowed.
    assert pace_allowed_spend_micros(line, usd_to_micros(30), 0.1) == usd_to_micros(15)
    assert pace_allowed_spend_micros(line, 0, 0.1) > pace_allowed_spend_micros(even, 0, 0.1)


def test_asap_finishes_early():
    line = make_line(budget_usd=100, pacing=Pacing.ASAP)
    # By ~1/4 of the day the front-loaded target reaches the full budget: all remaining allowed.
    assert pace_allowed_spend_micros(line, usd_to_micros(30), 0.25) == usd_to_micros(70)


def test_freq_cap_remaining():
    line = make_line(freq_cap=FreqCap(impressions=2, per_days=1))
    seg = _seg(size=1000)
    assert freq_remaining_impressions(line, seg, shown_today=0) == 2000
    assert freq_remaining_impressions(line, seg, shown_today=1500) == 500


def test_no_freq_cap_is_unbounded():
    line = make_line(freq_cap=None)
    assert freq_remaining_impressions(line, _seg(), shown_today=10_000) == float("inf")
