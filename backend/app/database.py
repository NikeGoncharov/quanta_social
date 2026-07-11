"""Async SQLAlchemy engine + session (mirrors ua-simulator/Report database.py).

SQLite under concurrent access needs these PRAGMAs or a long write holds the
writer-lock and any parallel write fails immediately with "database is locked":
 - journal_mode=WAL: readers don't block the writer (persistent DB-file setting);
 - busy_timeout=30000: wait up to 30s for a lock instead of erroring instantly;
 - foreign_keys=ON: SQLite otherwise ignores foreign keys (per-connection).

The single background simulation writer + request-path readers make WAL essential.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine, event

from .config import DATABASE_URL, DATABASE_URL_SYNC

_SQLITE_TIMEOUT_S = 30


def _apply_sqlite_pragmas(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


# Async engine for FastAPI + the world loop
async_engine = create_async_engine(
    DATABASE_URL, echo=False, connect_args={"timeout": _SQLITE_TIMEOUT_S}
)
async_session_maker = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

# Sync engine for Alembic migrations
sync_engine = create_engine(
    DATABASE_URL_SYNC, echo=False, connect_args={"timeout": _SQLITE_TIMEOUT_S}
)

# Apply PRAGMAs on every new connection of both engines. For async we listen on the
# sync_engine wrapper — the SQLAlchemy-recommended way to configure aiosqlite.
event.listen(async_engine.sync_engine, "connect", _apply_sqlite_pragmas)
event.listen(sync_engine, "connect", _apply_sqlite_pragmas)

Base = declarative_base()


async def get_db() -> AsyncSession:
    """FastAPI dependency: yield an async database session."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create all tables (dev convenience; Alembic owns schema in production)."""
    import app.models  # noqa: F401  ensure every model is registered on Base.metadata

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
