"""Shared test fixtures.

`client` is the plain ASGI client (no world loop). The sim fixtures below bind the runtime
to a throwaway temp database and drive it by hand (step_once/flush) so tests are fully
deterministic — no wall clock, no background task.
"""
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def temp_session_maker(tmp_path):
    """An async sessionmaker over a fresh temp SQLite file with the full schema."""
    import app.models  # noqa: F401  register every table on Base.metadata
    from app.database import Base, _apply_sqlite_pragmas

    url = f"sqlite+aiosqlite:///{tmp_path / 'sim_test.db'}"
    engine = create_async_engine(url)
    event.listen(engine.sync_engine, "connect", _apply_sqlite_pragmas)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


@pytest_asyncio.fixture
async def sim_runtime(temp_session_maker):
    """A SimRuntime bound to the temp DB, controls initialized, loop NOT started."""
    from app.adsim.world import load_world
    from app.sim.runtime import SimRuntime
    from app.sim.seed import seed_lines

    rt = SimRuntime(load_world(), seed_lines(), session_maker=temp_session_maker)
    await rt._load_or_init_control()
    return rt


@pytest_asyncio.fixture
async def sim_client(sim_runtime):
    """A client with a hand-driven runtime attached to app.state, pre-populated with a few
    ticks of delivery + auction samples."""
    for _ in range(24):
        sim_runtime.step_once()
    await sim_runtime.flush(final=True)

    app.state.runtime = sim_runtime
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, sim_runtime
    finally:
        if getattr(app.state, "runtime", None) is sim_runtime:
            del app.state.runtime


@pytest_asyncio.fixture
async def db_runtime(temp_session_maker):
    """A DB-backed runtime (Phase 3): the seed roster is materialized into the temp DB and
    the runtime loads its lines from there via load_lines. Loop NOT started — driven by hand.
    """
    from app.adsim.world import load_world
    from app.sim.line_builder import load_lines
    from app.sim.runtime import SimRuntime
    from app.sim.seed import ensure_seed_campaigns

    async with temp_session_maker() as s:
        await ensure_seed_campaigns(s)
        await s.commit()
    rt = SimRuntime(load_world(), load_lines=load_lines, session_maker=temp_session_maker)
    await rt._load_or_init_control()
    return rt


@pytest_asyncio.fixture
async def cabinet_client(db_runtime, temp_session_maker):
    """A client for the cabinet API: the runtime and the request-path get_db both bind the
    SAME temp DB (so a campaign created via the API is seen by the loop and by reporting).
    Pre-stepped so there is delivery to report on."""
    from app.database import get_db

    for _ in range(24):
        db_runtime.step_once()
    await db_runtime.flush(final=True)

    async def _override_get_db():
        async with temp_session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = _override_get_db
    app.state.runtime = db_runtime
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, db_runtime
    finally:
        app.dependency_overrides.pop(get_db, None)
        if getattr(app.state, "runtime", None) is db_runtime:
            del app.state.runtime
