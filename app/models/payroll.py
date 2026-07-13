from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PayrollRun(Base):
    """One processed pay period (Backend Schema §3.7)."""

    __tablename__ = "payroll_runs"
    __table_args__ = (CheckConstraint("status IN ('completed', 'failed')", name="ck_payroll_runs_status"),)

    id = Column(Integer, primary_key=True)
    period = Column(Date, unique=True, nullable=False)
    run_date = Column(DateTime, nullable=False, default=_utcnow)
    status = Column(String(15), nullable=False, default="completed")
    total_gross = Column(Numeric(14, 2), nullable=False)
    total_deductions = Column(Numeric(14, 2), nullable=False)
    total_net_pay = Column(Numeric(14, 2), nullable=False)
    employee_count = Column(Integer, nullable=False)
    run_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    line_items = relationship("PayrollLineItem", back_populates="payroll_run", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<PayrollRun period={self.period} status={self.status!r}>"


class PayrollLineItem(Base):
    """
    One employee's result within a payroll run — a snapshot, not a live
    reference (Backend Schema §3.8). This is the table the "numbers never
    change after the fact" guarantee depends on.
    """

    __tablename__ = "payroll_line_items"
    __table_args__ = (UniqueConstraint("payroll_run_id", "employee_id", name="uq_payroll_line_items_run_employee"),)

    id = Column(Integer, primary_key=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False)
    # RESTRICT, not CASCADE: the database itself refuses to let an employee
    # with payroll history be hard-deleted (Backend Schema §7). Paired with
    # passive_deletes=True on Employee.payroll_line_items so the ORM doesn't
    # try to work around it.
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False)
    employee_code_snapshot = Column(String(20), nullable=False)
    employee_name_snapshot = Column(String(120), nullable=False)
    days_present_snapshot = Column(Numeric(4, 1), nullable=False)
    days_on_leave_snapshot = Column(Numeric(4, 1), nullable=False)
    gross_pay = Column(Numeric(12, 2), nullable=False)
    total_deductions = Column(Numeric(12, 2), nullable=False)
    net_pay = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    payroll_run = relationship("PayrollRun", back_populates="line_items")
    employee = relationship("Employee", back_populates="payroll_line_items")
    components = relationship(
        "PayrollLineItemComponent", back_populates="line_item", cascade="all, delete-orphan"
    )
    payslip = relationship("Payslip", back_populates="line_item", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<PayrollLineItem run={self.payroll_run_id} employee={self.employee_id} net_pay={self.net_pay}>"


class PayrollLineItemComponent(Base):
    """
    Itemized earnings/deductions backing a payslip (Backend Schema §3.9) —
    independent of the live salary_components, so it stays accurate even if
    an employee's salary structure changes after this run.
    """

    __tablename__ = "payroll_line_item_components"
    __table_args__ = (
        CheckConstraint("component_type IN ('earning', 'deduction')", name="ck_payroll_line_item_components_type"),
    )

    id = Column(Integer, primary_key=True)
    payroll_line_item_id = Column(Integer, ForeignKey("payroll_line_items.id", ondelete="CASCADE"), nullable=False)
    component_type = Column(String(10), nullable=False)
    name = Column(String(60), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)

    line_item = relationship("PayrollLineItem", back_populates="components")

    def __repr__(self) -> str:
        return f"<PayrollLineItemComponent {self.component_type} {self.name!r}={self.amount}>"


class Payslip(Base):
    """Optional cache/reference for a generated payslip PDF (Backend Schema §3.10)."""

    __tablename__ = "payslips"

    id = Column(Integer, primary_key=True)
    payroll_line_item_id = Column(
        Integer, ForeignKey("payroll_line_items.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    generated_at = Column(DateTime, nullable=False, default=_utcnow)
    file_path = Column(String(255), nullable=True)

    line_item = relationship("PayrollLineItem", back_populates="payslip")

    def __repr__(self) -> str:
        return f"<Payslip line_item_id={self.payroll_line_item_id}>"
