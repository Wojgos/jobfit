from typing import Any

from google import genai
from google.genai import types

from app.llm.base import EmbedTask, LLMStep, Message, T, ToolCall, ToolSpec


class GeminiClient:
    def __init__(self, *, api_key: str, model: str, embedding_model: str, embedding_dim: int):
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._embedding_model = embedding_model
        self._embedding_dim = embedding_dim

    async def structured(self, *, system: str, prompt: str, schema: type[T]) -> T:
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        if isinstance(response.parsed, schema):
            return response.parsed
        return schema.model_validate_json(response.text or "{}")

    async def generate(self, *, system: str, prompt: str) -> str:
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=system, temperature=0.4),
        )
        return (response.text or "").strip()

    async def embed(self, texts: list[str], *, task: EmbedTask) -> list[list[float]]:
        if not texts:
            return []
        response = await self._client.aio.models.embed_content(
            model=self._embedding_model,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT" if task == "document" else "RETRIEVAL_QUERY",
                output_dimensionality=self._embedding_dim,
            ),
        )
        return [list(e.values or []) for e in response.embeddings or []]

    async def step(self, *, system: str, history: list[Message], tools: list[ToolSpec]) -> LLMStep:
        declarations = [
            types.FunctionDeclaration(
                name=t.name, description=t.description, parameters_json_schema=t.parameters
            )
            for t in tools
        ]
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=self._to_contents(history),
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.0,
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
            result: dict[str, Any] = message.tool_result or {}
            return types.Content(
                role="user",
                parts=[
                    types.Part.from_function_response(name=message.tool_name or "", response=result)
                ],
            )
        if message.role == "assistant":
            parts = [types.Part(text=message.text)] if message.text else []
            parts += [
                types.Part(function_call=types.FunctionCall(id=c.id, name=c.name, args=c.args))
                for c in message.tool_calls
            ]
            return types.Content(role="model", parts=parts)
        return types.Content(role="user", parts=[types.Part(text=message.text)])
