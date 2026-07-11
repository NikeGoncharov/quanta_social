from app.adsim.metrics.diagnostics import diagnose
from app.adsim.money import usd_to_micros


def _kw(**over):
    base = dict(
        win_rate=0.5,
        audience_size=1_000_000,
        spent_today_micros=usd_to_micros(10),
        daily_budget_micros=usd_to_micros(100),
        freq_saturation=0.0,
        in_learning=False,
    )
    base.update(over)
    return base


def test_narrow_audience_wins_priority():
    assert diagnose(**_kw(audience_size=1_000)).limiter == "audience"


def test_budget_limited():
    d = diagnose(**_kw(spent_today_micros=usd_to_micros(100)))
    assert d.limiter == "budget" and not d.delivering


def test_frequency_capped():
    assert diagnose(**_kw(freq_saturation=0.95)).limiter == "frequency"


def test_bid_too_low():
    assert diagnose(**_kw(win_rate=0.05)).limiter == "bid"


def test_learning_is_delivering_but_flagged():
    d = diagnose(**_kw(in_learning=True, signal_to_exit=20))
    assert d.limiter == "learning" and d.delivering


def test_healthy_delivery_has_no_limiter():
    d = diagnose(**_kw())
    assert d.limiter is None and d.delivering
