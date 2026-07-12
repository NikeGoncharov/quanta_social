"""Request bodies for the social API."""
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ProfilePatch(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None
    interests: Optional[list[str]] = None
    geo: Optional[str] = None
    age_band: Optional[str] = None
    gender: Optional[str] = None
    avatar_seed: Optional[str] = None


class PostCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    image_key: Optional[str] = None

    @field_validator("body")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Post body cannot be empty")
        return v


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=1000)

    @field_validator("body")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Comment cannot be empty")
        return v


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)

    @field_validator("body")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty")
        return v
