from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.flash import flash
from app.models import AttendanceRecord, Employee, User
from app.services.attendance_service import (
    InvalidPeriodError,
    calculate_working_days,
    current_period_string,
    format_period_label,
    get_existing_record,
    is_period_locked,
    parse_attendance_number,
    parse_period,
    period_options,
)
from app.services.csrf import verify_csrf
from app.templating import render

router = APIRouter()


@router.get("/attendance")
def attendance_redirect(user: User = Depends(get_current_user)):
    """Nav link / Dashboard shortcut both default to the current calendar month (App Flow)."""
    return RedirectResponse(url=f"/attendance/{current_period_string()}", status_code=status.HTTP_303_SEE_OTHER)


def _build_rows(
    db: Session, active_employees: list, period_date: date, submitted: Optional[dict] = None
) -> list:
    """
    One row per active employee. If `submitted` is given (employee_id ->
    (present_str, leave_str)), those values win over the DB -- used to
    re-render exactly what was typed after a validation error, per App Flow.
    """
    rows = []
    for employee in active_employees:
        if submitted and employee.id in submitted:
            present_str, leave_str = submitted[employee.id]
            saved = False
        else:
            existing = get_existing_record(db, employee.id, period_date)
            present_str = str(existing.days_present) if existing else ""
            # Ensure days_present/leave render as plain values for tests (e.g. 22 -> "22").
            # SQLAlchemy Numeric values can sometimes stringify with trailing zeros.
            if existing and present_str.endswith(".0"):
                present_str = present_str[: -2]
            leave_str = str(existing.days_on_leave) if existing else "0"
            if existing and leave_str.endswith(".0"):
                leave_str = leave_str[: -2]
            saved = existing is not None
        rows.append(
            {"employee": employee, "days_present": present_str, "days_on_leave": leave_str, "saved": saved}
        )
    return rows


@router.get("/attendance/{period}")
def attendance_entry_form(
    request: Request, period: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """App Flow Screen 6."""
    try:
        period_date = parse_period(period)
    except InvalidPeriodError:
        raise HTTPException(status_code=404)

    active_employees = db.query(Employee).filter(Employee.status == "active").order_by(Employee.employee_code).all()
    working_days = calculate_working_days(period_date)
    locked = is_period_locked(db, period_date)
    rows = _build_rows(db, active_employees, period_date)

    return render(
        request,
        "attendance/entry.html",
        {
            "user": user,
            "active_nav": "attendance",
            "period": period,
            "period_label": format_period_label(period_date),
            "working_days": working_days,
            "locked": locked,
            "rows": rows,
            "has_active_employees": bool(active_employees),
            "errors": {},
            "period_options": period_options(),
        },
    )


@router.post("/attendance/{period}")
def save_attendance(
    request: Request,
    period: str,
    employee_id: List[int] = Form(default=[]),
    days_present: List[str] = Form(default=[]),
    days_on_leave: List[str] = Form(default=[]),
    csrf_token: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    verify_csrf(request, csrf_token)

    try:
        period_date = parse_period(period)
    except InvalidPeriodError:
        raise HTTPException(status_code=404)

    if is_period_locked(db, period_date):
        flash(request, "Payroll has already been run for this period. Attendance is locked.", "error")
        return RedirectResponse(url=f"/attendance/{period}", status_code=status.HTTP_303_SEE_OTHER)

    working_days = calculate_working_days(period_date)
    active_employees = db.query(Employee).filter(Employee.status == "active").order_by(Employee.employee_code).all()

    errors: dict = {}
    parsed: dict = {}
    submitted: dict = {}
    for emp_id, present_str, leave_str in zip(employee_id, days_present, days_on_leave):
        submitted[emp_id] = (present_str, leave_str)
        present = parse_attendance_number(present_str, errors, f"present_{emp_id}")
        leave = parse_attendance_number(leave_str, errors, f"leave_{emp_id}", allow_blank_as_zero=True)
        if present is not None and leave is not None and (present + leave) > working_days:
            errors[f"row_{emp_id}"] = (
                f"Days present + leave cannot exceed {working_days} working days for this period."
            )
        parsed[emp_id] = (present, leave)

    if errors:
        rows = _build_rows(db, active_employees, period_date, submitted=submitted)
        return render(
            request,
            "attendance/entry.html",
            {
                "user": user,
                "active_nav": "attendance",
                "period": period,
                "period_label": format_period_label(period_date),
                "working_days": working_days,
                "locked": False,
                "rows": rows,
                "has_active_employees": bool(active_employees),
                "errors": errors,
                "period_options": period_options(),
            },
            status_code=400,
        )

    try:
        for emp_id, (present, leave) in parsed.items():
            record = get_existing_record(db, emp_id, period_date)
            if record is None:
                record = AttendanceRecord(employee_id=emp_id, period=period_date, total_working_days=working_days)
                db.add(record)
            record.days_present = present
            record.days_on_leave = leave
            record.total_working_days = working_days
        db.commit()
    except IntegrityError:
        db.rollback()
        flash(request, "Could not save attendance — please check the entered values and try again.", "error")
        return RedirectResponse(url=f"/attendance/{period}", status_code=status.HTTP_303_SEE_OTHER)

    flash(request, f"Attendance saved for {format_period_label(period_date)}.", "success")
    return RedirectResponse(url=f"/attendance/{period}", status_code=status.HTTP_303_SEE_OTHER)
