import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import selectinload

from app.api.deps import SessionDep
from app.db.models import Application, JobOffer
from app.schemas.api import ApplicationOut, ApplicationPatch

router = APIRouter(prefix="/api/applications", tags=["applications"])


def _out(application: Application) -> ApplicationOut:
    offer = application.offer
    return ApplicationOut(
        id=application.id,
        offer_id=application.offer_id,
        title=offer.title,
        company=offer.company,
        score=offer.analysis.score if offer.analysis else None,
        status=application.status,
        notes=application.notes,
        updated_at=application.updated_at,
    )


def _query() -> Select[Application]:
    return select(Application).options(
        selectinload(Application.offer).selectinload(JobOffer.analysis)
    )


@router.get("")
async def list_applications(session: SessionDep) -> list[ApplicationOut]:
    """All tracked applications, most recently changed first; the UI groups them by status."""
    applications = await session.scalars(_query().order_by(Application.updated_at.desc()))
    return [_out(a) for a in applications]


@router.patch("/{application_id}")
async def update_application(
    application_id: uuid.UUID, body: ApplicationPatch, session: SessionDep
) -> ApplicationOut:
    application = await session.scalar(_query().where(Application.id == application_id))
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if body.status is not None:
        application.status = body.status
    if body.notes is not None:
        application.notes = body.notes
    await session.commit()
    await session.refresh(application, ["updated_at"])
    return _out(application)
