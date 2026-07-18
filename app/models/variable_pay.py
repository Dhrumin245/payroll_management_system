"""
VariablePayItem model — one-off per-period bonuses or deductions that are
injected into the payroll engine without altering the standing salary structure.
"""
import json
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SalaryStructureHistory(Base):
    """
    Immutable snapshot of a salary structure, created automatically whenever
    a salary edit is saved.  Rows are never mutated after creation — only
    superseded_at is set (to a timestamp) when a newer revision arrives.
    """

    __tablename__ = "salary_structure_history"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    basic_pay = Column(Numeric(12, 2), nullable=False)
    hra = Column(Numeric(12, 2), nullable=False, default=0)
    conveyance_allowance = Column(Numeric(12, 2), nullable=False, default=0)
    # JSON list of {"type": ..., "name": ..., "amount": ...} dicts
    components_json = Column(Text, nullable=False, default="[]")
    effective_from = Column(Date, nullable=False)
    superseded_at = Column(DateTime, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    employee = relationship("Employee", back_populates="salary_history")
    created_by = relationship("User", foreign_keys=[created_by_user_id])

    # --------------- helpers -----------------------------------------------

    @property
    def components(self) -> list:
        """Deserialise the JSON blob back into a list of dicts."""
        return json.loads(self.components_json or "[]")

    def __repr__(self) -> str:
        return f"<SalaryStructureHistory employee_id={self.employee_id} from={self.effective_from}>"


class VariablePayItem(Base):
    """
    One-off bonus / reimbursement / deduction for a specific pay period.
    These are picked up by the payroll engine at run time and appear as
    extra line-item components on the payslip, labelled appropriately.
    """

    __tablename__ = "variable_pay_items"
    __table_args__ = (
        CheckConstraint("component_type IN ('earning', 'deduction')", name="ck_variable_pay_items_type"),
        CheckConstraint("amount >= 0", name="ck_variable_pay_items_amount"),
        UniqueConstraint("employee_id", "period", "name", name="uq_variable_pay_employee_period_name"),
    )

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    period = Column(Date, nullable=False)
    component_type = Column(String(10), nullable=False)  # 'earning' | 'deduction'
    name = Column(String(60), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    employee = relationship("Employee", back_populates="variable_pay_items")
    created_by = relationship("User", foreign_keys=[created_by_user_id])

    def __repr__(self) -> str:
        return f"<VariablePayItem {self.component_type} {self.name!r}={self.amount} period={self.period}>"
