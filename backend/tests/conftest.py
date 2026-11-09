import os

# Configure before the app (and its cached settings) is imported.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://jobfit:jobfit@localhost:5433/jobfit_test"
)
os.environ["LLM_PROVIDER"] = "fake"

from collections.abc import AsyncIterator  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import models  # noqa: E402,F401
from app.db.base import Base  # noqa: E402
from app.db.session import get_engine  # noqa: E402
from app.main import app  # noqa: E402

CV_TEXT = """Jan Kowalski - Junior Python Developer

Experience
Intern - Python / React Native Developer at Example Soft (05.2025 - 07.2025).
Built CRUD endpoints in a Python REST API and the matching React Native screens.

Projects
Online store (BSc thesis): Django, Django REST Framework, PostgreSQL, Celery and Redis
for background jobs, Angular 18 front end, Docker Compose, more than 200 pytest tests.

Trading dashboard: FastAPI, SQLAlchemy, WebSocket price stream, Angular with RxJS,
CI pipeline on GitHub Actions.

Skills: Python, Django, FastAPI, Angular, TypeScript, PostgreSQL, Docker, Git.
Languages: Polish (native), English C1."""

OFFER_TEXT = """Junior Python Developer
Company: Example Fintech

We are looking for a junior developer to join our backend team. Remote work, B2B contract.
Salary: 40 - 60 PLN/h netto + VAT (B2B)

Requirements:
- Python and Django
- PostgreSQL and SQL
- Docker
- English B2

Nice to have:
- Kubernetes
- AWS
"""


@pytest.fixture(scope="session", autouse=True)
async def database() -> AsyncIterator[None]:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_tables() -> None:
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with get_engine().begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} CASCADE"))


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def cv(client: httpx.AsyncClient) -> dict[str, object]:
    response = await client.post("/api/cv/text", json={"text": CV_TEXT, "filename": "cv.txt"})
    assert response.status_code == 201
    data: dict[str, object] = response.json()
    return data
