"""Quanta backend: FastAPI app.

Lifespan creates tables and (from Phase 2) seeds the world and starts the single
real-time simulation loop. Routers are mounted per domain as phases land.
"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import FRONTEND_URL
from app.database import init_db
from app.adsim.world import load_world
from app.sim.runtime import SimRuntime
from app.sim.seed import seed_lines
from app.sim import routes as sim_routes

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("quanta")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Build the world + seed campaigns, then start the single real-time world loop. The
    # loop is viewer-gated, so it stays idle until the cabinet opens an SSE stream.
    world = load_world()
    runtime = SimRuntime(world, seed_lines())
    app.state.runtime = runtime
    await runtime.start()
    log.info("Quanta backend started; world loop running")
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


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "quanta"}
