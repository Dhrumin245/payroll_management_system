"""
Payroll run orchestration: readiness checks, calling the payroll engine for
every active employee, and persisting the results atomically. Kept separate
from the router (TRD §2's layered architecture) and from the pure
calculation logic in payroll_engine.py.
"""
from datetime import date, datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from app.models import Employee, PayrollLineItem, PayrollLineItemComponent, PayrollRun
from app.services.attendance_service import get_existing_record, is_period_locked
from app.services.payroll_engine import PayrollInput, SalaryComponentInput, calculate_payroll_run


def active_employees_missing_attendance(db: Session, period_date: date) -> List[Employee]:
    """Active employees who have no attendance record yet for this period."""
    active_employees = db.query(Employee).filter(Employee.status == "active").all()
    return [e for e in active_employees if get_existing_record(db, e.id, period_date) is None]


def period_already_run(db: Session, period_date: date) -> bool:
    return is_period_locked(db, period_date)


def run_payroll(db: Session, period_date: date, run_by_user_id: int) -> PayrollRun:
    """
    Computes and persists a full payroll run for `period_date`. The caller
    (the router) is expected to have already checked period_already_run()
    and active_employees_missing_attendance() for user-facing messaging --
    the checks repeated here are a defensive backstop, not the primary UX,
    per App Flow Screen 8's guards.

    Everything happens against one session with a single commit at the end.
    If anything raises partway through, the caller must roll back -- no
    partial run is ever committed (Implementation Plan's exit criteria for
    this phase).
    """
    if period_already_run(db, period_date):
        raise ValueError("Payroll for this period has already been processed.")

    active_employees = db.query(Employee).filter(Employee.status == "active").order_by(Employee.employee_code).all()
    if not active_employees:
        raise ValueError("No active employees to process.")

    payroll_inputs = []
    for employee in active_employees:
        attendance = get_existing_record(db, employee.id, period_date)
        if attendance is None:
            raise ValueError(f"Attendance is missing for {employee.full_name}.")

        salary = employee.salary_structure
        if salary is None:
            raise ValueError(f"{employee.full_name} has no salary structure configured.")

        components = [
            SalaryComponentInput(component_type=c.component_type, name=c.name, amount=c.amount)
            for c in salary.components
        ]

        payroll_inputs.append(
            PayrollInput(
                employee_id=employee.id,
                employee_code=employee.employee_code,
                employee_name=employee.full_name,
                basic_pay=salary.basic_pay,
                hra=salary.hra,
                conveyance_allowance=salary.conveyance_allowance,
                components=components,
                days_present=attendance.days_present,
                days_on_leave=attendance.days_on_leave,
                total_working_days=attendance.total_working_days,
            )
        )

    run_result = calculate_payroll_run(payroll_inputs)

    payroll_run = PayrollRun(
        period=period_date,
        run_date=datetime.now(timezone.utc),
        status="completed",
        total_gross=run_result.total_gross,
        total_deductions=run_result.total_deductions,
        total_net_pay=run_result.total_net_pay,
        employee_count=run_result.employee_count,
        run_by_user_id=run_by_user_id,
    )
    db.add(payroll_run)
    db.flush()  # populates payroll_run.id for the line items below

    for line_item_result in run_result.line_items:
        line_item = PayrollLineItem(
            payroll_run_id=payroll_run.id,
            employee_id=line_item_result.employee_id,
            employee_code_snapshot=line_item_result.employee_code,
            employee_name_snapshot=line_item_result.employee_name,
            days_present_snapshot=line_item_result.days_present,
            days_on_leave_snapshot=line_item_result.days_on_leave,
            gross_pay=line_item_result.gross_pay,
            total_deductions=line_item_result.total_deductions,
            net_pay=line_item_result.net_pay,
        )
        db.add(line_item)
        db.flush()  # populates line_item.id for its components below

        for component_result in line_item_result.line_components:
            db.add(
                PayrollLineItemComponent(
                    payroll_line_item_id=line_item.id,
                    component_type=component_result.component_type,
                    name=component_result.name,
                    amount=component_result.amount,
                )
            )

    db.commit()
    db.refresh(payroll_run)
    return payroll_run
