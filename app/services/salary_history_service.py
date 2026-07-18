"""
Salary History & Variable Pay Service — Phase 11.

Provides:
  - snapshot_salary()          : called by employee_service.save_employee() to
                                 capture the *current* salary before overwriting it.
  - get_salary_history()       : returns all historical snapshots for an employee.
  - upsert_variable_pay()      : replaces all variable-pay items for one
                                 (employee, period) pair atomically.
  - get_variable_pay_for_period(): used by payroll_service to inject items into engine.
  - delete_variable_pay_item() : removes a single item by id.
"""
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import Employee, SalaryStructure
from app.models.variable_pay import SalaryStructureHistory, VariablePayItem


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Salary history
# ---------------------------------------------------------------------------

def snapshot_salary(
    db: Session,
    salary: SalaryStructure,
    effective_from: date,
    created_by_user_id: Optional[int] = None,
) -> SalaryStructureHistory:
    """
    Persist an immutable copy of *salary* (and its dynamic components) as a
    new SalaryStructureHistory row.  Must be called *before* the caller
    overwrites the live SalaryStructure row.

    Any existing snapshot that has no superseded_at is marked superseded now.
    """
    # Mark previous open snapshot as superseded
    existing_open = (
        db.query(SalaryStructureHistory)
        .filter(
            SalaryStructureHistory.employee_id == salary.employee_id,
            SalaryStructureHistory.superseded_at.is_(None),
        )
        .first()
    )
    if existing_open is not None:
        existing_open.superseded_at = _utcnow()

    components_list = [
        {"type": c.component_type, "name": c.name, "amount": str(c.amount)}
        for c in salary.components
    ]

    snapshot = SalaryStructureHistory(
        employee_id=salary.employee_id,
        basic_pay=salary.basic_pay,
        hra=salary.hra,
        conveyance_allowance=salary.conveyance_allowance,
        components_json=json.dumps(components_list),
        effective_from=effective_from,
        created_by_user_id=created_by_user_id,
        superseded_at=_utcnow(),
    )
    db.add(snapshot)
    return snapshot


def get_salary_history(db: Session, employee_id: int) -> List[SalaryStructureHistory]:
    """Return all history rows, newest-first."""
    return (
        db.query(SalaryStructureHistory)
        .filter(SalaryStructureHistory.employee_id == employee_id)
        .order_by(SalaryStructureHistory.effective_from.desc(), SalaryStructureHistory.created_at.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# Variable pay
# ---------------------------------------------------------------------------

def upsert_variable_pay(
    db: Session,
    employee_id: int,
    period: date,
    items: List[dict],
    created_by_user_id: Optional[int] = None,
) -> None:
    """
    Replace all variable-pay items for (employee_id, period) with the
    supplied list.  Each dict in *items* must have keys:
        component_type: 'earning' | 'deduction'
        name: str
        amount: str | Decimal
    Blank-named rows are silently skipped.
    """
    # Delete existing items for this employee+period
    db.query(VariablePayItem).filter(
        VariablePayItem.employee_id == employee_id,
        VariablePayItem.period == period,
    ).delete(synchronize_session="fetch")

    for item in items:
        name = (item.get("name") or "").strip()
        if not name:
            continue
        db.add(
            VariablePayItem(
                employee_id=employee_id,
                period=period,
                component_type=item["component_type"],
                name=name,
                amount=Decimal(str(item["amount"])),
                created_by_user_id=created_by_user_id,
            )
        )


def get_variable_pay_for_period(
    db: Session, employee_id: int, period: date
) -> List[VariablePayItem]:
    """Return all variable-pay items for an (employee, period) pair."""
    return (
        db.query(VariablePayItem)
        .filter(
            VariablePayItem.employee_id == employee_id,
            VariablePayItem.period == period,
        )
        .order_by(VariablePayItem.component_type, VariablePayItem.name)
        .all()
    )


def delete_variable_pay_item(db: Session, item_id: int) -> bool:
    """Delete a single item by id. Returns True if found and deleted."""
    item = db.query(VariablePayItem).filter(VariablePayItem.id == item_id).first()
    if item is None:
        return False
    db.delete(item)
    return True
