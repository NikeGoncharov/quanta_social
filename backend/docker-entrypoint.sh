#!/bin/sh
set -e

# Alembic owns the schema in production. --workers 1 is mandatory: the real-time
# simulation world loop is a single in-process asyncio task and must not be forked.
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
