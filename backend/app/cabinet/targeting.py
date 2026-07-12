"""Targeting catalog + live audience sizing (the wizard/editor's audience gauge). Reads the
world through the runtime so the catalog and the sizing always match the running simulation.
"""
from fastapi import APIRouter, Request

from ..adsim.dsp.campaign import Targeting
from ..adsim.dsp.targeting import audience_size, matching_segments
from ..sim.routes import get_runtime
from .schemas import AudienceBody

router = APIRouter(prefix="/cabinet/targeting", tags=["cabinet"])


@router.get("/options")
async def targeting_options(request: Request):
    """The dimensions an advertiser can target — straight from the world definition."""
    world = get_runtime(request).world
    return {
        "interests": list(world.interests),
        "geos": list(world.geos),
        "age_bands": list(world.age_bands),
        "genders": list(world.genders),
        "population": world.population,
    }


@router.post("/audience")
async def audience(body: AudienceBody, request: Request):
    """Estimated reach for a targeting spec — the number that animates the audience gauge."""
    world = get_runtime(request).world
    t = Targeting.from_dict(body.targeting.model_dump())
    size = audience_size(t, world)
    return {
        "audience": size,
        "segments": len(matching_segments(t, world)),
        "population": world.population,
        "reach_pct": round(size / world.population, 4) if world.population else 0.0,
    }
