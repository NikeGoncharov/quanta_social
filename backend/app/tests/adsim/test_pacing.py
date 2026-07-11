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


def test_asap_pacing_uses_remaining_budget():
    line = make_line(budget_usd=100, pacing=Pacing.ASAP)
    assert pace_allowed_spend_micros(line, usd_to_micros(30), 0.1) == usd_to_micros(70)


def test_freq_cap_remaining():
    line = make_line(freq_cap=FreqCap(impressions=2, per_days=1))
    seg = _seg(size=1000)
    assert freq_remaining_impressions(line, seg, shown_today=0) == 2000
    assert freq_remaining_impressions(line, seg, shown_today=1500) == 500


def test_no_freq_cap_is_unbounded():
    line = make_line(freq_cap=None)
    assert freq_remaining_impressions(line, _seg(), shown_today=10_000) == float("inf")
