from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, Date, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Employee(Base):
    """Core employee record (Backend Schema §3.2)."""

    __tablename__ = "employees"
    __table_args__ = (CheckConstraint("status IN ('active', 'inactive')", name="ck_employees_status"),)

    id = Column(Integer, primary_key=True)
    employee_code = Column(String(20), unique=True, nullable=False)
    full_name = Column(String(120), nullable=False)
    designation = Column(String(80), nullable=False)
    joining_date = Column(Date, nullable=False)
    email = Column(String(120), nullable=True)
    phone = Column(String(20), nullable=True)
    status = Column(String(10), nullable=False, default="active")
    deactivated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships -- convenience for the service layer built in Phase 4.
    bank_details = relationship(
        "EmployeeBankDetails", back_populates="employee", uselist=False, cascade="all, delete-orphan"
    )
    salary_structure = relationship(
        "SalaryStructure", back_populates="employee", uselist=False, cascade="all, delete-orphan"
    )
    attendance_records = relationship(
        "AttendanceRecord", back_populates="employee", cascade="all, delete-orphan"
    )
    # No delete cascade here on purpose, and passive_deletes=True so
    # SQLAlchemy doesn't try to manage/nullify these on an employee delete --
    # the database's ON DELETE RESTRICT (Backend Schema §7) is what should
    # reject the delete, not the ORM silently working around it.
    payroll_line_items = relationship(
        "PayrollLineItem", back_populates="employee", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Employee id={self.id} code={self.employee_code!r} status={self.status!r}>"
