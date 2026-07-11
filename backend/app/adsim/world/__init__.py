"""The synthetic world: segments (interest x geo x demo), the phantom market, the economy,
and the learning/fatigue parameters. Authored in world.yaml, loaded into typed objects."""
from .loader import load_world
from .schema import (
    Economy,
    Fatigue,
    Learning,
    PhantomSeat,
    Segment,
    World,
)

__all__ = [
    "load_world",
    "World",
    "Segment",
    "Economy",
    "Learning",
    "Fatigue",
    "PhantomSeat",
]
