"""JWT-cookie authentication — ported from Report/app/auth.py, adapted to Quanta's
string user ids, public @handles, and module-level config.

A single identity spans the social app and the ad cabinet. Tokens are HS256 JWTs delivered
as httponly cookies (and echoed in the body); `get_current_user` reads either the
Authorization header or the cookie. Registration is optionally gated by an email allowlist.
"""
import json
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import (
    ACCESS_TOKEN_TTL_MIN,
    ALLOWED_REGISTRATION_EMAILS,
    COOKIE_SECURE,
    JWT_ALGORITHM,
    REFRESH_TOKEN_TTL_DAYS,
    SECRET_KEY,
)
from app.database import get_db
from app.models import Profile, User

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# A throwaway hash to verify against when the email is unknown or passwordless, so every login
# pays the same bcrypt cost and response latency can't reveal whether an account exists.
_DUMMY_HASH = pwd_context.hash("quanta-timing-equalizer")

ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"


# --- schemas -----------------------------------------------------------------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    handle: Optional[str] = None

    @field_validator("email")
    @classmethod
    def _norm_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def _norm_email(cls, v: str) -> str:
        return v.strip().lower()


class UserOut(BaseModel):
    id: str
    email: Optional[str]
    handle: str
    created_at: float


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# --- password + token helpers ------------------------------------------------
def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def _create_token(sub: str, *, kind: str, expires: timedelta) -> str:
    payload = {"sub": sub, "type": kind, "exp": datetime.now(timezone.utc) + expires}
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_access_token(sub: str) -> str:
    return _create_token(sub, kind="access", expires=timedelta(minutes=ACCESS_TOKEN_TTL_MIN))


def create_refresh_token(sub: str) -> str:
    return _create_token(sub, kind="refresh", expires=timedelta(days=REFRESH_TOKEN_TTL_DAYS))


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None


def set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    response.set_cookie(
        ACCESS_TOKEN_COOKIE, access, httponly=True, secure=COOKIE_SECURE, samesite="lax",
        max_age=ACCESS_TOKEN_TTL_MIN * 60, path="/",
    )
    response.set_cookie(
        REFRESH_TOKEN_COOKIE, refresh, httponly=True, secure=COOKIE_SECURE, samesite="lax",
        max_age=REFRESH_TOKEN_TTL_DAYS * 24 * 60 * 60, path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/")
    response.delete_cookie(REFRESH_TOKEN_COOKIE, path="/")


# --- current-user dependency -------------------------------------------------
async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the Authorization header or the access cookie."""
    token = credentials.credentials if credentials else request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    user = await db.get(User, sub)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


# --- handle helpers ----------------------------------------------------------
def _slugify_handle(raw: str) -> str:
    base = re.sub(r"[^a-z0-9_]", "", (raw or "").lower())
    return base[:20] or "user"


async def _unique_handle(db: AsyncSession, base: str) -> str:
    base = _slugify_handle(base)
    candidate = base
    for _ in range(50):
        exists = (await db.execute(select(User.id).where(User.handle == candidate))).first()
        if exists is None:
            return candidate
        candidate = f"{base}{uuid4().hex[:4]}"
    return f"{base}{uuid4().hex[:8]}"


# --- endpoints ---------------------------------------------------------------
@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterIn, response: Response, db: AsyncSession = Depends(get_db)):
    if ALLOWED_REGISTRATION_EMAILS and body.email not in ALLOWED_REGISTRATION_EMAILS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is invite-only right now. Ask an admin to add your email.",
        )
    exists = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    handle = await _unique_handle(db, body.handle or body.email.split("@")[0])
    now = time.time()
    user = User(
        id="usr-" + uuid4().hex[:8], email=body.email, handle=handle,
        password_hash=get_password_hash(body.password), is_synthetic=False, is_guest=False,
        created_at=now,
    )
    db.add(user)
    db.add(Profile(
        user_id=user.id, display_name=handle, avatar_seed=user.id, bio="",
        interests_json="[]", geo="", age_band="", gender="",
    ))
    await db.commit()

    access, refresh = create_access_token(user.id), create_refresh_token(user.id)
    set_auth_cookies(response, access, refresh)
    return UserOut(id=user.id, email=user.email, handle=user.handle, created_at=user.created_at)


@router.post("/login", response_model=Token)
async def login(body: LoginIn, response: Response, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    # Always run a bcrypt verify (against a dummy hash when the account is missing/passwordless)
    # so the response time doesn't leak whether the email is registered.
    stored = user.password_hash if user and user.password_hash else _DUMMY_HASH
    password_ok = verify_password(body.password, stored)
    if user is None or not user.password_hash or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password",
        )
    access, refresh = create_access_token(user.id), create_refresh_token(user.id)
    set_auth_cookies(response, access, refresh)
    return Token(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=Token)
async def refresh_tokens(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token required")
    payload = decode_token(token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token",
        )
    sub = payload.get("sub")
    user = await db.get(User, sub) if sub else None
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    access, refresh = create_access_token(user.id), create_refresh_token(user.id)
    set_auth_cookies(response, access, refresh)
    return Token(access_token=access, refresh_token=refresh)


@router.post("/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"status": "ok"}


@router.get("/me")
async def me(current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    profile = await db.get(Profile, current.id)
    interests = json.loads(profile.interests_json) if profile else []
    return {
        "id": current.id,
        "email": current.email,
        "handle": current.handle,
        "display_name": (profile.display_name if profile else current.handle) or current.handle,
        "avatar_seed": (profile.avatar_seed if profile else current.id) or current.id,
        "bio": profile.bio if profile else "",
        "interests": interests,
        "geo": profile.geo if profile else "",
        "age_band": profile.age_band if profile else "",
        "gender": profile.gender if profile else "",
        "is_synthetic": current.is_synthetic,
    }
