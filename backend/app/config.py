"""App configuration, loaded from environment (mirrors Report/ua-simulator config)."""
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv(".env")

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

APP_DIR = Path(__file__).resolve().parent
# The synthetic world definition (segments, interests, market, economy).
WORLD_YAML = os.getenv("WORLD_YAML", str(APP_DIR / "adsim" / "world" / "world.yaml"))

# Environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT == "production"

# Database (SQLite + WAL; see database.py)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{DATA_DIR}/data.db")
DATABASE_URL_SYNC = os.getenv("DATABASE_URL_SYNC", f"sqlite:///{DATA_DIR}/data.db")

# Frontend URL (for CORS in local dev). In production the SPA is same-origin behind Caddy.
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# --- Auth (used from Phase 4) ------------------------------------------------
# Dev default; production MUST override or the app refuses to boot.
SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-change-me")
if IS_PRODUCTION and SECRET_KEY == "dev-insecure-change-me":
    raise RuntimeError("SECRET_KEY must be set in production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL_MIN = int(os.getenv("ACCESS_TOKEN_TTL_MIN", "30"))
REFRESH_TOKEN_TTL_DAYS = int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "30"))

# Send auth cookies with the Secure flag only over HTTPS. Defaults on in production
# (behind Caddy/Cloudflare) and off in local dev over plain HTTP.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true" if IS_PRODUCTION else "false").lower() == "true"

# Registration allowlist (comma-separated emails). Empty list = open (dev only).
ALLOWED_REGISTRATION_EMAILS = [
    e.strip().lower()
    for e in os.getenv("ALLOWED_REGISTRATION_EMAILS", "").split(",")
    if e.strip()
]
# Fail CLOSED in production: registration is invite-only, so an empty allowlist (a forgotten
# env var) would silently open sign-up to the world. Mirror the SECRET_KEY guard above.
if IS_PRODUCTION and not ALLOWED_REGISTRATION_EMAILS:
    raise RuntimeError(
        "ALLOWED_REGISTRATION_EMAILS must be set in production (registration is invite-only)"
    )

# --- Guest demo mode (Phase 5) -----------------------------------------------
# A one-click sandbox identity so the public case study can be explored without an invite.
# Guests are throwaway: a background reaper deletes each guest and everything they authored
# once it is older than the TTL, so the shared demo never accumulates junk. Registration
# stays invite-only; the guest path is intentionally separate and creates no email/password.
GUEST_DEMO_ENABLED = os.getenv("GUEST_DEMO_ENABLED", "true").lower() == "true"
# A guest older than this is reaped on the next sweep (default 3h — long enough for a session).
GUEST_TTL_SECONDS = int(os.getenv("GUEST_TTL_SECONDS", str(3 * 60 * 60)))
# How often the background reaper sweeps for expired guests (default 30 min).
GUEST_REAP_INTERVAL_SECONDS = int(os.getenv("GUEST_REAP_INTERVAL_SECONDS", str(30 * 60)))
