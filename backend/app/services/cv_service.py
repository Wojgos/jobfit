import io
import uuid

from pypdf import PdfReader
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CvChunk, CvDocument
from app.llm.base import LLMClient
from app.services.chunking import chunk_text


class EmptyCvError(ValueError):
    pass


def extract_text(filename: str, data: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()
    return data.decode("utf-8", errors="replace").strip()


async def ingest_cv(
    session: AsyncSession, llm: LLMClient, *, filename: str, text: str
) -> tuple[CvDocument, int]:
    chunks = chunk_text(text)
    if not chunks:
        raise EmptyCvError("The CV does not contain any text")
    vectors = await llm.embed(chunks, task="document")
    document = CvDocument(
        filename=filename,
        content=text,
        chunks=[
            CvChunk(position=i, text=chunk, embedding=vector)
            for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
        ],
    )
    session.add(document)
    await session.commit()
    return document, len(chunks)


async def latest_cv(session: AsyncSession) -> CvDocument | None:
    result = await session.execute(
        select(CvDocument).order_by(CvDocument.created_at.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def count_chunks(session: AsyncSession, document_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count()).select_from(CvChunk).where(CvChunk.document_id == document_id)
    )
    return int(result.scalar_one())


async def search_cv(
    session: AsyncSession, document_id: uuid.UUID, vector: list[float], limit: int = 3
) -> list[tuple[str, float]]:
    """Return the CV chunks closest to ``vector`` as (text, cosine similarity) pairs."""
    distance = CvChunk.embedding.cosine_distance(vector).label("distance")
    result = await session.execute(
        select(CvChunk.text, distance)
        .where(CvChunk.document_id == document_id)
        .order_by(distance)
        .limit(limit)
    )
    return [(text, round(1 - float(dist), 3)) for text, dist in result.all()]
