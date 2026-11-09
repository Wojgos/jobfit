from typing import Literal

from app.db.models import JobOffer
from app.llm.base import LLMClient
from app.llm.prompting import build_prompt

COVER_SYSTEM = """You write short, specific cover letters for junior developer applications.
120-180 words, plain text, no placeholders like [Name]. Mention two or three concrete
matching skills backed by the CV evidence you are given. Never invent experience the
evidence does not show. Avoid clichés."""


async def write_cover_letter(llm: LLMClient, offer: JobOffer, language: Literal["pl", "en"]) -> str:
    analysis = offer.analysis
    matches = analysis.matches if analysis else []
    data = {
        "language": language,
        "offer": {"title": offer.title, "company": offer.company},
        "strengths": [m["name"] for m in matches if m["status"] == "met"],
        "evidence": [m["evidence"] for m in matches if m["evidence"]][:6],
        "gaps": [
            m["name"] for m in matches if m["status"] == "missing" and m["importance"] == "must"
        ],
    }
    target = "Polish" if language == "pl" else "English"
    return await llm.generate(
        system=COVER_SYSTEM, prompt=build_prompt(f"Write the cover letter in {target}.", data)
    )
