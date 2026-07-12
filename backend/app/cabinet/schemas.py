"""Request bodies for the cabinet API. USD floats at the edge (converted to micros in the
service layer); targeting/creative mirror the engine's Targeting / NativeCreative shapes."""
from typing import Literal

from pydantic import BaseModel, Field

Objective = Literal["awareness", "traffic", "engagement", "conversions"]
Pacing = Literal["even", "asap"]
Status = Literal["active", "paused", "draft"]


class TargetingIn(BaseModel):
    interests: list[str] = []
    geos: list[str] = []
    age_bands: list[str] = []
    genders: list[str] = []


class CreativeIn(BaseModel):
    title: str = Field(min_length=1)
    body: str = ""
    cta_text: str = "Learn more"
    brand_name: str = ""
    main_image_key: str = ""
    link_url: str = ""


class CampaignCreate(BaseModel):
    """Publish a campaign (creates the account link, campaign, ad set and ad atomically)."""
    name: str = Field(min_length=1)
    objective: Objective
    daily_budget_usd: float = Field(gt=0)
    bid_usd: float = Field(gt=0, description="CPM / CPC / target-CPA by objective")
    pacing: Pacing = "even"
    value_usd: float = Field(default=60.0, ge=0, description="baseline conversion value")
    targeting: TargetingIn = TargetingIn()
    creative: CreativeIn
    freq_cap_impressions: int | None = Field(default=None, ge=1)
    freq_cap_per_days: int = Field(default=1, ge=1)
    account_id: str | None = None  # defaults to the local account
    status: Status = "active"


class CampaignPatch(BaseModel):
    """Partial edit — only the fields present in the request are applied (exclude_unset)."""
    name: str | None = Field(default=None, min_length=1)
    status: Status | None = None
    daily_budget_usd: float | None = Field(default=None, gt=0)
    pacing: Pacing | None = None
    bid_usd: float | None = Field(default=None, gt=0)
    value_usd: float | None = Field(default=None, ge=0)
    targeting: TargetingIn | None = None
    creative: CreativeIn | None = None
    freq_cap_impressions: int | None = Field(default=None, ge=1)
    freq_cap_per_days: int | None = Field(default=None, ge=1)


class EstimateBody(BaseModel):
    objective: Objective
    daily_budget_usd: float = Field(gt=0)
    bid_usd: float = Field(gt=0)
    value_usd: float = Field(default=60.0, ge=0)
    targeting: TargetingIn = TargetingIn()
    freq_cap_impressions: int | None = Field(default=None, ge=1)
    freq_cap_per_days: int = Field(default=1, ge=1)


class AudienceBody(BaseModel):
    targeting: TargetingIn = TargetingIn()
