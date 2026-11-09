from functools import lru_cache

from app.core.config import EMBEDDING_DIM, get_settings
from app.llm.base import LLMClient
from app.llm.fake import FakeLLM


@lru_cache
def get_llm() -> LLMClient:
    settings = get_settings()
    if settings.llm_provider == "gemini":
        if not settings.google_api_key:
            raise RuntimeError("LLM_PROVIDER=gemini requires GOOGLE_API_KEY")
        from app.llm.gemini import GeminiClient  # imported lazily: the SDK is slow to load

        return GeminiClient(
            api_key=settings.google_api_key,
            model=settings.llm_model,
            embedding_model=settings.embedding_model,
            embedding_dim=EMBEDDING_DIM,
        )
    return FakeLLM()
