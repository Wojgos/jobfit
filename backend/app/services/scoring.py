from collections.abc import Iterable

from app.schemas.analysis import RequirementMatch

IMPORTANCE_WEIGHT = {"must": 2.0, "nice": 1.0}
STATUS_VALUE = {"met": 1.0, "partial": 0.5, "missing": 0.0}


def compute_score(matches: Iterable[RequirementMatch]) -> float:
    """Weighted share of satisfied requirements, 0-100.

    Must-haves count twice as much as nice-to-haves; a partial match counts as half.
    """
    total = earned = 0.0
    for match in matches:
        weight = IMPORTANCE_WEIGHT[match.importance]
        total += weight
        earned += weight * STATUS_VALUE[match.status]
    return round(100 * earned / total, 1) if total else 0.0
