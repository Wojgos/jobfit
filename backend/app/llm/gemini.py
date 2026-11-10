import asyncio
import logging
from collections.abc import Awaitable
from typing import Any, TypeVar

from google import genai
from google.genai import errors, types

from app.llm.base import EmbedTask, LLMError, LLMStep, Message, T, ToolCall, ToolSpec

R = TypeVar("R")
logger = logging.getLogger(__name__)

# One quick retry; a model that keeps failing is skipped in favour of the next one.
RETRY = types.HttpRetryOptions(
    attempts=2, initial_delay=1.5, max_delay=5.0, http_status_codes=[429, 500, 503, 504]
)
THINKING_LEVELS = {
    "low": types.ThinkingLevel.LOW,
    "medium": types.ThinkingLevel.MEDIUM,
    "high": types.ThinkingLevel.HIGH,
}
# Codes that say "this model, right now" rather than "this request": try the next model.
FALLBACK_CODES = {404, 500, 503, 504}


class GeminiClient:
    """Gemini 3.x client with a model fallback chain.

    Gemini 3 ignores ``temperature``/``top_p``/``top_k`` (deprecated), so determinism comes
    from the system instructions. On the free tier the newest models are often overloaded
    (503) and older ones get closed to new users (404), so generation walks through
    ``models`` in order and remembers models that are not available at all.
    """

    def __init__(
        self,
        *,
        api_key: str,
        models: list[str],
        embedding_model: str,
        embedding_dim: int,
        thinking_level: str | None = None,
        call_timeout: float = 30.0,
    ) -> None:
        if not models:
            raise ValueError("At least one model is required")
        self._client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(retry_options=RETRY)
        )
        self._models = list(dict.fromkeys(models))
        self._unavailable: set[str] = set()
        self._embedding_model = embedding_model
        self._embedding_dim = embedding_dim
        self._thinking = (
            types.ThinkingConfig(thinking_level=THINKING_LEVELS[thinking_level])
            if thinking_level
            else None
        )
        self._timeout = call_timeout

    async def _call(self, request: Awaitable[R]) -> R:
        """Bound one request (SDK retries included) and translate provider errors."""
        try:
            return await asyncio.wait_for(request, self._timeout)
        except TimeoutError as exc:
            raise LLMError("The AI model took too long to answer. Try again.", 504) from exc
        except errors.APIError as exc:
            if exc.code == 429:
                raise LLMError(
                    "The AI quota is used up for now. Try again in a minute.", 429
                ) from exc
            error = LLMError(f"The AI provider returned an error ({exc.code}).")
            error.provider_code = exc.code
            raise error from exc

    async def _generate(
        self, contents: Any, config: types.GenerateContentConfig
    ) -> types.GenerateContentResponse:
        last: LLMError | None = None
        for model in [m for m in self._models if m not in self._unavailable] or self._models:
            try:
                return await self._call(
                    self._client.aio.models.generate_content(
                        model=model, contents=contents, config=config
                    )
                )
            except LLMError as exc:
                code = exc.provider_code or exc.status_code
                if code not in FALLBACK_CODES:
                    raise
                if code == 404:
                    self._unavailable.add(model)
                logger.warning("Model %s failed (%s), trying the next one", model, code)
                last = exc
        assert last is not None
        raise last

    def _config(self, system: str, **options: Any) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=system, thinking_config=self._thinking, **options
        )

    async def structured(self, *, system: str, prompt: str, schema: type[T]) -> T:
        response = await self._generate(
            prompt,
            self._config(system, response_mime_type="application/json", response_schema=schema),
        )
        if isinstance(response.parsed, schema):
            return response.parsed
        return schema.model_validate_json(response.text or "{}")

    async def generate(self, *, system: str, prompt: str) -> str:
        response = await self._generate(prompt, self._config(system))
        return (response.text or "").strip()

    async def embed(self, texts: list[str], *, task: EmbedTask) -> list[list[float]]:
        if not texts:
            return []
        response = await self._call(
            self._client.aio.models.embed_content(
                model=self._embedding_model,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT" if task == "document" else "RETRIEVAL_QUERY",
                    output_dimensionality=self._embedding_dim,
                ),
            )
        )
        return [list(e.values or []) for e in response.embeddings or []]

    async def step(self, *, system: str, history: list[Message], tools: list[ToolSpec]) -> LLMStep:
        declarations = [
            types.FunctionDeclaration(
                name=t.name, description=t.description, parameters_json_schema=t.parameters
            )
            for t in tools
        ]
        response = await self._generate(
            self._to_contents(history),
            self._config(
                system,
                tools=[types.Tool(function_declarations=declarations)],
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        raw = response.candidates[0].content if response.candidates else None
        calls = [
            ToolCall(id=fc.id or f"call_{i}", name=fc.name or "", args=dict(fc.args or {}))
            for i, fc in enumerate(response.function_calls or [])
        ]
        if calls:
            return LLMStep(text=None, tool_calls=calls, raw=raw)
        return LLMStep(text=(response.text or "").strip(), tool_calls=[], raw=raw)

    @classmethod
    def _to_contents(cls, history: list[Message]) -> list[types.Content]:
        """Convert history; results of parallel tool calls go back as one turn."""
        contents: list[types.Content] = []
        for message in history:
            content = cls._to_content(message)
            previous = contents[-1] if contents else None
            if (
                message.role == "tool"
                and previous is not None
                and previous.role == "user"
                and previous.parts
                and all(p.function_response for p in previous.parts)
            ):
                previous.parts.extend(content.parts or [])
            else:
                contents.append(content)
        return contents

    @staticmethod
    def _to_content(message: Message) -> types.Content:
        if message.role == "assistant" and isinstance(message.raw, types.Content):
            return message.raw  # keeps thought signatures required for multi-turn tool use
        if message.role == "tool":
            # Gemini 3 expects every function response to carry the call id and name.
            response = types.FunctionResponse(
                id=message.tool_call_id,
                name=message.tool_name or "",
                response=message.tool_result or {},
            )
            return types.Content(role="user", parts=[types.Part(function_response=response)])
        if message.role == "assistant":
            parts = [types.Part(text=message.text)] if message.text else []
            parts += [
                types.Part(function_call=types.FunctionCall(id=c.id, name=c.name, args=c.args))
                for c in message.tool_calls
            ]
            return types.Content(role="model", parts=parts)
        return types.Content(role="user", parts=[types.Part(text=message.text)])
