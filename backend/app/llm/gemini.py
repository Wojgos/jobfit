import asyncio
from collections.abc import Awaitable
from typing import Any, TypeVar

from google import genai
from google.genai import errors, types

from app.llm.base import EmbedTask, LLMError, LLMStep, Message, T, ToolCall, ToolSpec

R = TypeVar("R")

# Free-tier quotas are a few requests per minute: back off and retry before giving up.
RETRY = types.HttpRetryOptions(
    attempts=3, initial_delay=2.0, max_delay=20.0, http_status_codes=[429, 500, 503, 504]
)
THINKING_LEVELS = {
    "low": types.ThinkingLevel.LOW,
    "medium": types.ThinkingLevel.MEDIUM,
    "high": types.ThinkingLevel.HIGH,
}


class GeminiClient:
    """Gemini 3.x client.

    Gemini 3 ignores ``temperature``/``top_p``/``top_k`` (deprecated), so determinism comes
    from the system instructions. ``thinking_level="low"`` keeps latency down; extracting
    requirements and judging matches do not need long reasoning.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        embedding_model: str,
        embedding_dim: int,
        thinking_level: str | None = "low",
        call_timeout: float = 50.0,
    ) -> None:
        self._client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(retry_options=RETRY)
        )
        self._model = model
        self._embedding_model = embedding_model
        self._embedding_dim = embedding_dim
        self._thinking = (
            types.ThinkingConfig(thinking_level=THINKING_LEVELS[thinking_level])
            if thinking_level
            else None
        )
        self._timeout = call_timeout

    async def _call(self, request: Awaitable[R]) -> R:
        """Bound every request (retries included) and translate provider errors.

        Two model calls per analysis must fit in the 120 s Cloud Run request timeout.
        """
        try:
            return await asyncio.wait_for(request, self._timeout)
        except TimeoutError as exc:
            raise LLMError("The AI model took too long to answer. Try again.", 504) from exc
        except errors.APIError as exc:
            if exc.code == 429:
                raise LLMError(
                    "The AI quota is used up for now. Try again in a minute.", 429
                ) from exc
            raise LLMError(f"The AI provider returned an error ({exc.code}).") from exc

    def _config(self, system: str, **options: Any) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=system, thinking_config=self._thinking, **options
        )

    async def structured(self, *, system: str, prompt: str, schema: type[T]) -> T:
        response = await self._call(
            self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=self._config(
                    system, response_mime_type="application/json", response_schema=schema
                ),
            )
        )
        if isinstance(response.parsed, schema):
            return response.parsed
        return schema.model_validate_json(response.text or "{}")

    async def generate(self, *, system: str, prompt: str) -> str:
        response = await self._call(
            self._client.aio.models.generate_content(
                model=self._model, contents=prompt, config=self._config(system)
            )
        )
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
        response = await self._call(
            self._client.aio.models.generate_content(
                model=self._model,
                contents=self._to_contents(history),
                config=self._config(
                    system,
                    tools=[types.Tool(function_declarations=declarations)],
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                ),
            )
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
