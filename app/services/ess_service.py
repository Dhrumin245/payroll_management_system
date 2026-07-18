"""
Database query logic for the Employee Self-Service (ESS) Portal.
Allows employees to retrieve their own payslips and attendance records safely.
"""
from sqlalchemy.orm import Session
from app.models import PayrollLineItem, AttendanceRecord, PayrollRun


def get_my_payslips(db: Session, employee_id: int) -> list[PayrollLineItem]:
    """Retrieves all historical payroll line items for a given employee, ordered by period desc."""
    return (
        db.query(PayrollLineItem)
        .join(PayrollRun)
        .filter(PayrollLineItem.employee_id == employee_id)
        .order_by(PayrollRun.period.desc())
        .all()
    )


def get_my_attendance(db: Session, employee_id: int) -> list[AttendanceRecord]:
    """Retrieves all historical attendance records for a given employee, ordered by period desc."""
    return (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.employee_id == employee_id)
        .order_by(AttendanceRecord.period.desc())
        .all()
    )
