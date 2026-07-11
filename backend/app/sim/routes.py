"""The sim + RTB-inspector API: world controls, the live delivery series, the SSE stream,
and the auction-sample inspector. Mounted at /sim (the SPA calls /api/sim/...).
"""
import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from .runtime import SimRuntime
from .schemas import ControlPatch, ReplayBody

router = APIRouter(prefix="/sim", tags=["sim"])


def get_runtime(request: Request) -> SimRuntime:
    rt = getattr(request.app.state, "runtime", None)
    if rt is None:
        raise HTTPException(status_code=503, detail="simulation runtime is not available")
    return rt


@router.get("/status")
async def sim_status(request: Request):
    return get_runtime(request).status()


@router.post("/control")
async def sim_control(patch: ControlPatch, request: Request):
    rt = get_runtime(request)
    return await rt.apply_control(**patch.model_dump(exclude_none=True))


@router.get("/delivery")
async def sim_delivery(request: Request, window: int = 180, campaign_id: str | None = None):
    rt = get_runtime(request)
    window = max(1, min(window, 1000))
    return {"points": await rt.delivery_series(window=window, campaign_id=campaign_id)}


@router.get("/rtb/samples")
async def rtb_samples(request: Request, limit: int = 40):
    rt = get_runtime(request)
    limit = max(1, min(limit, 200))
    return {"samples": await rt.list_samples(limit=limit)}


@router.get("/rtb/samples/{sample_id}")
async def rtb_sample(sample_id: int, request: Request):
    detail = await get_runtime(request).get_sample(sample_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="auction sample not found")
    return detail


@router.post("/rtb/replay")
async def rtb_replay(body: ReplayBody, request: Request):
    detail = await get_runtime(request).replay(ad_id=body.ad_id, segment_key=body.segment_key)
    if detail is None:
        raise HTTPException(status_code=400, detail="no active line/segment available to replay")
    return detail


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/stream")
async def sim_stream(request: Request):
    """Server-Sent Events: an initial snapshot, then live `delivery` and `status` events.
    Connecting counts as a viewer, which un-pauses the idle world loop."""
    rt = get_runtime(request)

    async def gen():
        # Subscribe INSIDE the generator: if the client aborts before Starlette primes the
        # body, gen() never runs, so subscribe() never runs either — no leaked viewer. When
        # it does run, the finally always unsubscribes.
        queue = rt.subscribe()
        try:
            yield _sse("snapshot", await rt.snapshot())
            while True:
                if await request.is_disconnected():
                    break
                try:
                    evt = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield _sse(evt["type"], evt["data"])
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"  # comment frame keeps the connection warm
        finally:
            rt.unsubscribe(queue)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # tell Caddy/nginx not to buffer the stream
        },
    )
