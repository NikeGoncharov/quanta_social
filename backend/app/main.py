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

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("quanta")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Phase 2+: seed world.yaml, start the real-time simulation world loop here.
    log.info("Quanta backend started")
    yield
    # Phase 2+: stop the simulation world loop here.


app = FastAPI(
    title="Quanta API",
    description="Quanta Social — a mock social network with a glass-box programmatic ad cabinet.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers are mounted here as phases land:
#   auth · social(profiles/posts/messages) · cabinet(...) · sim(control/inspector/demo) · stream


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "quanta"}
