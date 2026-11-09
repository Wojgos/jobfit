import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import ApplicationStatus
from app.schemas.analysis import NormalizedSalary, OfferExtraction, RequirementMatch


class CvTextIn(BaseModel):
    text: str = Field(min_length=50)
    filename: str = "cv.txt"


class CvOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    chunks: int
    created_at: datetime


class OfferIn(BaseModel):
    raw_text: str = Field(min_length=80, max_length=30_000)
    source_url: str | None = Field(default=None, max_length=1000)


class AnalysisOut(BaseModel):
    score: float
    summary: str
    extraction: OfferExtraction
    matches: list[RequirementMatch]
    salary: NormalizedSalary | None


class OfferSummary(BaseModel):
    id: uuid.UUID
    title: str
    company: str | None
    score: float | None
    status: ApplicationStatus | None
    created_at: datetime


class OfferDetail(OfferSummary):
    source_url: str | None
    raw_text: str
    analysis: AnalysisOut | None
    application_id: uuid.UUID | None


class CoverLetterIn(BaseModel):
    language: Literal["pl", "en"] = "pl"


class CoverLetterOut(BaseModel):
    text: str


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class ToolTrace(BaseModel):
    tool: str
    args: dict[str, object]
    result_preview: str


class AskOut(BaseModel):
    answer: str
    steps: list[ToolTrace]


class ApplicationOut(BaseModel):
    id: uuid.UUID
    offer_id: uuid.UUID
    title: str
    company: str | None
    score: float | None
    status: ApplicationStatus
    notes: str
    updated_at: datetime


class ApplicationPatch(BaseModel):
    status: ApplicationStatus | None = None
    notes: str | None = Field(default=None, max_length=5000)
