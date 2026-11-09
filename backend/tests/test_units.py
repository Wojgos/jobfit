import pytest

from app.llm.fake import extract_offer, find_skills, hashed_embedding
from app.schemas.analysis import RequirementMatch, SalaryInfo
from app.services.chunking import chunk_text
from app.services.salary import normalize_monthly
from app.services.scoring import compute_score
from tests.conftest import OFFER_TEXT


class TestChunking:
    def test_short_paragraphs_are_packed_together(self) -> None:
        assert chunk_text("one\n\ntwo\n\nthree", max_chars=100, overlap=10) == [
            "one\n\ntwo\n\nthree"
        ]

    def test_paragraphs_split_when_limit_is_reached(self) -> None:
        text = "a" * 60 + "\n\n" + "b" * 60
        assert chunk_text(text, max_chars=100, overlap=10) == ["a" * 60, "b" * 60]

    def test_long_paragraph_is_cut_into_overlapping_windows(self) -> None:
        text = "".join(str(i % 10) for i in range(250))
        chunks = chunk_text(text, max_chars=100, overlap=20)
        assert [len(c) for c in chunks] == [100, 100, 90]
        assert chunks[0][-20:] == chunks[1][:20]
        assert "".join(c[20:] if i else c for i, c in enumerate(chunks)) == text

    def test_empty_text_gives_no_chunks(self) -> None:
        assert chunk_text("  \n\n ") == []

    def test_overlap_must_be_smaller_than_chunk(self) -> None:
        with pytest.raises(ValueError):
            chunk_text("x", max_chars=10, overlap=10)


class TestSalary:
    @pytest.mark.parametrize(
        ("unit", "low", "high", "expected"),
        [
            ("hour", 40, 60, (6720, 10080)),
            ("day", 500, 700, (10500, 14700)),
            ("month", 8000, 12000, (8000, 12000)),
            ("year", 120000, 180000, (10000, 15000)),
        ],
    )
    def test_converts_to_monthly(
        self, unit: str, low: float, high: float, expected: tuple[int, int]
    ) -> None:
        result = normalize_monthly(
            SalaryInfo.model_validate({"min": low, "max": high, "unit": unit})
        )
        assert (result.monthly_min, result.monthly_max) == expected

    def test_swapped_range_is_fixed_and_contract_passed_through(self) -> None:
        result = normalize_monthly(SalaryInfo(min=12000, max=8000, contract="b2b"))
        assert (result.monthly_min, result.monthly_max, result.contract) == (8000, 12000, "b2b")

    def test_open_range(self) -> None:
        result = normalize_monthly(SalaryInfo(min=None, max=50, unit="hour"))
        assert (result.monthly_min, result.monthly_max) == (None, 8400)


class TestScoring:
    def test_must_haves_weigh_twice_as_much(self) -> None:
        matches = [
            RequirementMatch(name="Python", importance="must", status="met"),
            RequirementMatch(name="AWS", importance="nice", status="missing"),
        ]
        assert compute_score(matches) == pytest.approx(66.7)

    def test_partial_counts_as_half(self) -> None:
        matches = [RequirementMatch(name="Docker", importance="must", status="partial")]
        assert compute_score(matches) == 50.0

    def test_no_requirements(self) -> None:
        assert compute_score([]) == 0.0


class TestFakeExtraction:
    def test_reads_requirements_and_their_importance(self) -> None:
        extraction = extract_offer(OFFER_TEXT)
        importance = {r.name: r.importance for r in extraction.requirements}
        assert importance == {
            "Python": "must",
            "Django": "must",
            "PostgreSQL": "must",
            "SQL": "must",
            "Docker": "must",
            "Kubernetes": "nice",
            "AWS": "nice",
            "English B2": "must",
        }
        assert extraction.title == "Junior Python Developer"
        assert extraction.company == "Example Fintech"
        assert (extraction.seniority, extraction.work_mode) == ("junior", "remote")

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Salary 8000 - 12000 PLN / month, UoP", (8000, 12000, "month", "uop")),
            ("12 000 – 18 000 zł brutto / mies.", (12000, 18000, "month", "unknown")),
            ("Stawka 120-150 PLN/h na B2B", (120, 150, "hour", "b2b")),
            ("Up to 30k a year", None),
        ],
    )
    def test_salary_formats(
        self, text: str, expected: tuple[float, float, str, str] | None
    ) -> None:
        salary = extract_offer("Developer\n" + text).salary
        found = salary and (salary.min, salary.max, salary.unit, salary.contract)
        assert found == expected

    def test_reads_salary(self) -> None:
        salary = extract_offer(OFFER_TEXT).salary
        assert salary is not None
        assert (salary.min, salary.max, salary.unit, salary.contract) == (40, 60, "hour", "b2b")

    def test_longer_skill_names_win(self) -> None:
        names = [name for name, _ in find_skills("React Native, JavaScript and Spring Boot")]
        assert names == ["React Native", "JavaScript", "Spring Boot"]

    def test_hashed_embeddings_are_unit_vectors_and_similar_for_shared_words(self) -> None:
        a, b, c = (hashed_embedding(t) for t in ("Python Django", "Django REST", "Kubernetes"))

        def dot(x: list[float], y: list[float]) -> float:
            return sum(p * q for p, q in zip(x, y, strict=True))

        assert dot(a, a) == pytest.approx(1.0)
        assert dot(a, b) > dot(a, c)
