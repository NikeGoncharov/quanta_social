"""The learning phase (Conversions / Engagement objectives).

A fresh optimized campaign delivers weakly and noisily; as it accumulates signal (realized
conversions/engagements) toward `threshold`, its effectiveness ramps from start_lift up to
target_lift. Below threshold the campaign is "in learning" — surfaced in the cabinet with
an explicit "N more conversions to exit learning" badge.
"""
from ..mathx import clamp


def learning_lift(signal: float, learning, rng=None) -> float:
    """Multiplier on CVR (and thus on the conversions-objective bid) from optimization."""
    conf = clamp(signal / learning.threshold, 0.0, 1.0) if learning.threshold > 0 else 1.0
    lift = learning.start_lift + (learning.target_lift - learning.start_lift) * conf
    if conf < 1.0 and rng is not None:
        lift *= 1.0 + rng.uniform(-learning.noise, learning.noise) * (1.0 - conf)
    return max(0.0, lift)


def in_learning(signal: float, learning) -> bool:
    return signal < learning.threshold


def signal_to_exit(signal: float, learning) -> float:
    """How much more signal is needed to exit the learning phase (>= 0)."""
    return max(0.0, learning.threshold - signal)
