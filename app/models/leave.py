from datetime import date, datetime, timezone
from sqlalchemy import Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LeaveType(Base):
    """Configuration of a specific leave category (e.g. Paid Leave, Sick Leave)."""

    __tablename__ = "leave_types"

    id = Column(Integer, primary_key=True)
    name = Column(String(60), nullable=False, unique=True)
    max_days_per_year = Column(Numeric(5, 1), nullable=True)
    is_paid = Column(Boolean, nullable=False, default=True)

    requests = relationship("LeaveRequest", back_populates="leave_type", cascade="all, delete-orphan")
    balances = relationship("LeaveBalance", back_populates="leave_type", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<LeaveType id={self.id} name={self.name!r}>"


class LeaveRequest(Base):
    """An employee's request for leave days."""

    __tablename__ = "leave_requests"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_leave_requests_status"),
        CheckConstraint("start_date <= end_date", name="ck_leave_requests_dates"),
    )

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    leave_type_id = Column(Integer, ForeignKey("leave_types.id", ondelete="CASCADE"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(String(255), nullable=True)
    status = Column(String(15), nullable=False, default="pending")
    approved_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    employee = relationship("Employee", backref="leave_requests")
    leave_type = relationship("LeaveType", back_populates="requests")
    approved_by = relationship("User", backref="approved_leaves")

    def __repr__(self) -> str:
        return f"<LeaveRequest id={self.id} employee_id={self.employee_id} status={self.status!r}>"


class LeaveBalance(Base):
    """Annual usage balance tracker for each leave type and employee."""

    __tablename__ = "leave_balances"
    __table_args__ = (
        UniqueConstraint("employee_id", "leave_type_id", "year", name="uq_leave_balance_employee_type_year"),
    )

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    leave_type_id = Column(Integer, ForeignKey("leave_types.id", ondelete="CASCADE"), nullable=False)
    year = Column(Integer, nullable=False)
    days_used = Column(Numeric(5, 1), nullable=False, default=0.0)

    employee = relationship("Employee", backref="leave_balances")
    leave_type = relationship("LeaveType", back_populates="balances")

    def __repr__(self) -> str:
        return f"<LeaveBalance employee_id={self.employee_id} leave_type_id={self.leave_type_id} year={self.year} days_used={self.days_used}>"
