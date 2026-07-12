"""Quanta backend: FastAPI app.

Lifespan creates tables and (from Phase 2) seeds the world and starts the single
real-time simulation loop. Routers are mounted per domain as phases land.
"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import FRONTEND_URL
from app.database import async_session_maker, init_db
from app.adsim.world import load_world
from app.sim.runtime import SimRuntime
from app.sim.line_builder import load_lines
from app.sim.seed import ensure_seed_campaigns
from app.sim import routes as sim_routes
from app.cabinet import router as cabinet_router

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("quanta")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Seed the canonical campaign roster into the DB (once), then start the single real-time
    # world loop reading its lines from the DB — so campaigns created in the cabinet join the
    # live auction. The loop is viewer-gated, staying idle until the cabinet opens an SSE
    # stream. Line reloads happen inside the loop whenever a cabinet edit requests one.
    async with async_session_maker() as s:
        await ensure_seed_campaigns(s)
        await s.commit()
    world = load_world()
    runtime = SimRuntime(world, load_lines=load_lines)
    app.state.runtime = runtime
    await runtime.start()
    log.info("Quanta backend started; world loop running (DB-backed campaigns)")
    try:
        yield
    finally:
        await runtime.stop()
        log.info("Quanta backend stopped; world loop halted")


app = FastAPI(
    title="Quanta API",
    description="Quanta Social — a mock social network with a glass-box programmatic ad cabinet.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://localhost:5175", "http://localhost:3000", FRONTEND_URL,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers are mounted here as phases land:
#   auth · social(profiles/posts/messages) · cabinet(...) · sim(control/inspector/demo) · stream
app.include_router(sim_routes.router)
app.include_router(cabinet_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "quanta"}
