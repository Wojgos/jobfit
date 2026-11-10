"""Provider-agnostic LLM interface used by services and the agent loop."""

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
EmbedTask = Literal["document", "query"]


class LLMError(RuntimeError):
    """The LLM provider failed; ``status_code`` is what the API should answer with."""

    def __init__(self, message: str, status_code: int = 503) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema of the arguments


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass
class Message:
    role: Literal["user", "assistant", "tool"]
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_name: str | None = None
    tool_result: dict[str, Any] | None = None
    # Provider-native message (e.g. Gemini Content with thought signatures), replayed as-is.
    raw: Any = None


@dataclass
class LLMStep:
    text: str | None
    tool_calls: list[ToolCall]
    raw: Any = None


class LLMClient(Protocol):
    async def structured(self, *, system: str, prompt: str, schema: type[T]) -> T: ...

    async def generate(self, *, system: str, prompt: str) -> str: ...

    async def embed(self, texts: list[str], *, task: EmbedTask) -> list[list[float]]: ...

    async def step(
        self, *, system: str, history: list[Message], tools: list[ToolSpec]
    ) -> LLMStep: ...
