"""Shared FastAPI dependencies."""
from app.database import get_db  # noqa: F401

# get_current_user is added in Phase 4 (auth), ported from Report/app/auth.py.
