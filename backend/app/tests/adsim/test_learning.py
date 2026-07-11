from app.adsim.simulation.learning import in_learning, learning_lift, signal_to_exit
from app.adsim.world.schema import Learning

L = Learning(start_lift=0.6, target_lift=1.5, threshold=50, noise=0.0)


def test_lift_ramps_from_start_to_target():
    assert learning_lift(0, L) == 0.6
    assert learning_lift(50, L) == 1.5
    assert abs(learning_lift(25, L) - (0.6 + (1.5 - 0.6) * 0.5)) < 1e-9


def test_lift_is_monotonic_in_signal():
    xs = [learning_lift(s, L) for s in range(0, 60, 5)]
    assert all(b >= a for a, b in zip(xs, xs[1:]))


def test_in_learning_and_signal_to_exit():
    assert in_learning(10, L)
    assert not in_learning(50, L)
    assert signal_to_exit(10, L) == 40
    assert signal_to_exit(80, L) == 0
