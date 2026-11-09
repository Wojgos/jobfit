from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Analysis, Application, JobOffer
from app.llm.base import LLMClient
from app.llm.prompting import build_prompt
from app.schemas.analysis import (
    MatchJudgement,
    OfferExtraction,
    Requirement,
    RequirementMatch,
)
from app.services.cv_service import latest_cv, search_cv
from app.services.salary import normalize_monthly
from app.services.scoring import compute_score

EXTRACT_SYSTEM = """You extract structured data from job offers for software developers.
List every concrete requirement as a separate item with a short canonical name
(e.g. "Python", "PostgreSQL", "REST API", "English B2"). Mark importance "nice" only for
items the offer explicitly calls optional, nice to have or a plus. Never invent requirements.
If the offer states a salary, fill it in with its unit (hour, day, month or year)."""

JUDGE_SYSTEM = """You compare job requirements with excerpts from a candidate's CV.
For each requirement decide: "met" when the CV clearly shows it, "partial" when it shows
related or weaker experience, "missing" when there is no evidence. Use only the provided
excerpts and quote them briefly as evidence. Keep the requirement names unchanged.
Write a 2-3 sentence summary for the candidate in the language of the job offer."""

EVIDENCE_PER_REQUIREMENT = 3


class NoCvError(RuntimeError):
    pass


def dedupe(requirements: list[Requirement]) -> list[Requirement]:
    seen: dict[str, Requirement] = {}
    for req in requirements:
        key = req.name.strip().lower()
        if key and (key not in seen or req.importance == "must"):
            seen[key] = req
    return list(seen.values())


def reconcile(
    requirements: list[Requirement], judged: list[RequirementMatch]
) -> list[RequirementMatch]:
    """Keep exactly one match per extracted requirement, trusting our own importance."""
    by_name = {m.name.strip().lower(): m for m in judged}
    result = []
    for req in requirements:
        match = by_name.get(req.name.strip().lower())
        result.append(
            RequirementMatch(
                name=req.name,
                importance=req.importance,
                status=match.status if match else "missing",
                evidence=match.evidence if match else "",
                comment=match.comment if match else "",
            )
        )
    return result


async def analyze_offer(
    session: AsyncSession, llm: LLMClient, *, raw_text: str, source_url: str | None
) -> JobOffer:
    cv = await latest_cv(session)
    if cv is None:
        raise NoCvError("Upload your CV before analysing offers")

    extraction = await llm.structured(
        system=EXTRACT_SYSTEM,
        prompt=build_prompt("Extract the job offer.", {"offer": raw_text}),
        schema=OfferExtraction,
    )
    requirements = dedupe(extraction.requirements)

    vectors = await llm.embed([r.name for r in requirements], task="query")
    # One AsyncSession must not run queries concurrently, so the searches go one by one.
    evidence = [await search_cv(session, cv.id, v, EVIDENCE_PER_REQUIREMENT) for v in vectors]

    if requirements:
        judgement = await llm.structured(
            system=JUDGE_SYSTEM,
            prompt=build_prompt(
                "Judge every requirement against the CV excerpts.",
                {
                    "requirements": [
                        {"name": r.name, "importance": r.importance, "evidence": [t for t, _ in ev]}
                        for r, ev in zip(requirements, evidence, strict=True)
                    ]
                },
            ),
            schema=MatchJudgement,
        )
    else:
        judgement = MatchJudgement(matches=[], summary="No requirements were found in the offer.")

    matches = reconcile(requirements, judgement.matches)
    salary = extraction.salary
    normalized = (
        normalize_monthly(salary)
        if salary and (salary.min is not None or salary.max is not None)
        else None
    )

    offer = JobOffer(
        title=extraction.title[:255],
        company=(extraction.company or None) and extraction.company[:255],
        source_url=source_url,
        raw_text=raw_text,
    )
    offer.analysis = Analysis(
        cv_document_id=cv.id,
        extraction=extraction.model_copy(update={"requirements": requirements}).model_dump(),
        matches=[m.model_dump() for m in matches],
        salary=normalized.model_dump() if normalized else None,
        score=compute_score(matches),
        summary=judgement.summary,
    )
    offer.application = Application()
    session.add(offer)
    await session.commit()
    return offer
