from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SalaryStructure(Base):
    """
    Current salary structure per employee (Backend Schema §3.4). One row per
    employee (1:1) — a salary change updates this row in place; history is
    preserved through the payroll snapshot tables instead, not here.
    """

    __tablename__ = "salary_structures"
    __table_args__ = (CheckConstraint("basic_pay > 0", name="ck_salary_structures_basic_pay_positive"),)

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), unique=True, nullable=False)
    basic_pay = Column(Numeric(12, 2), nullable=False)
    hra = Column(Numeric(12, 2), nullable=False, default=0)
    conveyance_allowance = Column(Numeric(12, 2), nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    employee = relationship("Employee", back_populates="salary_structure")
    components = relationship("SalaryComponent", back_populates="salary_structure", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<SalaryStructure employee_id={self.employee_id} basic_pay={self.basic_pay}>"


class SalaryComponent(Base):
    """Dynamic allowance/deduction rows attached to a salary structure (Backend Schema §3.5)."""

    __tablename__ = "salary_components"
    __table_args__ = (
        CheckConstraint("component_type IN ('allowance', 'deduction')", name="ck_salary_components_type"),
        CheckConstraint("amount >= 0", name="ck_salary_components_amount_nonnegative"),
    )

    id = Column(Integer, primary_key=True)
    salary_structure_id = Column(Integer, ForeignKey("salary_structures.id", ondelete="CASCADE"), nullable=False)
    component_type = Column(String(10), nullable=False)
    name = Column(String(60), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    salary_structure = relationship("SalaryStructure", back_populates="components")

    def __repr__(self) -> str:
        return f"<SalaryComponent {self.component_type} {self.name!r}={self.amount}>"
