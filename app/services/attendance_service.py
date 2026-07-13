"""
Attendance period helpers and business logic, kept separate from the router
(TRD §2's layered architecture).
"""
import calendar
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy.orm import Session

from app.models import AttendanceRecord, PayrollRun
from app.services.period_utils import (  # noqa: F401 -- re-exported for existing callers (app/routers/attendance.py)
    InvalidPeriodError,
    current_period_string,
    format_period_label,
    parse_period,
    period_options,
)


def calculate_working_days(period_date: date) -> int:
    """
    [Decision] Auto-calculated as every day in the month except Sundays
    (6-day work week). No holiday calendar for MVP -- holidays are absorbed
    into "days on leave," entered manually. See the missing-details
    discussion this project's planning docs called out explicitly.
    """
    _, num_days = calendar.monthrange(period_date.year, period_date.month)
    return sum(
        1 for day in range(1, num_days + 1) if date(period_date.year, period_date.month, day).weekday() != 6
    )


def is_period_locked(db: Session, period_date: date) -> bool:
    """A period is locked once a completed payroll run exists for it (App Flow Screen 6)."""
    return (
        db.query(PayrollRun)
        .filter(PayrollRun.period == period_date, PayrollRun.status == "completed")
        .first()
        is not None
    )


def get_existing_record(db: Session, employee_id: int, period_date: date) -> Optional[AttendanceRecord]:
    return (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.employee_id == employee_id, AttendanceRecord.period == period_date)
        .first()
    )


def parse_attendance_number(
    value: str, errors: dict, key: str, allow_blank_as_zero: bool = False
) -> Optional[Decimal]:
    value = (value or "").strip()
    if not value:
        if allow_blank_as_zero:
            return Decimal("0")
        errors[key] = "Required."
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        errors[key] = "Enter a valid number."
        return None
    if parsed < 0:
        errors[key] = "Must be zero or greater."
        return None
    return parsed
