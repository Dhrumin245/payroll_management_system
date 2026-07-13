"""
Phase 6 checks: direct unit tests of attendance_service.py's validation and
calculation logic, independent of the HTTP layer -- closing the coverage
gap the Phase 5 report showed (70%, the lowest in services/). Run with: pytest
"""
from datetime import date
from decimal import Decimal

from app.services.attendance_service import calculate_working_days, parse_attendance_number


def test_parse_attendance_number_accepts_valid_value():
    errors = {}
    result = parse_attendance_number("22", errors, "present")
    assert result == Decimal("22")
    assert errors == {}


def test_parse_attendance_number_rejects_blank_by_default():
    errors = {}
    result = parse_attendance_number("", errors, "present")
    assert result is None
    assert errors["present"] == "Required."


def test_parse_attendance_number_allows_blank_as_zero_when_requested():
    errors = {}
    result = parse_attendance_number("", errors, "leave", allow_blank_as_zero=True)
    assert result == Decimal("0")
    assert errors == {}


def test_parse_attendance_number_rejects_non_numeric_input():
    errors = {}
    result = parse_attendance_number("not-a-number", errors, "present")
    assert result is None
    assert errors["present"] == "Enter a valid number."


def test_parse_attendance_number_rejects_negative_values():
    errors = {}
    result = parse_attendance_number("-5", errors, "present")
    assert result is None
    assert errors["present"] == "Must be zero or greater."


def test_parse_attendance_number_accepts_half_days():
    errors = {}
    result = parse_attendance_number("21.5", errors, "present")
    assert result == Decimal("21.5")
    assert errors == {}


def test_calculate_working_days_february_non_leap_year():
    # 2026 is not a leap year -- 28 days in February.
    working_days = calculate_working_days(date(2026, 2, 1))
    assert 0 < working_days <= 28


def test_calculate_working_days_february_leap_year():
    # 2028 is a leap year -- 29 days in February, one more potential working day than 2026.
    working_days_2026 = calculate_working_days(date(2026, 2, 1))
    working_days_2028 = calculate_working_days(date(2028, 2, 1))
    assert working_days_2028 >= working_days_2026


def test_calculate_working_days_excludes_only_sundays():
    """[Decision] documented in attendance_service.py: 6-day work week, Sundays only excluded."""
    # December 2026: 31 days. Confirm the count matches days-minus-Sundays exactly.
    import calendar

    year, month = 2026, 12
    _, num_days = calendar.monthrange(year, month)
    sundays = sum(1 for day in range(1, num_days + 1) if date(year, month, day).weekday() == 6)
    saturdays = sum(1 for day in range(1, num_days + 1) if date(year, month, day).weekday() == 5)

    working_days = calculate_working_days(date(year, month, 1))
    assert working_days == num_days - sundays  # Sundays excluded
    assert saturdays > 0 and working_days != num_days - sundays - saturdays  # Saturdays NOT excluded
