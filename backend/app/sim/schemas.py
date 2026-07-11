"""Request bodies for the sim/inspector API. Responses are plain dicts the runtime builds
(already USD-normalized), so they don't need response models here."""
from pydantic import BaseModel, Field


class ControlPatch(BaseModel):
    """Partial update to the world controls — omit a field to leave it unchanged."""
    running: bool | None = None
    speed: float | None = Field(default=None, gt=0, description="sim-seconds per real second")
    tick_hz: float | None = Field(default=None, gt=0)
    market_density: float | None = Field(default=None, ge=0)


class ReplayBody(BaseModel):
    """Run a fresh auction on demand. Omit both to sample a random active line/segment."""
    ad_id: str | None = None
    segment_key: str | None = None
