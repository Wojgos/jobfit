"""Deterministic offline stand-in for a real LLM.

Used by the test suite and when no API key is configured. It reads the JSON block that
every prompt carries (see app.llm.prompting) and answers with simple heuristics, so the
whole application works end to end without network access.
"""

import math
import re
import zlib
from typing import Any

from app.core.config import EMBEDDING_DIM
from app.llm.base import EmbedTask, LLMStep, Message, T, ToolCall, ToolSpec
from app.llm.prompting import read_data
from app.schemas.analysis import (
    MatchJudgement,
    OfferExtraction,
    Requirement,
    RequirementMatch,
    SalaryInfo,
)

SKILLS: dict[str, str] = {
    # name -> category
    "Python": "language",
    "Java": "language",
    "Kotlin": "language",
    "C#": "language",
    "JavaScript": "language",
    "TypeScript": "language",
    "Go": "language",
    "SQL": "language",
    "HTML": "language",
    "CSS": "language",
    "SCSS": "language",
    "Django": "framework",
    "Django REST Framework": "framework",
    "FastAPI": "framework",
    "Flask": "framework",
    "SQLAlchemy": "framework",
    "Pydantic": "framework",
    "Celery": "framework",
    "Spring Boot": "framework",
    ".NET": "framework",
    "Angular": "framework",
    "React": "framework",
    "React Native": "framework",
    "Vue": "framework",
    "Node.js": "framework",
    "Next.js": "framework",
    "RxJS": "framework",
    "NgRx": "framework",
    "Tailwind": "framework",
    "LangChain": "framework",
    "PyTorch": "framework",
    "TensorFlow": "framework",
    "scikit-learn": "framework",
    "pandas": "framework",
    "PostgreSQL": "database",
    "MySQL": "database",
    "MongoDB": "database",
    "Redis": "database",
    "Elasticsearch": "database",
    "Kafka": "tool",
    "RabbitMQ": "tool",
    "Docker": "tool",
    "Kubernetes": "tool",
    "Terraform": "tool",
    "Git": "tool",
    "GitHub Actions": "tool",
    "GitLab CI": "tool",
    "Jenkins": "tool",
    "Linux": "tool",
    "Airflow": "tool",
    "Jira": "tool",
    "AWS": "cloud",
    "Azure": "cloud",
    "GCP": "cloud",
    "REST API": "practice",
    "GraphQL": "practice",
    "WebSocket": "practice",
    "Microservices": "practice",
    "CI/CD": "practice",
    "Unit testing": "practice",
    "pytest": "tool",
    "Jest": "tool",
    "Playwright": "tool",
    "Selenium": "tool",
    "Machine learning": "practice",
    "LLM": "practice",
    "RAG": "practice",
    "Agile": "practice",
    "Scrum": "practice",
}
ALIASES: dict[str, str] = {
    "drf": "Django REST Framework",
    "postgres": "PostgreSQL",
    "k8s": "Kubernetes",
    "google cloud": "GCP",
    "rest": "REST API",
    "restful": "REST API",
    "nodejs": "Node.js",
    "sass": "SCSS",
    "testy jednostkowe": "Unit testing",
    "unit tests": "Unit testing",
    "uczenie maszynowe": "Machine learning",
    "ml": "Machine learning",
    "websockets": "WebSocket",
    "mikroserwisy": "Microservices",
    "tailwind css": "Tailwind",
    "dotnet": ".NET",
}

NICE_HEADINGS = re.compile(
    r"nice to have|mile widziane|will be a plus|dodatkow\w* atut|bonus|advantage|optional", re.I
)
MUST_HEADINGS = re.compile(
    r"requirements|wymagania|must have|oczekujemy|we expect|what you need|your skills|tech stack",
    re.I,
)
TOKEN = re.compile(r"[a-ząćęłńóśźż0-9+#.]+", re.I)


def _pattern(term: str) -> re.Pattern[str]:
    return re.compile(r"(?<![\w+#.])" + re.escape(term) + r"(?![\w+#])", re.I)


SKILL_PATTERNS = sorted(
    [(name, _pattern(name)) for name in SKILLS]
    + [(name, _pattern(a)) for a, name in ALIASES.items()],
    key=lambda item: -len(item[1].pattern),  # longest first, so "React Native" wins over "React"
)


def tokens(text: str) -> list[str]:
    return [t.strip(".").lower() for t in TOKEN.findall(text) if t.strip(".")]


def hashed_embedding(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    vector = [0.0] * dim
    for token in tokens(text):
        vector[zlib.crc32(token.encode()) % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        vector[0] = 1.0
        return vector
    return [v / norm for v in vector]


def find_skills(text: str) -> list[tuple[str, int]]:
    """Return (skill, position) pairs, ignoring matches inside a longer skill match."""
    taken: list[tuple[int, int]] = []
    found: dict[str, int] = {}
    for name, pattern in SKILL_PATTERNS:
        for m in pattern.finditer(text):
            if any(m.start() < end and start < m.end() for start, end in taken):
                continue
            taken.append((m.start(), m.end()))
            found.setdefault(name, m.start())
    return sorted(found.items(), key=lambda item: item[1])


def extract_offer(text: str) -> OfferExtraction:
    lines = [line.strip() for line in text.splitlines()]
    title = next((line for line in lines if line), "Job offer")[:120]

    # Importance of each line follows the last section heading seen above it.
    importance_at: list[tuple[int, str]] = []
    offset, current = 0, "must"
    for line in text.splitlines(keepends=True):
        if NICE_HEADINGS.search(line):
            current = "nice"
        elif MUST_HEADINGS.search(line):
            current = "must"
        importance_at.append((offset, current))
        offset += len(line)

    def importance(pos: int) -> str:
        level = "must"
        for start, value in importance_at:
            if start > pos:
                break
            level = value
        return level

    requirements = [
        Requirement(name=name, category=SKILLS[name], importance=importance(pos))
        for name, pos in find_skills(text)
    ]
    english = re.search(r"(english|angielski\w*)[^\n]{0,30}?\b([abc][12])\b", text, re.I)
    if english:
        requirements.append(
            Requirement(
                name=f"English {english.group(2).upper()}",
                category="soft_skill",
                importance=importance(english.start()),
            )
        )

    lower = text.lower()
    seniority = next(
        (
            level
            for level, words in [
                ("intern", ("intern", "trainee", "staż", "stażyst")),
                ("junior", ("junior", "młodszy", "mlodszy")),
                ("senior", ("senior",)),
                ("mid", ("regular", "mid-level", " mid ")),
            ]
            if any(w in lower for w in words)
        ),
        "unknown",
    )
    work_mode = next(
        (
            mode
            for mode, words in [
                ("remote", ("remote", "zdaln")),
                ("hybrid", ("hybrid", "hybryd")),
                ("onsite", ("on-site", "onsite", "stacjonar", "office")),
            ]
            if any(w in lower for w in words)
        ),
        "unknown",
    )
    company_match = re.search(r"^(?:company|firma|pracodawca)\s*[:\-]\s*(.+)$", text, re.I | re.M)
    return OfferExtraction(
        title=title,
        company=company_match.group(1).strip() if company_match else None,
        seniority=seniority,
        work_mode=work_mode,
        requirements=requirements,
        salary=extract_salary(text),
    )


# "12000", "12 000" (also with a non-breaking space) and "60,5".
NUMBER = r"\d+(?:[  ]\d{3})*(?:[.,]\d+)?"
SALARY = re.compile(
    rf"({NUMBER})\s*(?:-|–|do|to)\s*({NUMBER})\s*(pln|zł|zl|eur|€|usd|\$)?"
    r"[^\n]{0,25}?(?:/|per|na)\s*(h\b|godz|hour|dzie|day|mies|month|mc|rok|year)",
    re.I,
)


def _number(raw: str) -> float:
    return float(raw.replace(" ", "").replace(" ", "").replace(",", "."))


def extract_salary(text: str) -> SalaryInfo | None:
    m = SALARY.search(text)
    if not m:
        return None
    currency = {"zł": "PLN", "zl": "PLN", "€": "EUR", "$": "USD"}.get(
        (m.group(3) or "pln").lower(), (m.group(3) or "PLN").upper()
    )
    unit_raw = m.group(4).lower()
    unit = (
        "hour"
        if unit_raw.startswith(("h", "godz"))
        else "day"
        if unit_raw.startswith(("dzie", "day"))
        else "year"
        if unit_raw.startswith(("rok", "year"))
        else "month"
    )
    lower = text.lower()
    contract = (
        "b2b"
        if "b2b" in lower
        else "uop"
        if re.search(r"umow\w* o prac|\buop\b|employment contract|permanent", lower)
        else "unknown"
    )
    return SalaryInfo(
        min=_number(m.group(1)),
        max=_number(m.group(2)),
        currency=currency,
        unit=unit,
        contract=contract,
    )


def judge(data: dict[str, Any]) -> MatchJudgement:
    matches: list[RequirementMatch] = []
    for req in data.get("requirements", []):
        name: str = req["name"]
        evidence: list[str] = req.get("evidence", [])
        pattern = _pattern(name)
        hit = next((e for e in evidence if pattern.search(e)), None)
        name_tokens = {t for t in tokens(name) if len(t) > 2}
        partial = next((e for e in evidence if name_tokens & set(tokens(e))), None)
        if hit:
            status, quote = "met", hit
        elif partial:
            status, quote = "partial", partial
        else:
            status, quote = "missing", ""
        matches.append(
            RequirementMatch(
                name=name,
                importance=req.get("importance", "must"),
                status=status,
                evidence=quote[:200],
            )
        )
    met = sum(m.status == "met" for m in matches)
    return MatchJudgement(
        matches=matches, summary=f"{met} of {len(matches)} requirements found in the CV."
    )


class FakeLLM:
    async def structured(self, *, system: str, prompt: str, schema: type[T]) -> T:
        data = read_data(prompt)
        if schema is OfferExtraction:
            return schema.model_validate(extract_offer(data.get("offer", "")).model_dump())
        if schema is MatchJudgement:
            return schema.model_validate(judge(data).model_dump())
        raise NotImplementedError(f"FakeLLM cannot produce {schema.__name__}")

    async def generate(self, *, system: str, prompt: str) -> str:
        data = read_data(prompt)
        offer = data.get("offer", {})
        strengths = ", ".join(data.get("strengths", [])[:5]) or "the required technologies"
        target = offer.get("title", "this position")
        if offer.get("company"):
            target += (
                f" at {offer['company']}"
                if data.get("language") == "en"
                else f" w {offer['company']}"
            )
        if data.get("language") == "en":
            return (
                f"Dear Hiring Team,\n\nI am applying for {target}. "
                f"In my projects I have worked with {strengths}, "
                "which matches your requirements.\n\n"
                "Kind regards"
            )
        return (
            f"Szanowni Państwo,\n\naplikuję na stanowisko {target}. "
            f"W swoich projektach pracowałem z {strengths}, "
            "co pokrywa się z Państwa wymaganiami.\n\n"
            "Z wyrazami szacunku"
        )

    async def embed(self, texts: list[str], *, task: EmbedTask) -> list[list[float]]:
        return [hashed_embedding(t) for t in texts]

    async def step(self, *, system: str, history: list[Message], tools: list[ToolSpec]) -> LLMStep:
        question = next((m.text for m in reversed(history) if m.role == "user"), "")
        results = [m for m in history if m.role == "tool"]
        if not results and any(t.name == "search_cv" for t in tools):
            return LLMStep(
                text=None,
                tool_calls=[ToolCall(id="fake-1", name="search_cv", args={"query": question})],
            )
        found = [
            chunk["text"] for r in results for chunk in (r.tool_result or {}).get("chunks", [])
        ]
        if not found:
            return LLMStep(text="I could not find anything relevant in the CV.", tool_calls=[])
        return LLMStep(text="Relevant parts of the CV:\n- " + "\n- ".join(found[:3]), tool_calls=[])
