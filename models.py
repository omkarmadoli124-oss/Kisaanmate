import re
from typing import Literal
from pydantic import BaseModel, Field, field_validator

_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f<>]")
def clean(s):
    return _CTRL.sub("", s).strip() if isinstance(s, str) else s

class Profile(BaseModel):
    state: str = Field(min_length=2, max_length=60)
    district: str = Field(min_length=2, max_length=60)
    village: str = Field("", max_length=80)
    crop: str = Field(min_length=2, max_length=60)
    variety: str = Field("", max_length=60)
    growth_stage: str = Field("", max_length=60)
    sowing_date: str = Field("", max_length=10)
    irrigation: str = Field("", max_length=40)
    soil: str = Field("", max_length=40)
    farm_acres: float | None = Field(None, gt=0, le=10000)
    budget_inr: float = Field(ge=0, le=10_000_000)

    @field_validator("state", "district", "village", "crop", "variety", "growth_stage",
                     "sowing_date", "irrigation", "soil", mode="before")
    @classmethod
    def _c(cls, v):
        return clean(v)

class Problem(BaseModel):
    symptoms: str = Field("", max_length=1000)
    selected: list[str] = Field(default_factory=list, max_length=10)
    started: str = Field("", max_length=60)
    spread: str = Field("", max_length=60)

    @field_validator("symptoms", "started", "spread", mode="before")
    @classmethod
    def _c(cls, v):
        return clean(v)

    @field_validator("selected", mode="before")
    @classmethod
    def _s(cls, v):
        return [clean(x)[:40] for x in v] if isinstance(v, list) else v

class AssessRequest(BaseModel):
    profile: Profile
    problem: Problem
    language: Literal["en", "hi", "mr"] = "en"
    answers: dict[str, str] = Field(default_factory=dict)
    image_id: str = Field("", max_length=64, pattern=r"^[a-f0-9]*$")
    allow_demo_weather: bool = False
