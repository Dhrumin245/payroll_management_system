"""
Analytics Router — Phase 14.

Exposes payroll history charts, headcount trends, and compensation breakdowns.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db, require_admin
from app.models import User
from app.services.dashboard_service import (
    get_payroll_trend,
    get_compensation_breakdown,
    get_headcount_trend,
)
from app.templating import render

router = APIRouter()


@router.get("/analytics")
def analytics_dashboard(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Renders the main analytics dashboard for admin/manager users."""
    if user.role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="Access denied")

    trend = get_payroll_trend(db)
    breakdown = get_compensation_breakdown(db)
    headcount = get_headcount_trend(db)

    return render(
        request,
        "analytics/index.html",
        {
            "user": user,
            "active_nav": "analytics",
            "payroll_trend": trend,
            "comp_breakdown": breakdown,
            "headcount_trend": headcount,
        },
    )


@router.get("/analytics/data/payroll-trend")
def analytics_payroll_trend_api(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """JSON API returning historical payroll spend trend."""
    if user.role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="Access denied")
    return get_payroll_trend(db)


@router.get("/analytics/data/headcount")
def analytics_headcount_api(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """JSON API returning historical active employee headcount trend."""
    if user.role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="Access denied")
    return get_headcount_trend(db)
