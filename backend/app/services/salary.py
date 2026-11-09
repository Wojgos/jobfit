from app.schemas.analysis import NormalizedSalary, SalaryInfo

HOURS_PER_MONTH = 168
DAYS_PER_MONTH = 21

_FACTORS: dict[str, tuple[float, str]] = {
    "hour": (HOURS_PER_MONTH, f"x {HOURS_PER_MONTH} h"),
    "day": (DAYS_PER_MONTH, f"x {DAYS_PER_MONTH} days"),
    "month": (1, "per month"),
    "year": (1 / 12, "/ 12 months"),
}


def normalize_monthly(salary: SalaryInfo) -> NormalizedSalary:
    """Express any salary range as a monthly amount so offers can be compared.

    Uses full-time assumptions (168 h or 21 working days a month). Taxes and the
    B2B vs employment-contract difference are not modelled - the contract type is
    passed through so the user can judge it.
    """
    factor, basis = _FACTORS[salary.unit]

    def convert(value: float | None) -> int | None:
        return None if value is None else round(value * factor)

    low, high = salary.min, salary.max
    if low is not None and high is not None and low > high:
        low, high = high, low
    return NormalizedSalary(
        monthly_min=convert(low),
        monthly_max=convert(high),
        currency=salary.currency,
        contract=salary.contract,
        basis=f"{salary.unit} {basis}",
    )
