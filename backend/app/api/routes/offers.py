import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.agent.loop import run_agent
from app.agent.tools import AgentContext
from app.api.deps import LLMDep, SessionDep, forbid_in_demo
from app.api.rate_limit import llm_rate_limit
from app.core.config import get_settings
from app.db.models import JobOffer
from app.schemas.analysis import NormalizedSalary, OfferExtraction, RequirementMatch
from app.schemas.api import (
    AnalysisOut,
    AskIn,
    AskOut,
    CoverLetterIn,
    CoverLetterOut,
    OfferDetail,
    OfferIn,
    OfferSummary,
)
from app.services.analysis_service import NoCvError, analyze_offer
from app.services.cover_letter import write_cover_letter

router = APIRouter(prefix="/api/offers", tags=["offers"])


def _summary(offer: JobOffer) -> OfferSummary:
    return OfferSummary(
        id=offer.id,
        title=offer.title,
        company=offer.company,
        score=offer.analysis.score if offer.analysis else None,
        status=offer.application.status if offer.application else None,
        created_at=offer.created_at,
    )


def _detail(offer: JobOffer) -> OfferDetail:
    analysis = offer.analysis
    return OfferDetail(
        **_summary(offer).model_dump(),
        source_url=offer.source_url,
        raw_text=offer.raw_text,
        application_id=offer.application.id if offer.application else None,
        analysis=AnalysisOut(
            score=analysis.score,
            summary=analysis.summary,
            extraction=OfferExtraction.model_validate(analysis.extraction),
            matches=[RequirementMatch.model_validate(m) for m in analysis.matches],
            salary=NormalizedSalary.model_validate(analysis.salary) if analysis.salary else None,
        )
        if analysis
        else None,
    )


async def _get_offer(session: SessionDep, offer_id: uuid.UUID) -> JobOffer:
    offer = await session.scalar(
        select(JobOffer)
        .where(JobOffer.id == offer_id)
        .options(selectinload(JobOffer.analysis), selectinload(JobOffer.application))
        .execution_options(populate_existing=True)
    )
    if offer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Offer not found")
    return offer


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(llm_rate_limit)])
async def create_offer(body: OfferIn, session: SessionDep, llm: LLMDep) -> OfferDetail:
    """Analyse a pasted job offer against the current CV and add it to the board."""
    try:
        offer = await analyze_offer(
            session, llm, raw_text=body.raw_text, source_url=body.source_url
        )
    except NoCvError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return _detail(await _get_offer(session, offer.id))


@router.get("")
async def list_offers(session: SessionDep) -> list[OfferSummary]:
    offers = await session.scalars(
        select(JobOffer)
        .options(selectinload(JobOffer.analysis), selectinload(JobOffer.application))
        .order_by(JobOffer.created_at.desc())
    )
    return [_summary(o) for o in offers]


@router.get("/{offer_id}")
async def get_offer(offer_id: uuid.UUID, session: SessionDep) -> OfferDetail:
    return _detail(await _get_offer(session, offer_id))


@router.delete(
    "/{offer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(forbid_in_demo)],
)
async def delete_offer(offer_id: uuid.UUID, session: SessionDep) -> None:
    await session.delete(await _get_offer(session, offer_id))
    await session.commit()


@router.post("/{offer_id}/cover-letter", dependencies=[Depends(llm_rate_limit)])
async def cover_letter(
    offer_id: uuid.UUID, body: CoverLetterIn, session: SessionDep, llm: LLMDep
) -> CoverLetterOut:
    offer = await _get_offer(session, offer_id)
    return CoverLetterOut(text=await write_cover_letter(llm, offer, body.language))


@router.post("/{offer_id}/ask", dependencies=[Depends(llm_rate_limit)])
async def ask(offer_id: uuid.UUID, body: AskIn, session: SessionDep, llm: LLMDep) -> AskOut:
    """Ask the assistant about this offer; it can search the CV and read the analysis."""
    offer = await _get_offer(session, offer_id)
    ctx = AgentContext(
        session=session,
        llm=llm,
        offer=offer,
        cv_document_id=offer.analysis.cv_document_id if offer.analysis else None,
    )
    return await run_agent(llm, ctx, body.question, get_settings().agent_max_steps)
