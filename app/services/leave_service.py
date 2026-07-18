"""
Leave Management service layer (LMS).
Handles approval, rejection, balance tracking, and attendance sync for employee leaves.
"""
import calendar
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models import LeaveRequest, LeaveBalance, LeaveType, AttendanceRecord, Employee
from app.services.attendance_service import calculate_working_days, is_period_locked, get_existing_record


def get_pending_requests(db: Session) -> list[LeaveRequest]:
    """Retrieves all pending leave requests, ordered by creation date asc."""
    return db.query(LeaveRequest).filter(LeaveRequest.status == "pending").order_by(LeaveRequest.created_at.asc()).all()


def get_employee_leave_balances(db: Session, employee_id: int, year: int) -> list[dict]:
    """
    Retrieves all leave types and the employee's remaining/used balances for a given year.
    If a balance row doesn't exist, we assume 0 days used.
    """
    leave_types = db.query(LeaveType).all()
    balances = db.query(LeaveBalance).filter(LeaveBalance.employee_id == employee_id, LeaveBalance.year == year).all()
    balances_map = {b.leave_type_id: b.days_used for b in balances}

    result = []
    for lt in leave_types:
        days_used = balances_map.get(lt.id, Decimal("0.0"))
        max_days = lt.max_days_per_year
        remaining = max_days - days_used if max_days is not None else None
        result.append({
            "leave_type": lt,
            "days_used": days_used,
            "max_days": max_days,
            "remaining": remaining
        })
    return result


def create_leave_request(
    db: Session, employee_id: int, leave_type_id: int, start_date: date, end_date: date, reason: str = None
) -> LeaveRequest:
    """Creates a new leave request in 'pending' status after basic validation."""
    if start_date > end_date:
        raise ValueError("Start date must be on or before end date.")

    # Validate that employee doesn't have an overlapping pending/approved leave request
    overlapping = (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status.in_(["pending", "approved"]),
            or_(
                and_(LeaveRequest.start_date <= start_date, LeaveRequest.end_date >= start_date),
                and_(LeaveRequest.start_date <= end_date, LeaveRequest.end_date >= end_date),
                and_(LeaveRequest.start_date >= start_date, LeaveRequest.end_date <= end_date)
            )
        )
        .first()
    )
    if overlapping:
        raise ValueError("You have an overlapping leave request for this date range.")

    req = LeaveRequest(
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
        status="pending"
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def count_working_leave_days(start_date: date, end_date: date, month_start: date, month_end: date) -> Decimal:
    """Counts non-Sunday calendar days in the overlap range."""
    overlap_start = max(start_date, month_start)
    overlap_end = min(end_date, month_end)

    if overlap_start > overlap_end:
        return Decimal("0.0")

    days = 0
    curr = overlap_start
    while curr <= overlap_end:
        if curr.weekday() != 6:  # Skip Sundays
            days += 1
        curr += timedelta(days=1)
    return Decimal(days)


def approve_leave_request(db: Session, request_id: int, approver_user_id: int) -> LeaveRequest:
    """Approves a leave request, updating status, approver meta, and incrementing leave balances."""
    req = db.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()
    if not req:
        raise ValueError("Leave request not found.")
    if req.status != "pending":
        raise ValueError(f"Request cannot be approved from '{req.status}' status.")

    # Calculate total working leave days in this request's range across years (usually single year)
    years = {req.start_date.year, req.end_date.year}
    for year in years:
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        total_days = count_working_leave_days(req.start_date, req.end_date, year_start, year_end)

        if total_days > 0:
            # Check leave type limits
            lt = req.leave_type
            if lt.max_days_per_year is not None:
                bal = (
                    db.query(LeaveBalance)
                    .filter(LeaveBalance.employee_id == req.employee_id, LeaveBalance.leave_type_id == lt.id, LeaveBalance.year == year)
                    .first()
                )
                current_used = bal.days_used if bal else Decimal("0.0")
                if current_used + total_days > lt.max_days_per_year:
                    raise ValueError(f"Leave limit exceeded for {lt.name}. Current used: {current_used}, requested: {total_days}, max: {lt.max_days_per_year}.")

                if bal is None:
                    bal = LeaveBalance(employee_id=req.employee_id, leave_type_id=lt.id, year=year, days_used=Decimal("0.0"))
                    db.add(bal)
                bal.days_used += total_days

    req.status = "approved"
    req.approved_by_user_id = approver_user_id
    req.approved_at = datetime.now(timezone.utc)
    
    db.commit()
    
    # Auto-sync attendance for any months touched by this request
    start_period = date(req.start_date.year, req.start_date.month, 1)
    end_period = date(req.end_date.year, req.end_date.month, 1)
    
    curr = start_period
    while curr <= end_period:
        sync_attendance_from_leaves(db, curr)
        # Move to next month
        if curr.month == 12:
            curr = date(curr.year + 1, 1, 1)
        else:
            curr = date(curr.year, curr.month + 1, 1)

    db.commit()
    db.refresh(req)
    return req


def reject_leave_request(db: Session, request_id: int, approver_user_id: int, reason: str = None) -> LeaveRequest:
    """Rejects a leave request."""
    req = db.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()
    if not req:
        raise ValueError("Leave request not found.")
    if req.status != "pending":
        raise ValueError(f"Request cannot be rejected from '{req.status}' status.")

    req.status = "rejected"
    req.approved_by_user_id = approver_user_id
    req.approved_at = datetime.now(timezone.utc)
    if reason:
        # Append rejection reason to request description/reason or keep in memory
        req.reason = f"{req.reason or ''} (Rejection reason: {reason})".strip()

    db.commit()
    db.refresh(req)
    return req


def sync_attendance_from_leaves(db: Session, period_date: date) -> None:
    """
    Syncs approved leave records overlapping the month of `period_date`
    into the `AttendanceRecord` table. If the period is locked, does nothing.
    """
    if is_period_locked(db, period_date):
        return

    _, num_days = calendar.monthrange(period_date.year, period_date.month)
    month_start = date(period_date.year, period_date.month, 1)
    month_end = date(period_date.year, period_date.month, num_days)

    working_days = calculate_working_days(period_date)
    active_employees = db.query(Employee).filter(Employee.status == "active").all()

    for emp in active_employees:
        # Sum non-Sunday leave days for all approved leaves overlapping this month
        leaves = (
            db.query(LeaveRequest)
            .filter(
                LeaveRequest.employee_id == emp.id,
                LeaveRequest.status == "approved",
                LeaveRequest.start_date <= month_end,
                LeaveRequest.end_date >= month_start
            )
            .all()
        )

        total_leave_days = Decimal("0.0")
        for leave in leaves:
            total_leave_days += count_working_leave_days(leave.start_date, leave.end_date, month_start, month_end)

        # Retrieve or create attendance record
        record = get_existing_record(db, emp.id, period_date)
        if record is None:
            if total_leave_days > 0:
                record = AttendanceRecord(
                    employee_id=emp.id,
                    period=period_date,
                    days_on_leave=total_leave_days,
                    days_present=Decimal(working_days) - total_leave_days,
                    total_working_days=working_days
                )
                db.add(record)
        else:
            record.days_on_leave = total_leave_days
            # Enforce constraints: days_present + days_on_leave <= total_working_days
            if record.days_present + total_leave_days > working_days:
                record.days_present = Decimal(working_days) - total_leave_days
            record.total_working_days = working_days
