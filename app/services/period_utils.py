"""
Period string parsing/formatting/options, shared between Attendance and
Payroll -- both work in terms of 'YYYY-MM' periods (Backend Schema §3.6/3.7).
"""
from datetime import date


class InvalidPeriodError(ValueError):
    """Raised when a period string doesn't match the expected YYYY-MM format."""


def parse_period(period_str: str) -> date:
    """Parses 'YYYY-MM' into a date representing the 1st of that month."""
    try:
        year_str, month_str = period_str.split("-")
        year, month = int(year_str), int(month_str)
        if not (1 <= month <= 12) or not (2000 <= year <= 2100):
            raise ValueError
        return date(year, month, 1)
    except (ValueError, AttributeError) as exc:
        raise InvalidPeriodError(f"'{period_str}' is not a valid period (expected YYYY-MM).") from exc


def format_period_label(period_date: date) -> str:
    """e.g. date(2026, 7, 1) -> 'July 2026'."""
    return period_date.strftime("%B %Y")


def current_period_string() -> str:
    today = date.today()
    return f"{today.year:04d}-{today.month:02d}"


def period_options(months_back: int = 12, months_forward: int = 1) -> list:
    """A rolling window of (value, label) period options around today, newest first."""
    today = date.today()
    index = today.year * 12 + (today.month - 1)
    options = []
    for i in range(index + months_forward, index - months_back - 1, -1):
        year, month = divmod(i, 12)
        month += 1
        d = date(year, month, 1)
        options.append((f"{year:04d}-{month:02d}", format_period_label(d)))
    return options
