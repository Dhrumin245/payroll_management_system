"""
Leave Management admin/manager routes.
"""
from decimal import Decimal
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_manager_or_above, require_admin
from app.flash import flash
from app.models import User, LeaveRequest, LeaveType
from app.services.csrf import verify_csrf
from app.services.leave_service import get_pending_requests, approve_leave_request, reject_leave_request
from app.templating import render

router = APIRouter()


@router.get("/leaves")
def list_leaves(
    request: Request,
    user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db)
):
    """LMS screen showing pending requests for managers/admins to action, and historical requests."""
    pending = get_pending_requests(db)
    all_requests = db.query(LeaveRequest).order_by(LeaveRequest.created_at.desc()).all()
    
    return render(
        request,
        "leaves/pending.html",
        {
            "user": user,
            "active_nav": "leaves",
            "pending": pending,
            "all_requests": all_requests,
        }
    )


@router.post("/leaves/{id}/approve")
def approve_request_route(
    id: int,
    request: Request,
    csrf_token: str = Form(...),
    user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db)
):
    verify_csrf(request, csrf_token)
    try:
        approve_leave_request(db, id, user.id)
        flash(request, "Leave request approved and synced to attendance.", "success")
    except ValueError as e:
        flash(request, str(e), "error")
        
    return RedirectResponse(url="/leaves", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/leaves/{id}/reject")
def reject_request_route(
    id: int,
    request: Request,
    csrf_token: str = Form(...),
    reason: str = Form(""),
    user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db)
):
    verify_csrf(request, csrf_token)
    try:
        reject_leave_request(db, id, user.id, reason=reason)
        flash(request, "Leave request rejected.", "info")
    except ValueError as e:
        flash(request, str(e), "error")
        
    return RedirectResponse(url="/leaves", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/leaves/types")
def configure_leave_types(
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Admin configuration page for leave types."""
    types = db.query(LeaveType).order_by(LeaveType.name).all()
    return render(
        request,
        "leaves/types.html",
        {
            "user": user,
            "active_nav": "settings",
            "leave_types": types,
        }
    )


@router.post("/leaves/types/new")
def create_leave_type_route(
    request: Request,
    name: str = Form(...),
    max_days: str = Form(None),
    is_paid: bool = Form(True),
    csrf_token: str = Form(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    verify_csrf(request, csrf_token)
    
    # Validation
    if not name.strip():
        flash(request, "Leave type name is required.", "error")
        return RedirectResponse(url="/leaves/types", status_code=status.HTTP_303_SEE_OTHER)
        
    max_days_val = None
    if max_days and max_days.strip():
        try:
            max_days_val = Decimal(max_days.strip())
            if max_days_val <= 0:
                flash(request, "Entitlement must be greater than zero.", "error")
                return RedirectResponse(url="/leaves/types", status_code=status.HTTP_303_SEE_OTHER)
        except Exception:
            flash(request, "Entitlement must be a number.", "error")
            return RedirectResponse(url="/leaves/types", status_code=status.HTTP_303_SEE_OTHER)

    if db.query(LeaveType).filter(LeaveType.name == name.strip()).first():
        flash(request, f"Leave type '{name}' already exists.", "error")
        return RedirectResponse(url="/leaves/types", status_code=status.HTTP_303_SEE_OTHER)

    lt = LeaveType(name=name.strip(), max_days_per_year=max_days_val, is_paid=is_paid)
    db.add(lt)
    db.commit()
    
    flash(request, f"Leave type '{lt.name}' configured.", "success")
    return RedirectResponse(url="/leaves/types", status_code=status.HTTP_303_SEE_OTHER)
