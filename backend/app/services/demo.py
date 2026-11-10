"""Sample data for the public demo. Everything here is fictional."""

import logging

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.db.models import Application, ApplicationStatus, CvDocument
from app.llm.base import LLMClient
from app.services.analysis_service import analyze_offer
from app.services.cv_service import ingest_cv

logger = logging.getLogger(__name__)

DEMO_CV = """Alex Nowak - Junior Python Developer (sample CV)

Experience
Intern - Python / React Native Developer (05.2025 - 07.2025). Built CRUD endpoints in a Python
REST API and the matching React Native screens, including a QR code management module.

Projects
Online store (BSc thesis): Django, Django REST Framework, PostgreSQL, Celery and Redis for
background jobs, Elasticsearch search, Angular 18 front end, Docker Compose, 200+ pytest tests.

Real-time trading dashboard: FastAPI, SQLAlchemy, WebSocket price stream, Angular with RxJS
and signals, CI on GitHub Actions.

Retail analytics: PostgreSQL with CTEs, window functions and triggers, REST API in Spring Boot.

Skills: Python, Django, FastAPI, Angular, TypeScript, PostgreSQL, Docker, Git, pytest, LangChain.
Languages: Polish (native), English C1."""

DEMO_OFFERS: list[tuple[str, ApplicationStatus]] = [
    (
        """Junior Python Developer
Company: Northwind Software (sample)

Remote, B2B. Rate: 40 - 60 PLN/h

Requirements:
- Python, Django, Django REST Framework
- PostgreSQL and SQL
- Docker, Git
- English B2

Nice to have:
- Celery, Redis
- Google Cloud""",
        ApplicationStatus.APPLIED,
    ),
    (
        """Junior Fullstack Developer (Angular + Python)
Company: Brightpath Labs (sample)

Hybrid work in Bialystok. Salary 8000 - 11000 PLN / month, employment contract.

What we expect:
- TypeScript and Angular with RxJS
- Python with FastAPI
- REST API design
- Unit testing

Nice to have:
- NgRx
- Playwright""",
        ApplicationStatus.INTERVIEW,
    ),
    (
        """Junior Software AI Engineer
Company: Cloudline (sample)

Remote. We build agents and LLM-based tools for enterprise clients.

Requirements:
- Python
- LLM APIs and RAG
- Azure
- Kubernetes

Nice to have:
- LangChain
- Terraform""",
        ApplicationStatus.TO_APPLY,
    ),
]


async def reset_demo(session: AsyncSession, llm: LLMClient) -> int:
    """Wipe all data and load the sample CV and offers. Returns the number of offers."""
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    await session.execute(text(f"TRUNCATE {tables} CASCADE"))
    await session.commit()

    await ingest_cv(session, llm, filename="sample-cv.txt", text=DEMO_CV)
    for raw_text, status in DEMO_OFFERS:
        offer = await analyze_offer(session, llm, raw_text=raw_text, source_url=None)
        application = await session.scalar(
            select(Application).where(Application.offer_id == offer.id)
        )
        if application is not None:
            application.status = status
    await session.commit()
    return len(DEMO_OFFERS)


async def seed_if_empty(session: AsyncSession, llm: LLMClient) -> None:
    """Called on start-up in demo mode; never blocks the app from starting."""
    try:
        if await session.scalar(select(CvDocument.id).limit(1)) is None:
            count = await reset_demo(session, llm)
            logger.info("Demo data seeded with %d offers", count)
    except Exception:
        logger.exception("Seeding demo data failed")
        await session.rollback()
