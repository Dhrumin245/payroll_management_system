from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AttendanceRecord(Base):
    """Monthly attendance per employee (Backend Schema §3.6)."""

    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("employee_id", "period", name="uq_attendance_employee_period"),
        CheckConstraint("days_present >= 0", name="ck_attendance_days_present_nonnegative"),
        CheckConstraint("days_on_leave >= 0", name="ck_attendance_days_on_leave_nonnegative"),
        CheckConstraint(
            "days_present + days_on_leave <= total_working_days", name="ck_attendance_days_within_working_days"
        ),
    )

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    period = Column(Date, nullable=False)  # first-of-month; formatted as YYYY-MM at the route layer
    days_present = Column(Numeric(4, 1), nullable=False)
    days_on_leave = Column(Numeric(4, 1), nullable=False, default=0)
    total_working_days = Column(Numeric(4, 1), nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    employee = relationship("Employee", back_populates="attendance_records")

    def __repr__(self) -> str:
        return f"<AttendanceRecord employee_id={self.employee_id} period={self.period}>"
