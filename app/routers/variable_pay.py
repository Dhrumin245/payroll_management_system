from datetime import date
from typing import List
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db, require_manager_or_above
from app.flash import flash
from app.models import Employee, User
from app.services.attendance_service import (
    InvalidPeriodError,
    current_period_string,
    format_period_label,
    parse_period,
    period_options,
)
from app.services.csrf import verify_csrf
from app.services.salary_history_service import get_variable_pay_for_period, upsert_variable_pay
from app.templating import render

router = APIRouter()


@router.get("/employees/{employee_id}/variable-pay")
def view_variable_pay(
    request: Request,
    employee_id: int,
    period: str = "",
    user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    """View/add/edit variable pay items for a specific employee and period."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")

    if not period:
        period_str = current_period_string()
    else:
        period_str = period

    try:
        period_date = parse_period(period_str)
    except InvalidPeriodError:
        raise HTTPException(status_code=400, detail="Invalid period format")

    items = get_variable_pay_for_period(db, employee_id, period_date)

    return render(
        request,
        "employees/variable_pay.html",
        {
            "user": user,
            "active_nav": "employees",
            "employee": employee,
            "period": period_str,
            "period_label": format_period_label(period_date),
            "period_options": period_options(),
            "items": items,
        },
    )


@router.post("/employees/{employee_id}/variable-pay")
def save_variable_pay_items(
    request: Request,
    employee_id: int,
    period: str = Form(...),
    item_type: List[str] = Form(default=[]),
    item_name: List[str] = Form(default=[]),
    item_amount: List[str] = Form(default=[]),
    csrf_token: str = Form(...),
    user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    verify_csrf(request, csrf_token)

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")

    try:
        period_date = parse_period(period)
    except InvalidPeriodError:
        raise HTTPException(status_code=400, detail="Invalid period format")

    # Reconstruct items list
    items_to_save = []
    for t, name, amt in zip(item_type, item_name, item_amount):
        name_stripped = name.strip()
        if not name_stripped:
            continue
        try:
            val = float(amt) if amt else 0.0
            if val < 0:
                flash(request, f"Amount for '{name_stripped}' cannot be negative.", "danger")
                return RedirectResponse(
                    url=f"/employees/{employee_id}/variable-pay?period={period}",
                    status_code=status.HTTP_303_SEE_OTHER,
                )
        except ValueError:
            flash(request, f"Invalid amount format for '{name_stripped}'.", "danger")
            return RedirectResponse(
                url=f"/employees/{employee_id}/variable-pay?period={period}",
                status_code=status.HTTP_303_SEE_OTHER,
            )

        items_to_save.append({
            "component_type": t,
            "name": name_stripped,
            "amount": amt or "0.00"
        })

    upsert_variable_pay(db, employee_id, period_date, items_to_save, created_by_user_id=user.id)
    db.commit()

    flash(request, "Variable pay items updated successfully.", "success")
    return RedirectResponse(
        url=f"/employees/{employee_id}/variable-pay?period={period}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
