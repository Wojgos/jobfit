from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import applications, cv, health, offers
from app.core.config import get_settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="JobFit API",
        description="Match job offers against your CV with an LLM agent.",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in (health, cv, offers, applications):
        app.include_router(module.router)
    return app


app = create_app()
