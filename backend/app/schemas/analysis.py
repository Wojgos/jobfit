"""Schemas shared by the LLM layer (structured output) and the API."""

from typing import Literal

from pydantic import BaseModel, Field

Importance = Literal["must", "nice"]
MatchStatus = Literal["met", "partial", "missing"]
SalaryUnit = Literal["hour", "day", "month", "year"]
Contract = Literal["b2b", "uop", "other", "unknown"]


class Requirement(BaseModel):
    name: str = Field(description="Short skill or requirement name, e.g. 'Django' or 'English B2'")
    category: Literal[
        "language", "framework", "database", "cloud", "tool", "practice", "soft_skill", "other"
    ] = "other"
    importance: Importance = "must"


class SalaryInfo(BaseModel):
    min: float | None = None
    max: float | None = None
    currency: str = "PLN"
    unit: SalaryUnit = "month"
    contract: Contract = "unknown"


class OfferExtraction(BaseModel):
    """What the LLM extracts from a pasted job offer."""

    title: str
    company: str | None = None
    seniority: Literal["intern", "junior", "mid", "senior", "unknown"] = "unknown"
    work_mode: Literal["remote", "hybrid", "onsite", "unknown"] = "unknown"
    requirements: list[Requirement] = Field(default_factory=list)
    salary: SalaryInfo | None = None


class RequirementMatch(BaseModel):
    name: str
    importance: Importance = "must"
    status: MatchStatus
    evidence: str = Field(default="", description="Short quote from the CV supporting the status")
    comment: str = ""


class MatchJudgement(BaseModel):
    """What the LLM returns after comparing requirements with CV evidence."""

    matches: list[RequirementMatch]
    summary: str = ""


class NormalizedSalary(BaseModel):
    monthly_min: int | None
    monthly_max: int | None
    currency: str
    contract: Contract
    basis: str = Field(description="How the monthly value was derived, e.g. '60/hour x 168 h'")
