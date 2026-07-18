"""
Employee Portal routes (Employee Self-Service).
"""
from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.flash import flash
from app.models import Employee, PayrollLineItem, PayrollRun, User
from app.services.ess_service import get_my_attendance, get_my_payslips
from app.services.payslip_pdf import generate_payslip_pdf
from app.services.period_utils import format_period_label
from app.templating import render

router = APIRouter()


@router.get("/portal")
def portal_dashboard(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """ESS Dashboard."""
    if user.role != "employee" or user.employee_id is None:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

    employee = db.query(Employee).filter(Employee.id == user.employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee record not found.")

    payslips = get_my_payslips(db, user.employee_id)
    last_payslip = payslips[0] if payslips else None

    return render(
        request,
        "portal/dashboard.html",
        {
            "user": user,
            "employee": employee,
            "last_payslip": last_payslip,
            "has_any_payslips": bool(payslips),
        },
    )


@router.get("/portal/payslips")
def portal_payslips(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """ESS List of Payslips."""
    if user.employee_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not linked to an employee record.")

    payslips = get_my_payslips(db, user.employee_id)
    return render(
        request,
        "portal/payslips.html",
        {
            "user": user,
            "payslips": payslips,
        },
    )


@router.get("/portal/payslips/{run_id}")
def download_my_payslip(
    request: Request,
    run_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """ESS Payslip PDF download."""
    if user.employee_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not linked to an employee record.")

    payroll_run = db.query(PayrollRun).filter(PayrollRun.id == run_id).first()
    if payroll_run is None:
        raise HTTPException(status_code=404)

    line_item = (
        db.query(PayrollLineItem)
        .filter(PayrollLineItem.payroll_run_id == run_id, PayrollLineItem.employee_id == user.employee_id)
        .first()
    )
    if line_item is None:
        raise HTTPException(status_code=403, detail="Access denied to this payslip.")

    try:
        pdf_bytes = generate_payslip_pdf(line_item, format_period_label(payroll_run.period))
    except Exception:
        flash(request, "Could not generate payslip. Please try again.", "error")
        return RedirectResponse(url="/portal/payslips", status_code=status.HTTP_303_SEE_OTHER)

    filename = f"payslip_{line_item.employee_code_snapshot}_{payroll_run.period.strftime('%Y-%m')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/portal/attendance")
def portal_attendance(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """ESS Attendance history."""
    if user.employee_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not linked to an employee record.")

    records = get_my_attendance(db, user.employee_id)
    
    # We can format the period dates to readable labels in the template, 
    # but let's pass formatted ones or rely on helper.
    formatted_records = [
        {
            "period_label": format_period_label(r.period),
            "days_present": str(r.days_present).rstrip(".0") if str(r.days_present).endswith(".0") else str(r.days_present),
            "days_on_leave": str(r.days_on_leave).rstrip(".0") if str(r.days_on_leave).endswith(".0") else str(r.days_on_leave),
            "total_working_days": str(r.total_working_days).rstrip(".0") if str(r.total_working_days).endswith(".0") else str(r.total_working_days),
        }
        for r in records
    ]

    return render(
        request,
        "portal/attendance.html",
        {
            "user": user,
            "records": formatted_records,
        },
    )


@router.get("/portal/profile")
def portal_profile(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """ESS Profile Details."""
    if user.employee_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not linked to an employee record.")

    employee = db.query(Employee).filter(Employee.id == user.employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee record not found.")

    # Mask account number for security
    bank_details = employee.bank_details
    masked_account = ""
    if bank_details and bank_details.account_number:
        # Bank account is encrypted; model decrypts it on read
        raw_number = bank_details.account_number
        if len(raw_number) > 4:
            masked_account = "*" * (len(raw_number) - 4) + raw_number[-4:]
        else:
            masked_account = raw_number

    return render(
        request,
        "portal/profile.html",
        {
            "user": user,
            "employee": employee,
            "masked_account_number": masked_account,
        },
    )


@router.get("/portal/leaves")
def portal_leaves(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """ESS Leaves history, balances, and request submission form."""
    if user.employee_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not linked to an employee record.")

    from app.services.leave_service import get_employee_leave_balances
    from app.models import LeaveType, LeaveRequest
    
    current_year = date.today().year
    balances = get_employee_leave_balances(db, user.employee_id, current_year)
    requests = db.query(LeaveRequest).filter(LeaveRequest.employee_id == user.employee_id).order_by(LeaveRequest.created_at.desc()).all()
    leave_types = db.query(LeaveType).order_by(LeaveType.name).all()

    return render(
        request,
        "portal/leaves.html",
        {
            "user": user,
            "balances": balances,
            "requests": requests,
            "leave_types": leave_types,
            "current_year": current_year,
        },
    )


@router.post("/portal/leaves/new")
def submit_portal_leave(
    request: Request,
    leave_type_id: int = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    reason: str = Form(""),
    csrf_token: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """ESS Leave Request Submission."""
    from app.services.csrf import verify_csrf
    verify_csrf(request, csrf_token)

    if user.employee_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not linked to an employee record.")

    from app.services.leave_service import create_leave_request
    from datetime import datetime
    
    try:
        start_date_val = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_val = datetime.strptime(end_date, "%Y-%m-%d").date()
    except Exception:
        flash(request, "Invalid date format. Use YYYY-MM-DD.", "error")
        return RedirectResponse(url="/portal/leaves", status_code=status.HTTP_303_SEE_OTHER)

    try:
        create_leave_request(db, user.employee_id, leave_type_id, start_date_val, end_date_val, reason=reason)
        flash(request, "Leave request submitted successfully and is pending approval.", "success")
    except ValueError as e:
        flash(request, str(e), "error")

    return RedirectResponse(url="/portal/leaves", status_code=status.HTTP_303_SEE_OTHER)
