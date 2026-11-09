"""Tools the offer assistant can call. Each returns a JSON-serialisable dict."""

import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import JobOffer
from app.llm.base import LLMClient, ToolSpec
from app.schemas.analysis import SalaryInfo
from app.services.cv_service import search_cv
from app.services.salary import normalize_monthly


@dataclass
class AgentContext:
    session: AsyncSession
    llm: LLMClient
    offer: JobOffer
    cv_document_id: uuid.UUID | None


TOOLS = [
    ToolSpec(
        name="search_cv",
        description="Search the candidate's CV for experience related to a topic. "
        "Returns the most relevant CV excerpts with a similarity score.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to look for, e.g. 'Docker'"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 5},
            },
            "required": ["query"],
        },
    ),
    ToolSpec(
        name="get_offer_analysis",
        description="Get the analysed job offer: title, company, seniority, work mode, "
        "requirements with their match status, overall score and monthly salary.",
        parameters={"type": "object", "properties": {}},
    ),
    ToolSpec(
        name="convert_salary",
        description="Convert a salary range to a monthly amount (168 h or 21 days a month).",
        parameters={
            "type": "object",
            "properties": {
                "min": {"type": "number"},
                "max": {"type": "number"},
                "unit": {"type": "string", "enum": ["hour", "day", "month", "year"]},
                "currency": {"type": "string"},
            },
            "required": ["unit"],
        },
    ),
]


async def run_tool(name: str, args: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
    try:
        if name == "search_cv":
            if ctx.cv_document_id is None:
                return {"error": "No CV uploaded"}
            query = str(args.get("query", "")).strip()
            if not query:
                return {"error": "query must not be empty"}
            limit = max(1, min(5, int(args.get("limit", 3))))
            [vector] = await ctx.llm.embed([query], task="query")
            hits = await search_cv(ctx.session, ctx.cv_document_id, vector, limit)
            return {"chunks": [{"text": text, "similarity": sim} for text, sim in hits]}
        if name == "get_offer_analysis":
            analysis = ctx.offer.analysis
            if analysis is None:
                return {"error": "The offer has not been analysed"}
            return {
                "title": ctx.offer.title,
                "company": ctx.offer.company,
                "score": analysis.score,
                "extraction": analysis.extraction,
                "matches": analysis.matches,
                "salary": analysis.salary,
            }
        if name == "convert_salary":
            salary = SalaryInfo.model_validate({"currency": "PLN", **args})
            return normalize_monthly(salary).model_dump()
    except (ValidationError, ValueError, TypeError) as exc:
        return {"error": f"Invalid arguments: {exc}"}
    return {"error": f"Unknown tool: {name}"}
