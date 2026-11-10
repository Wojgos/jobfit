from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session
from app.llm.base import LLMClient
from app.llm.factory import get_llm

SessionDep = Annotated[AsyncSession, Depends(get_session)]
LLMDep = Annotated[LLMClient, Depends(get_llm)]


async def forbid_in_demo() -> None:
    """Guard for actions that would let visitors of the public demo change shared data."""
    if get_settings().demo_mode:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This action is disabled in the public demo")
