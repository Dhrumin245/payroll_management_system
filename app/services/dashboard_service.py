"""
Dashboard summary data (App Flow Screen 2) — enhanced in Phase 14 with
trend analysis and compensation breakdown aggregations for charts.
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Employee, PayrollRun, PayrollLineItem, PayrollLineItemComponent
from app.services.period_utils import format_period_label


def get_dashboard_data(db: Session) -> dict:
    active_employees = db.query(Employee).filter(Employee.status == "active").count()
    has_any_employees = db.query(Employee.id).first() is not None

    recent_runs = db.query(PayrollRun).order_by(PayrollRun.period.desc()).limit(5).all()
    last_run = recent_runs[0] if recent_runs else None

    # Prior month comparison for delta indicators
    prior_run = recent_runs[1] if len(recent_runs) >= 2 else None
    net_pay_delta = None
    if last_run and prior_run and prior_run.total_net_pay > 0:
        change = last_run.total_net_pay - prior_run.total_net_pay
        pct = (change / prior_run.total_net_pay) * 100
        net_pay_delta = {
            "change": float(change),
            "pct": round(float(pct), 1),
            "direction": "up" if change > 0 else ("down" if change < 0 else "flat"),
        }

    return {
        "active_employees": active_employees,
        "has_any_employees": has_any_employees,
        "has_any_runs": bool(recent_runs),
        "last_run_period": format_period_label(last_run.period) if last_run else "—",
        "last_run_net_pay": f"₹{last_run.total_net_pay:,.2f}" if last_run else "—",
        "net_pay_delta": net_pay_delta,
        "recent_runs": [
            {
                "id": r.id,
                "period": format_period_label(r.period),
                "run_date": r.run_date.strftime("%Y-%m-%d"),
                "employees": r.employee_count,
                "net_pay": f"₹{r.total_net_pay:,.2f}",
            }
            for r in recent_runs
        ],
    }


def get_payroll_trend(db: Session, months: int = 12) -> List[dict]:
    """Returns last N months of payroll data for trend charts."""
    runs = (
        db.query(PayrollRun)
        .order_by(PayrollRun.period.desc())
        .limit(months)
        .all()
    )
    # Reverse for chronological order (oldest first)
    runs.reverse()
    return [
        {
            "period": format_period_label(r.period),
            "period_raw": r.period.strftime("%Y-%m"),
            "total_gross": float(r.total_gross),
            "total_deductions": float(r.total_deductions),
            "total_net_pay": float(r.total_net_pay),
            "employee_count": r.employee_count,
        }
        for r in runs
    ]


def get_compensation_breakdown(db: Session) -> dict:
    """Returns average compensation breakdown for the latest payroll run."""
    latest_run = db.query(PayrollRun).order_by(PayrollRun.period.desc()).first()
    if not latest_run:
        return {"period": None, "categories": [], "values": []}

    line_items = (
        db.query(PayrollLineItem)
        .filter(PayrollLineItem.payroll_run_id == latest_run.id)
        .all()
    )

    # Aggregate component totals by name across all employees
    component_totals: dict[str, float] = {}
    for item in line_items:
        for comp in item.components:
            key = comp.name
            component_totals[key] = component_totals.get(key, 0.0) + float(comp.amount)

    # Sort by total (descending) and take top 8 for a clean chart
    sorted_items = sorted(component_totals.items(), key=lambda x: x[1], reverse=True)
    top_items = sorted_items[:8]
    if len(sorted_items) > 8:
        other_total = sum(v for _, v in sorted_items[8:])
        top_items.append(("Other", other_total))

    return {
        "period": format_period_label(latest_run.period),
        "categories": [item[0] for item in top_items],
        "values": [round(item[1], 2) for item in top_items],
    }


def get_headcount_trend(db: Session, months: int = 12) -> List[dict]:
    """Returns monthly active employee counts from payroll runs."""
    runs = (
        db.query(PayrollRun)
        .order_by(PayrollRun.period.desc())
        .limit(months)
        .all()
    )
    runs.reverse()
    return [
        {
            "period": format_period_label(r.period),
            "period_raw": r.period.strftime("%Y-%m"),
            "employee_count": r.employee_count,
        }
        for r in runs
    ]
