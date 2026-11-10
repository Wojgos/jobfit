from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.api.deps import LLMDep, SessionDep, forbid_in_demo
from app.schemas.api import CvOut, CvTextIn
from app.services.cv_service import (
    EmptyCvError,
    count_chunks,
    extract_text,
    ingest_cv,
    latest_cv,
)

router = APIRouter(prefix="/api/cv", tags=["cv"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


async def _store(session: SessionDep, llm: LLMDep, filename: str, text: str) -> CvOut:
    try:
        document, chunks = await ingest_cv(session, llm, filename=filename, text=text)
    except EmptyCvError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return CvOut(
        id=document.id, filename=document.filename, chunks=chunks, created_at=document.created_at
    )


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(forbid_in_demo)])
async def upload_cv(file: UploadFile, session: SessionDep, llm: LLMDep) -> CvOut:
    """Upload a CV as PDF or plain text. The newest CV is used for matching."""
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "The file is larger than 5 MB")
    filename = file.filename or "cv"
    try:
        text = extract_text(filename, data)
    except Exception as exc:  # pypdf raises many different errors for broken files
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Could not read the file"
        ) from exc
    return await _store(session, llm, filename, text)


@router.post("/text", status_code=status.HTTP_201_CREATED, dependencies=[Depends(forbid_in_demo)])
async def upload_cv_text(body: CvTextIn, session: SessionDep, llm: LLMDep) -> CvOut:
    return await _store(session, llm, body.filename, body.text)


@router.get("")
async def get_current_cv(session: SessionDep) -> CvOut:
    document = await latest_cv(session)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No CV uploaded yet")
    return CvOut(
        id=document.id,
        filename=document.filename,
        chunks=await count_chunks(session, document.id),
        created_at=document.created_at,
    )
