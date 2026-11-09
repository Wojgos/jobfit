import enum
import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import EMBEDDING_DIM
from app.db.base import Base


class CvDocument(Base):
    __tablename__ = "cv_documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chunks: Mapped[list["CvChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="CvChunk.position"
    )


class CvChunk(Base):
    __tablename__ = "cv_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cv_documents.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))

    document: Mapped[CvDocument] = relationship(back_populates="chunks")


class JobOffer(Base):
    __tablename__ = "job_offers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255))
    company: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    raw_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    analysis: Mapped["Analysis | None"] = relationship(
        back_populates="offer", cascade="all, delete-orphan", uselist=False
    )
    application: Mapped["Application | None"] = relationship(
        back_populates="offer", cascade="all, delete-orphan", uselist=False
    )


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    offer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_offers.id", ondelete="CASCADE"), unique=True
    )
    cv_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cv_documents.id", ondelete="SET NULL")
    )
    extraction: Mapped[dict[str, Any]] = mapped_column(JSONB)
    matches: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    salary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    score: Mapped[float] = mapped_column(Float)
    summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    offer: Mapped[JobOffer] = relationship(back_populates="analysis")


class ApplicationStatus(enum.StrEnum):
    TO_APPLY = "to_apply"
    APPLIED = "applied"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    offer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_offers.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(
            ApplicationStatus,
            name="application_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=ApplicationStatus.TO_APPLY,
    )
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    offer: Mapped[JobOffer] = relationship(back_populates="application")
