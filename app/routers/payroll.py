"""
Payroll routes: history list (Screen 7), new run (Screen 8), and run
summary (Screen 9's non-PDF portions -- payslip download and CSV export are
Phase 4d/5's job, once PDF generation exists).
"""
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.flash import flash
from app.models import Employee, PayrollLineItem, PayrollRun, User
from app.services.csrf import verify_csrf
from app.services.payroll_csv import generate_payroll_csv
from app.services.payroll_service import active_employees_missing_attendance, period_already_run, run_payroll
from app.services.payslip_pdf import generate_payslip_pdf
from app.services.period_utils import (
    InvalidPeriodError,
    current_period_string,
    format_period_label,
    parse_period,
    period_options,
)
from app.templating import render

router = APIRouter()


@router.get("/payroll")
def payroll_history(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """App Flow Screen 7."""
    runs = db.query(PayrollRun).order_by(PayrollRun.period.desc()).all()
    return render(
        request,
        "payroll/history.html",
        {"user": user, "active_nav": "payroll", "runs": runs, "has_any_runs": bool(runs)},
    )


@router.get("/payroll/new")
def new_payroll_run_form(
    request: Request, period: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """App Flow Screen 8. [Decision] Defaults to the current calendar month rather than
    scanning for the earliest un-run month -- simpler, and matches the common case of an
    admin running payroll for the current/most recent period."""
    if not period:
        period = current_period_string()
    try:
        period_date = parse_period(period)
    except InvalidPeriodError:
        raise HTTPException(status_code=404)

    active_count = db.query(Employee).filter(Employee.status == "active").count()
    missing_count = len(active_employees_missing_attendance(db, period_date))
    already_run = period_already_run(db, period_date)

    return render(
        request,
        "payroll/new_run.html",
        {
            "user": user,
            "active_nav": "payroll",
            "period": period,
            "period_label": format_period_label(period_date),
            "active_count": active_count,
            "missing_count": missing_count,
            "already_run": already_run,
            "period_options": period_options(),
        },
    )


@router.post("/payroll/run")
def trigger_payroll_run(
    request: Request,
    period: str = Form(...),
    csrf_token: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    verify_csrf(request, csrf_token)

    try:
        period_date = parse_period(period)
    except InvalidPeriodError:
        raise HTTPException(status_code=404)

    if period_already_run(db, period_date):
        flash(request, "Payroll for this period has already been processed.", "error")
        return RedirectResponse(url=f"/payroll/new?period={period}", status_code=status.HTTP_303_SEE_OTHER)

    missing = active_employees_missing_attendance(db, period_date)
    if missing:
        flash(
            request,
            f"Attendance is incomplete for {len(missing)} employee(s). "
            "Please complete attendance before running payroll.",
            "error",
        )
        return RedirectResponse(url=f"/attendance/{period}", status_code=status.HTTP_303_SEE_OTHER)

    try:
        payroll_run = run_payroll(db, period_date, run_by_user_id=user.id)
    except ValueError as exc:
        db.rollback()
        flash(request, str(exc), "error")
        return RedirectResponse(url=f"/payroll/new?period={period}", status_code=status.HTTP_303_SEE_OTHER)
    except Exception:
        db.rollback()
        flash(
            request,
            "Payroll run failed due to an unexpected error. No changes were made. Please try again.",
            "error",
        )
        return RedirectResponse(url=f"/payroll/new?period={period}", status_code=status.HTTP_303_SEE_OTHER)

    flash(request, f"Payroll run completed for {format_period_label(period_date)}.", "success")
    return RedirectResponse(url=f"/payroll/{payroll_run.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/payroll/{run_id}")
def payroll_run_summary(
    request: Request, run_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """App Flow Screen 9 (payslip download / CSV export arrive once PDF generation exists)."""
    payroll_run = db.query(PayrollRun).filter(PayrollRun.id == run_id).first()
    if payroll_run is None:
        raise HTTPException(status_code=404)

    line_items = (
        db.query(PayrollLineItem)
        .filter(PayrollLineItem.payroll_run_id == run_id)
        .order_by(PayrollLineItem.employee_code_snapshot)
        .all()
    )

    return render(
        request,
        "payroll/summary.html",
        {
            "user": user,
            "active_nav": "payroll",
            "run": payroll_run,
            "line_items": line_items,
            "period_label": format_period_label(payroll_run.period),
        },
    )


@router.get("/payroll/{run_id}/payslip/{employee_id}")
def download_payslip(
    request: Request,
    run_id: int,
    employee_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """App Flow Screen 10 -- a file response, not an HTML page."""
    payroll_run = db.query(PayrollRun).filter(PayrollRun.id == run_id).first()
    if payroll_run is None:
        raise HTTPException(status_code=404)

    line_item = (
        db.query(PayrollLineItem)
        .filter(PayrollLineItem.payroll_run_id == run_id, PayrollLineItem.employee_id == employee_id)
        .first()
    )
    if line_item is None:
        raise HTTPException(status_code=404)

    try:
        pdf_bytes = generate_payslip_pdf(line_item, format_period_label(payroll_run.period))
    except Exception:
        # App Flow Screen 9: the rest of the summary page stays usable even
        # if one payslip fails to generate.
        flash(request, f"Could not generate payslip for {line_item.employee_name_snapshot}. Please try again.", "error")
        return RedirectResponse(url=f"/payroll/{run_id}", status_code=status.HTTP_303_SEE_OTHER)

    filename = f"payslip_{line_item.employee_code_snapshot}_{payroll_run.period.strftime('%Y-%m')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/payroll/{run_id}/export")
def export_payroll_csv(
    run_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """App Flow Screen 9's optional stretch feature."""
    payroll_run = db.query(PayrollRun).filter(PayrollRun.id == run_id).first()
    if payroll_run is None:
        raise HTTPException(status_code=404)

    line_items = (
        db.query(PayrollLineItem)
        .filter(PayrollLineItem.payroll_run_id == run_id)
        .order_by(PayrollLineItem.employee_code_snapshot)
        .all()
    )

    csv_content = generate_payroll_csv(line_items)
    filename = f"payroll_{payroll_run.period.strftime('%Y-%m')}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
