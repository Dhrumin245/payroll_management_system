"""
Dashboard summary data (App Flow Screen 2) -- kept separate from main.py so
the route stays thin, consistent with every other screen in the app.
"""
from sqlalchemy.orm import Session

from app.models import Employee, PayrollRun
from app.services.period_utils import format_period_label


def get_dashboard_data(db: Session) -> dict:
    active_employees = db.query(Employee).filter(Employee.status == "active").count()
    has_any_employees = db.query(Employee.id).first() is not None

    recent_runs = db.query(PayrollRun).order_by(PayrollRun.period.desc()).limit(5).all()
    last_run = recent_runs[0] if recent_runs else None

    return {
        "active_employees": active_employees,
        "has_any_employees": has_any_employees,
        "has_any_runs": bool(recent_runs),
        "last_run_period": format_period_label(last_run.period) if last_run else "—",
        "last_run_net_pay": f"₹{last_run.total_net_pay:,.2f}" if last_run else "—",
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
