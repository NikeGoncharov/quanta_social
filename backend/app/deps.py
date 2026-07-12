"""Shared FastAPI dependencies."""
from app.auth import get_current_user  # noqa: F401
from app.database import get_db  # noqa: F401
