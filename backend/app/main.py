import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import Scope

from app.api.routes import admin, applications, cv, health, offers
from app.core.config import Settings, get_settings
from app.db.session import get_sessionmaker
from app.llm.factory import get_llm
from app.services.demo import seed_if_empty

logging.basicConfig(level=logging.INFO)


class SpaStaticFiles(StaticFiles):
    """Serve the built Angular app; unknown non-file paths fall back to index.html so that
    client-side routes like /offers/123 work after a page reload."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            response = None
        if response is not None and response.status_code != 404:
            return response
        # Decide on the URL path: ``path`` is an OS path (backslashes on Windows).
        url_path: str = scope["path"]
        is_route = "." not in url_path.rsplit("/", 1)[-1]
        if is_route and not url_path.startswith("/api/"):
            return await super().get_response("index.html", scope)
        raise StarletteHTTPException(status_code=404)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if get_settings().demo_mode:
        async with get_sessionmaker()() as session:
            await seed_if_empty(session, get_llm())
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="JobFit API",
        description="Match job offers against your CV with an LLM agent.",
        version="0.2.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in (health, admin, cv, offers, applications):
        app.include_router(module.router)
    # Mounted last so that every API route wins over the catch-all static files.
    if settings.static_dir and Path(settings.static_dir, "index.html").is_file():
        app.mount("/", SpaStaticFiles(directory=settings.static_dir, html=True), name="frontend")
    return app


app = create_app()
