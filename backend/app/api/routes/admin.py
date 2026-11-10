import secrets
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

from app.api.deps import LLMDep, SessionDep
from app.core.config import get_settings
from app.services.demo import reset_demo

router = APIRouter(tags=["admin"])


@router.get("/api/meta")
async def meta() -> dict[str, object]:
    """Lets the frontend know whether it runs as the public demo."""
    settings = get_settings()
    return {"demo_mode": settings.demo_mode, "llm_provider": settings.llm_provider}


@router.post("/api/admin/reset")
async def reset(
    session: SessionDep,
    llm: LLMDep,
    x_admin_token: Annotated[str | None, Header()] = None,
) -> dict[str, int]:
    """Restore the demo data; called nightly by a scheduled GitHub Actions workflow."""
    settings = get_settings()
    if not settings.demo_mode or not settings.admin_token:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if not x_admin_token or not secrets.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid admin token")
    return {"offers": await reset_demo(session, llm)}
