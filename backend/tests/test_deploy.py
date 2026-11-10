"""Features needed by the public Cloud Run deployment: demo mode, rate limit, static files."""

from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from app.api.rate_limit import RateLimiter, limiter
from app.core.config import Settings, get_settings, normalize_database_url
from app.main import create_app
from app.services.demo import DEMO_OFFERS
from tests.conftest import OFFER_TEXT


@pytest.fixture
def settings() -> Iterator[Settings]:
    """The cached settings object, restored after the test."""
    current = get_settings()
    snapshot = current.model_copy()
    yield current
    for field in Settings.model_fields:
        setattr(current, field, getattr(snapshot, field))
    limiter.reset()


class TestDatabaseUrl:
    def test_neon_url_is_adapted_for_asyncpg(self) -> None:
        url = "postgresql://u:p@ep-x.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
        assert normalize_database_url(url) == (
            "postgresql+asyncpg://u:p@ep-x.eu-central-1.aws.neon.tech/neondb?ssl=require"
        )

    def test_secrets_pasted_with_a_trailing_newline_are_trimmed(self) -> None:
        settings = Settings(database_url="postgresql://u:p@h/db\n", admin_token=" token\n")
        assert settings.database_url == "postgresql+asyncpg://u:p@h/db"
        assert settings.admin_token == "token"

    def test_asyncpg_url_is_left_alone(self) -> None:
        url = "postgresql+asyncpg://jobfit:jobfit@localhost:5433/jobfit"
        assert normalize_database_url(url) == url


class TestRateLimiter:
    def test_blocks_after_the_limit_and_recovers_after_the_window(self) -> None:
        rl = RateLimiter(limit=2, window_seconds=60)
        assert rl.hit("ip", now=0) is None
        assert rl.hit("ip", now=10) is None
        assert rl.hit("ip", now=20) == pytest.approx(40)
        assert rl.hit("other", now=20) is None
        assert rl.hit("ip", now=61) is None

    async def test_api_returns_429_with_retry_after(
        self, client: httpx.AsyncClient, cv: dict[str, object]
    ) -> None:
        limiter.reset()
        limiter.limit = 1
        try:
            headers = {"X-Forwarded-For": "1.2.3.4, 9.9.9.9"}
            first = await client.post("/api/offers", json={"raw_text": OFFER_TEXT}, headers=headers)
            second = await client.post(
                "/api/offers", json={"raw_text": OFFER_TEXT}, headers=headers
            )
            spoofed = {"X-Forwarded-For": "5.5.5.5, 9.9.9.9"}  # same real address, fake prefix
            third = await client.post("/api/offers", json={"raw_text": OFFER_TEXT}, headers=spoofed)
        finally:
            limiter.limit = 20
            limiter.reset()
        assert first.status_code == 201
        assert second.status_code == third.status_code == 429
        assert int(second.headers["Retry-After"]) > 0


class TestDemoMode:
    async def test_meta(self, client: httpx.AsyncClient, settings: Settings) -> None:
        settings.demo_mode = True
        assert (await client.get("/api/meta")).json() == {"demo_mode": True, "llm_provider": "fake"}

    async def test_cv_upload_and_delete_are_disabled(
        self, client: httpx.AsyncClient, cv: dict[str, object], settings: Settings
    ) -> None:
        offer = (await client.post("/api/offers", json={"raw_text": OFFER_TEXT})).json()
        settings.demo_mode = True
        upload = await client.post("/api/cv/text", json={"text": "x" * 60})
        delete = await client.delete(f"/api/offers/{offer['id']}")
        assert upload.status_code == delete.status_code == 403

    async def test_reset_requires_the_admin_token(
        self, client: httpx.AsyncClient, settings: Settings
    ) -> None:
        settings.demo_mode, settings.admin_token = True, "s3cret"
        assert (await client.post("/api/admin/reset")).status_code == 401
        wrong = await client.post("/api/admin/reset", headers={"X-Admin-Token": "nope"})
        assert wrong.status_code == 401

        ok = await client.post("/api/admin/reset", headers={"X-Admin-Token": "s3cret"})
        assert ok.json() == {"offers": len(DEMO_OFFERS)}
        board = (await client.get("/api/applications")).json()
        assert sorted(a["status"] for a in board) == ["applied", "interview", "to_apply"]
        assert (await client.get("/api/cv")).json()["filename"] == "sample-cv.txt"

    async def test_reset_is_hidden_outside_demo_mode(
        self, client: httpx.AsyncClient, settings: Settings
    ) -> None:
        settings.demo_mode, settings.admin_token = False, "s3cret"
        response = await client.post("/api/admin/reset", headers={"X-Admin-Token": "s3cret"})
        assert response.status_code == 404


class TestProviderErrors:
    async def test_gemini_errors_become_llm_errors_with_the_right_status(self) -> None:
        from google.genai import errors

        from app.llm.base import LLMError
        from app.llm.gemini import _provider_errors

        for code, expected in [(429, 429), (404, 503), (500, 503)]:
            with pytest.raises(LLMError) as caught:
                async with _provider_errors():
                    raise errors.ClientError(code, {"error": {"code": code, "message": "x"}})
            assert caught.value.status_code == expected

    async def test_api_answers_with_the_llm_error_status(
        self, client: httpx.AsyncClient, cv: dict[str, object]
    ) -> None:
        from app.llm.base import LLMError
        from app.llm.factory import get_llm
        from app.llm.fake import FakeLLM
        from app.main import app

        class QuotaExhausted(FakeLLM):
            async def structured(self, **kwargs: object) -> object:  # type: ignore[override]
                raise LLMError("The AI quota is used up for now.", 429)

        app.dependency_overrides[get_llm] = QuotaExhausted
        try:
            response = await client.post("/api/offers", json={"raw_text": OFFER_TEXT})
        finally:
            app.dependency_overrides.clear()
            limiter.reset()
        assert response.status_code == 429
        assert response.json() == {"detail": "The AI quota is used up for now."}


class TestDemoSeeding:
    async def test_a_half_finished_seed_is_retried(
        self, client: httpx.AsyncClient, cv: dict[str, object]
    ) -> None:
        """A CV without offers (e.g. the model failed on the first start) seeds again."""
        from app.db.session import get_sessionmaker
        from app.llm.fake import FakeLLM
        from app.services.demo import seed_if_empty

        async with get_sessionmaker()() as session:
            await seed_if_empty(session, FakeLLM())
        offers = (await client.get("/api/offers")).json()
        assert len(offers) == len(DEMO_OFFERS)

        async with get_sessionmaker()() as session:  # second start: nothing to do
            await seed_if_empty(session, FakeLLM())
        assert len((await client.get("/api/offers")).json()) == len(DEMO_OFFERS)


class TestStaticFrontend:
    @pytest.fixture
    async def spa_client(self, tmp_path: Path) -> httpx.AsyncClient:
        (tmp_path / "index.html").write_text("<app-root></app-root>")
        (tmp_path / "main-abc123.js").write_text("console.log('app')")
        app = create_app(Settings(static_dir=str(tmp_path)))
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    async def test_serves_index_assets_and_client_routes(
        self, spa_client: httpx.AsyncClient
    ) -> None:
        async with spa_client as c:
            assert "<app-root>" in (await c.get("/")).text
            assert "<app-root>" in (await c.get("/offers/123")).text
            assert "console.log" in (await c.get("/main-abc123.js")).text
            assert (await c.get("/missing.js")).status_code == 404

    async def test_api_routes_still_win_and_unknown_api_paths_are_404(
        self, spa_client: httpx.AsyncClient
    ) -> None:
        async with spa_client as c:
            assert (await c.get("/health")).json() == {"status": "ok"}
            assert (await c.get("/api/does-not-exist")).status_code == 404


class TestSeedLLM:
    async def test_only_embeddings_go_to_the_real_provider(self) -> None:
        from app.llm.prompting import build_prompt
        from app.schemas.analysis import OfferExtraction
        from app.services.demo import SeedLLM

        class RealProvider:
            def __init__(self) -> None:
                self.embedded: list[str] = []

            async def embed(self, texts: list[str], *, task: str) -> list[list[float]]:
                self.embedded += texts
                return [[1.0] for _ in texts]

            async def structured(self, **kwargs: object) -> object:
                raise AssertionError("generation must not be used while seeding")

        real = RealProvider()
        seed = SeedLLM(real)  # type: ignore[arg-type]
        assert await seed.embed(["Python"], task="query") == [[1.0]]
        extraction = await seed.structured(
            system="", prompt=build_prompt("x", {"offer": OFFER_TEXT}), schema=OfferExtraction
        )
        assert real.embedded == ["Python"]
        assert extraction.title == "Junior Python Developer"
