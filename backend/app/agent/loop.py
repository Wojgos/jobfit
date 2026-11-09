import json

from app.agent.tools import TOOLS, AgentContext, run_tool
from app.llm.base import LLMClient, Message
from app.schemas.api import AskOut, ToolTrace

AGENT_SYSTEM = """You are a career assistant helping a junior developer with one job offer.
Use the tools to look up facts about the offer and the candidate's CV before you answer.
Answer concisely in the language of the question. If the CV has no evidence for something,
say so plainly - never invent experience."""

STEP_LIMIT_ANSWER = "I could not finish within the step limit. Try a more specific question."


async def run_agent(llm: LLMClient, ctx: AgentContext, question: str, max_steps: int) -> AskOut:
    """Tool-calling loop: let the model call tools until it produces a text answer."""
    history = [Message(role="user", text=question)]
    trace: list[ToolTrace] = []
    for _ in range(max_steps):
        step = await llm.step(system=AGENT_SYSTEM, history=history, tools=TOOLS)
        if not step.tool_calls:
            return AskOut(answer=step.text or "", steps=trace)
        history.append(
            Message(
                role="assistant", text=step.text or "", tool_calls=step.tool_calls, raw=step.raw
            )
        )
        for call in step.tool_calls:
            result = await run_tool(call.name, call.args, ctx)
            history.append(Message(role="tool", tool_name=call.name, tool_result=result))
            trace.append(
                ToolTrace(
                    tool=call.name,
                    args=call.args,
                    result_preview=json.dumps(result, ensure_ascii=False)[:300],
                )
            )
    return AskOut(answer=STEP_LIMIT_ANSWER, steps=trace)
