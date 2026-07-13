from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.flash import flash
from app.models import Employee, User
from app.services.csrf import verify_csrf
from app.services.employee_service import (
    EmployeeFormData,
    components_from_submission,
    existing_components_for_template,
    field_values_from_employee,
    field_values_from_form_data,
    save_employee,
    suggest_employee_code,
    validate_employee_form,
)
from app.templating import render

router = APIRouter()


@router.get("/employees")
def list_employees(
    request: Request,
    search: str = "",
    status_filter: str = "active",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """App Flow Screen 3."""
    has_any_employees = db.query(Employee.id).first() is not None

    query = db.query(Employee)
    if status_filter in ("active", "inactive"):
        query = query.filter(Employee.status == status_filter)
    if search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(Employee.full_name.ilike(term), Employee.employee_code.ilike(term)))
    employees = query.order_by(Employee.employee_code).all()

    return render(
        request,
        "employees/list.html",
        {
            "user": user,
            "active_nav": "employees",
            "employees": employees,
            "search": search,
            "status_filter": status_filter,
            "has_any_employees": has_any_employees,
        },
    )


@router.get("/employees/new")
def new_employee_form(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """App Flow Screen 4."""
    suggested_code = suggest_employee_code(db)
    return render(
        request,
        "employees/form.html",
        {
            "user": user,
            "active_nav": "employees",
            "mode": "create",
            "employee": None,
            "errors": {},
            "field_values": field_values_from_employee(None, suggested_code=suggested_code),
            "existing_components": [],
        },
    )


@router.post("/employees/new")
def create_employee(
    request: Request,
    full_name: str = Form(""),
    employee_code: str = Form(""),
    designation: str = Form(""),
    joining_date: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    account_holder_name: str = Form(""),
    account_number: str = Form(""),
    ifsc_code: str = Form(""),
    bank_name: str = Form(""),
    basic_pay: str = Form(""),
    hra: str = Form(""),
    conveyance_allowance: str = Form(""),
    component_type: List[str] = Form(default=[]),
    component_name: List[str] = Form(default=[]),
    component_amount: List[str] = Form(default=[]),
    csrf_token: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    verify_csrf(request, csrf_token)

    data = EmployeeFormData(
        full_name=full_name,
        employee_code=employee_code,
        designation=designation,
        joining_date=joining_date,
        email=email,
        phone=phone,
        account_holder_name=account_holder_name,
        account_number=account_number,
        ifsc_code=ifsc_code,
        bank_name=bank_name,
        basic_pay=basic_pay,
        hra=hra,
        conveyance_allowance=conveyance_allowance,
        component_types=component_type,
        component_names=component_name,
        component_amounts=component_amount,
    )
    errors = validate_employee_form(db, data)

    if errors:
        return render(
            request,
            "employees/form.html",
            {
                "user": user,
                "active_nav": "employees",
                "mode": "create",
                "employee": None,
                "errors": errors,
                "field_values": field_values_from_form_data(data),
                "existing_components": components_from_submission(data),
            },
            status_code=400,
        )

    employee = save_employee(db, data)
    flash(request, "Employee added successfully.", "success")
    return RedirectResponse(url=f"/employees/{employee.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/employees/{employee_id}")
def employee_detail(
    request: Request,
    employee_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """App Flow Screen 5."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404)

    return render(
        request,
        "employees/form.html",
        {
            "user": user,
            "active_nav": "employees",
            "mode": "edit",
            "employee": employee,
            "errors": {},
            "field_values": field_values_from_employee(employee),
            "existing_components": existing_components_for_template(employee),
        },
    )


@router.post("/employees/{employee_id}")
def update_employee(
    request: Request,
    employee_id: int,
    full_name: str = Form(""),
    employee_code: str = Form(""),
    designation: str = Form(""),
    joining_date: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    account_holder_name: str = Form(""),
    account_number: str = Form(""),
    ifsc_code: str = Form(""),
    bank_name: str = Form(""),
    basic_pay: str = Form(""),
    hra: str = Form(""),
    conveyance_allowance: str = Form(""),
    component_type: List[str] = Form(default=[]),
    component_name: List[str] = Form(default=[]),
    component_amount: List[str] = Form(default=[]),
    csrf_token: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    verify_csrf(request, csrf_token)

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404)

    data = EmployeeFormData(
        full_name=full_name,
        employee_code=employee_code,
        designation=designation,
        joining_date=joining_date,
        email=email,
        phone=phone,
        account_holder_name=account_holder_name,
        account_number=account_number,
        ifsc_code=ifsc_code,
        bank_name=bank_name,
        basic_pay=basic_pay,
        hra=hra,
        conveyance_allowance=conveyance_allowance,
        component_types=component_type,
        component_names=component_name,
        component_amounts=component_amount,
    )
    errors = validate_employee_form(db, data, existing_employee_id=employee_id)

    if errors:
        return render(
            request,
            "employees/form.html",
            {
                "user": user,
                "active_nav": "employees",
                "mode": "edit",
                "employee": employee,
                "errors": errors,
                "field_values": field_values_from_form_data(data),
                "existing_components": components_from_submission(data),
            },
            status_code=400,
        )

    save_employee(db, data, employee=employee)
    flash(request, "Employee updated successfully.", "success")
    return RedirectResponse(url=f"/employees/{employee_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/employees/{employee_id}/deactivate")
def deactivate_employee(
    request: Request,
    employee_id: int,
    csrf_token: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """App Flow §3.11. NOTE: the guard against deactivating an employee with
    unpaid attendance for a completed-but-unrun period is deferred until
    Phase 4b/4c actually introduce attendance and payroll runs -- there's no
    way for that situation to exist yet."""
    verify_csrf(request, csrf_token)

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404)

    employee.status = "inactive"
    employee.deactivated_at = datetime.now(timezone.utc)
    db.commit()
    flash(request, "Employee deactivated.", "success")

    return RedirectResponse(
        url=request.headers.get("referer", f"/employees/{employee_id}"), status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/employees/{employee_id}/reactivate")
def reactivate_employee(
    request: Request,
    employee_id: int,
    csrf_token: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    verify_csrf(request, csrf_token)

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404)

    employee.status = "active"
    employee.deactivated_at = None
    db.commit()
    flash(request, "Employee reactivated.", "success")

    return RedirectResponse(
        url=request.headers.get("referer", f"/employees/{employee_id}"), status_code=status.HTTP_303_SEE_OTHER
    )
