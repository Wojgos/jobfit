"""The tool-calling loop, driven by a scripted model."""

import uuid
from typing import Any

from app.agent.loop import STEP_LIMIT_ANSWER, run_agent
from app.agent.tools import AgentContext, run_tool
from app.db.models import JobOffer
from app.llm.base import LLMStep, Message, T, ToolCall, ToolSpec
from app.llm.fake import FakeLLM


class ScriptedLLM(FakeLLM):
    def __init__(self, steps: list[LLMStep]) -> None:
        self.steps = steps
        self.seen: list[list[Message]] = []

    async def structured(self, *, system: str, prompt: str, schema: type[T]) -> T:
        raise AssertionError("not used")

    async def step(self, *, system: str, history: list[Message], tools: list[ToolSpec]) -> LLMStep:
        self.seen.append(list(history))
        return self.steps.pop(0)


def context(llm: FakeLLM) -> AgentContext:
    offer = JobOffer(id=uuid.uuid4(), title="Junior Python Developer", raw_text="...")
    return AgentContext(session=None, llm=llm, offer=offer, cv_document_id=None)  # type: ignore[arg-type]


async def test_tool_results_are_fed_back_until_the_model_answers() -> None:
    llm = ScriptedLLM(
        [
            LLMStep(
                text=None,
                tool_calls=[
                    ToolCall(
                        id="1", name="convert_salary", args={"min": 40, "max": 60, "unit": "hour"}
                    ),
                    ToolCall(id="2", name="no_such_tool", args={}),
                ],
            ),
            LLMStep(text="About 6720-10080 PLN a month.", tool_calls=[]),
        ]
    )
    result = await run_agent(llm, context(llm), "How much per month?", max_steps=5)

    assert result.answer == "About 6720-10080 PLN a month."
    assert [s.tool for s in result.steps] == ["convert_salary", "no_such_tool"]
    second_call_history = llm.seen[1]
    tool_messages = [m for m in second_call_history if m.role == "tool"]
    assert tool_messages[0].tool_result is not None
    assert tool_messages[0].tool_result["monthly_max"] == 10080
    assert tool_messages[1].tool_result == {"error": "Unknown tool: no_such_tool"}


async def test_loop_stops_at_the_step_limit() -> None:
    call = LLMStep(text=None, tool_calls=[ToolCall(id="1", name="get_offer_analysis", args={})])
    llm = ScriptedLLM([call, call, call])
    result = await run_agent(llm, context(llm), "?", max_steps=2)
    assert result.answer == STEP_LIMIT_ANSWER
    assert len(result.steps) == 2


async def test_tools_report_bad_input_instead_of_raising() -> None:
    ctx = context(FakeLLM())
    bad_unit: dict[str, Any] = {"unit": "week"}
    assert "error" in await run_tool("convert_salary", bad_unit, ctx)
    assert await run_tool("search_cv", {"query": "x"}, ctx) == {"error": "No CV uploaded"}
    assert "error" in await run_tool("get_offer_analysis", {}, ctx)
